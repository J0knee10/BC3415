"""The reusable prediction entry point.

Everything downstream — the Telegram bot, the OCR path, a notebook, the demo —
goes through ``predict()``. Nothing else needs to know how the model was built
or which rung of the ladder won.

    >>> from src.predict import predict
    >>> predict("Your DBS account is locked. Verify at http://bit.ly/x9")
    Prediction(label='smishing', confidence=0.98, red_flags=[...])

From the command line::

    python -m src.predict "your message here"
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from functools import lru_cache

import joblib
import pandas as pd

from . import evaluate as ev
from . import features as ft
from .config import CFG
from .preprocess import normalise_text
from .review import needs_review

MODEL_PATH = CFG.artifacts_dir / "model.joblib"


@dataclass
class Prediction:
    """One verdict, in the shape the bot needs to render it."""

    label: str
    confidence: float
    scores: dict[str, float] = field(default_factory=dict)
    red_flags: list[str] = field(default_factory=list)
    # True when the expected cost of this verdict standing alone exceeds the
    # cost of a human review (src/review.py). In a deployment the message
    # would go to a fraud analyst; here the reply says so.
    needs_review: bool = False

    @property
    def is_threat(self) -> bool:
        """True for smishing — the class that warrants a warning, not a note."""
        return self.label == CFG.target_label

    def describe(self) -> str:
        """User-facing one-liner, as the bot would send it."""
        icon = {"ham": "✅", "spam": "📣", "smishing": "⚠️"}.get(self.label, "•")
        if self.label == "ham" and self.needs_review:
            icon = "❔"  # not a tick: a person should check it first
        headline = {
            "ham": "No scam signals found",
            "spam": "Marketing / spam",
            "smishing": "Likely scam",
        }.get(self.label, self.label)
        line = f"{icon} {headline} ({self.confidence:.0%})"
        if self.red_flags:
            line += "\nFlagged on: " + ", ".join(f"'{w}'" for w in self.red_flags)
        if self.needs_review:
            # A missed scam costs 20 times a false alarm, so even a small
            # scam probability can make a human check worthwhile.
            reason = (
                "There is still enough chance this is a scam"
                if self.label == "ham"
                else "I'm not certain about this one"
            )
            line += (
                f"\n🔎 {reason}, so a person should check it. Until then, treat "
                "it as suspicious: don't click links, pay, or share codes."
            )
        elif self.label == "ham":
            # Not an all-clear: about a third of real local scams (19 of 60),
            # mostly chat-style ones with no link, get this verdict
            # (writeup "The application" and "Limitations").
            line += (
                "\nThis is not a guarantee. If it asks for money, a code or a "
                "login, check with the sender on a number you already trust."
            )
        return line


@lru_cache(maxsize=1)
def load_model():
    """Load the trained pipeline once per process."""
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"No model at {MODEL_PATH} — run `python -m src.train` first."
        )
    return joblib.load(MODEL_PATH)


def _frame(messages: list[str]) -> pd.DataFrame:
    """Build the two-column frame every pipeline in this project expects."""
    return pd.DataFrame(
        {
            ft.TEXT_RAW: messages,
            ft.TEXT_CLEAN: [normalise_text(m) for m in messages],
        }
    )


def predict_batch(messages: list[str], explain: bool = False) -> list[Prediction]:
    """Classify several messages at once. The bot path uses this with one.

    Raises ValueError on an empty message: the model would otherwise call
    nothing at all "legitimate" with high confidence.
    """
    if any(not str(m).strip() for m in messages):
        raise ValueError("cannot classify an empty message")
    model = load_model()
    X = _frame(messages)

    labels = model.predict(X)
    classes = list(model.classes_)

    if hasattr(model, "predict_proba"):
        probs = model.predict_proba(X)
        # Serve the operating point src.train chose on validation, so the
        # verdict a user sees is the one the test metrics describe.
        if getattr(model, "decision_rule_", "argmax") == "min_cost":
            labels = ev.min_cost_predict(probs, classes)
    else:  # an uncalibrated estimator — fall back to a hard 1.0
        probs = [[1.0 if c == lab else 0.0 for c in classes] for lab in labels]

    review = needs_review(probs, classes, labels)

    out = []
    for i, label in enumerate(labels):
        label = str(label)
        scores = {c: float(probs[i][j]) for j, c in enumerate(classes)}
        # Red flags only make sense for a warning; a legitimate message has none.
        flagged = explain and label != "ham"
        out.append(
            Prediction(
                label=label,
                confidence=scores[label],
                scores=scores,
                red_flags=explain_tokens(messages[i], label) if flagged else [],
                needs_review=bool(review[i]),
            )
        )
    return out


def predict(message: str, explain: bool = True) -> Prediction:
    """Classify a single message. The entry point everything else calls."""
    return predict_batch([message], explain=explain)[0]


# Punctuation trimmed from a token's ends for display, so 'customs.' reads as
# 'customs'. Tokens themselves are whitespace-delimited, which keeps a URL
# whole: 'bit.ly/x9' is one red flag, not three.
_TRIM = ".,!?:;\"'()[]"

# Function words LIME can pick up because they co-occur with the real cue
# ("Your account…"). They explain nothing to a user, so they are never shown
# as a red flag. Deliberately short: words like "free", "call" and "now" are
# real spam cues and stay (sklearn's English stop list would remove them).
_NOT_A_FLAG = {
    "a", "an", "the", "and", "or", "but", "if", "so", "as", "of", "to", "in",
    "on", "at", "by", "for", "from", "with", "this", "that", "these", "it",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "will", "would", "can", "could", "i", "me", "my", "we", "us",
    "our", "you", "your", "he", "she", "they", "them", "their", "its",
}


def explain(message: str, label: str, num_samples: int = 1000):
    """LIME explanation of one verdict, returned as LIME's own object.

    LIME perturbs the message by deleting random subsets of words, scores
    every variant with the real model, and fits a small weighted linear model
    to those scores. Each word's weight is its estimated push towards
    ``label``. Deleting *many* words at once is what lets it explain a 95%
    confident prediction, where removing any single word moves nothing.

    The notebook uses this directly for figures; the bot goes through
    ``explain_tokens``.
    """
    from lime.lime_text import LimeTextExplainer

    model = load_model()
    classes = list(model.classes_)
    explainer = LimeTextExplainer(
        class_names=classes,
        split_expression=r"\s+",
        random_state=CFG.split["random_state"],  # same flags every time
    )
    return explainer.explain_instance(
        message,
        lambda texts: model.predict_proba(_frame(list(texts))),
        labels=[classes.index(label)],
        num_features=10,
        num_samples=num_samples,
    )


def explain_tokens(message: str, label: str, top: int = 5) -> list[str]:
    """The words that pushed the message towards its predicted class, by LIME.

    Only positive evidence is kept, only above a small floor so that noise
    from the sampling does not surface as a flag, and never a bare function
    word (see ``_NOT_A_FLAG``) or a bare number: "482913" or "12" tells a
    user nothing, while an amount such as "£100,000" stays.

    A one-word message cannot be explained by deleting words, so the word
    itself is the flag.
    """
    model = load_model()
    if label not in list(model.classes_):
        return []
    tokens = message.split()
    if len(tokens) < 2:
        word = tokens[0].strip(_TRIM) if tokens else ""
        return [word] if _is_flaggable(word) else []

    col = list(model.classes_).index(label)
    flags: list[str] = []
    for word, weight in explain(message, label).as_list(label=col):
        word = word.strip(_TRIM)
        if weight > 0.01 and _is_flaggable(word) and word not in flags:
            flags.append(word)
    return flags[:top]


def _is_flaggable(word: str) -> bool:
    """A token worth showing a user: not empty, not a function word, and not
    a bare number unless it carries a currency sign."""
    if not word or word.lower() in _NOT_A_FLAG:
        return False
    return any(c.isalpha() for c in word) or any(c in "£$€" for c in word)


def main(argv: list[str]) -> int:
    # The verdict strings carry emoji; the Windows console defaults to cp1252.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    if len(argv) < 2:
        print(__doc__)
        return 1
    try:
        result = predict(" ".join(argv[1:]))
    except ValueError as exc:
        print(exc)
        return 1
    print(result.describe())
    print(f"\nscores: { {k: round(v, 3) for k, v in result.scores.items()} }")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
