"""The reusable prediction entry point.

Everything downstream — the Telegram bot, the OCR path, a notebook, the demo —
goes through ``predict()``. Nothing else needs to know how the model was built
or which rung of the ladder won.

    >>> from src.predict import predict
    >>> predict("Your DBS account is locked. Verify at http://bit.ly/x9")
    Prediction(label='spam', confidence=0.97, red_flags=[...])

From the command line::

    python -m src.predict "your message here"
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from functools import lru_cache

import joblib
import pandas as pd

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
    else:  # an uncalibrated estimator — fall back to a hard 1.0
        probs = [[1.0 if c == lab else 0.0 for c in classes] for lab in labels]

    out = []
    for i, label in enumerate(labels):
        scores = {c: float(probs[i][j]) for j, c in enumerate(classes)}
        out.append(
            Prediction(
                label=str(label),
                confidence=scores[str(label)],
                scores=scores,
                red_flags=explain_tokens(messages[i], str(label)) if explain else [],
            )
        )
    return out


def predict(message: str, explain: bool = True) -> Prediction:
    """Classify a single message. The entry point everything else calls."""
    return predict_batch([message], explain=explain)[0]


def explain_tokens(message: str, label: str, top: int = 5) -> list[str]:
    """Words that pushed the message towards its predicted class.

    A leave-one-out probe: drop each word, re-score, and keep the words whose
    removal costs the most confidence. It needs no extra dependency and works
    on any estimator with ``predict_proba``, which makes it a usable default
    until LIME or SHAP is wired in for the report.
    """
    model = load_model()
    words = message.split()
    if len(words) < 2 or label not in list(model.classes_):
        return []

    col = list(model.classes_).index(label)
    base = model.predict_proba(_frame([message]))[0][col]

    variants = [" ".join(words[:i] + words[i + 1 :]) for i in range(len(words))]
    dropped = model.predict_proba(_frame(variants))[:, col]

    # A large drop means the word was holding the prediction up.
    contributions = sorted(
        ((base - float(p), w) for p, w in zip(dropped, words)), reverse=True
    )
    return [w for delta, w in contributions[:top] if delta > 0.01]


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
