"""The reusable prediction entry point.

Everything downstream — the Telegram bot, the OCR path, a notebook, the demo —
goes through ``predict()``. Nothing else needs to know how the model was built
or which rung of the ladder won.

    >>> from src.predict import predict
    >>> predict("Your DBS account is locked. Verify at http://bit.ly/x9")
    Prediction(label='smishing', confidence=0.99, red_flags=[...])

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

MODEL_PATH = CFG.artifacts_dir / "model.joblib"


@dataclass
class Prediction:
    """One verdict, in the shape the bot needs to render it."""

    label: str
    confidence: float
    scores: dict[str, float] = field(default_factory=dict)
    red_flags: list[str] = field(default_factory=list)

    @property
    def is_threat(self) -> bool:
        """True for smishing — the class that warrants a warning, not a note."""
        return self.label == CFG.target_label

    def describe(self) -> str:
        """User-facing one-liner, as the bot would send it."""
        icon = {"ham": "✅", "spam": "📣", "smishing": "⚠️"}.get(self.label, "•")
        headline = {
            "ham": "Looks legitimate",
            "spam": "Marketing / spam",
            "smishing": "Likely scam",
        }.get(self.label, self.label)
        line = f"{icon} {headline} ({self.confidence:.0%})"
        if self.red_flags:
            line += "\nFlagged on: " + ", ".join(f"'{w}'" for w in self.red_flags)
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
    """Classify several messages at once. The bot path uses this with one."""
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


def explain(message: str, label: str, num_samples: int = 1000):
    """LIME explanation of one verdict, returned as LIME's own object.

    LIME perturbs the message by deleting random subsets of words, scores
    every variant with the real model, and fits a small weighted linear model
    to those scores. Each word's weight is its estimated push towards
    ``label``. Deleting *many* words at once is what lets it explain a 99%
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

    Only positive evidence is kept, and only above a small floor so that noise
    from the sampling does not surface as a flag.
    """
    model = load_model()
    if len(message.split()) < 2 or label not in list(model.classes_):
        return []

    col = list(model.classes_).index(label)
    flags: list[str] = []
    for word, weight in explain(message, label).as_list(label=col):
        word = word.strip(_TRIM)
        if weight > 0.01 and word and word not in flags:
            flags.append(word)
    return flags[:top]


def main(argv: list[str]) -> int:
    # The verdict strings carry emoji; the Windows console defaults to cp1252.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    if len(argv) < 2:
        print(__doc__)
        return 1
    result = predict(" ".join(argv[1:]))
    print(result.describe())
    print(f"\nscores: { {k: round(v, 3) for k, v in result.scores.items()} }")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
