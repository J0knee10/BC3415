"""LLM second stage — scam-type enrichment.

**This is not the classifier.** The trained model in ``src.predict`` makes the
ham / spam / smishing decision and is the component the project evaluates.
This module runs *only* on messages that model has already called smishing,
and only to name a likely scam type for the user-facing reply.

Why it is built this way: scam-type labels (job, investment, delivery,
banking impersonation, …) do not exist as public labelled message data. The
taxonomies live in analysis papers, not in a downloadable label column.
Training a scam-type classifier would mean inventing the labels, which would
undermine the trained classifier's evaluation. So the measurable
model gates an unmeasured one, and the boundary is stated rather than blurred.

The enrichment is **advisory: spot-checked, not part of the evaluation**. No
metric in this project depends on it, and ``enrich`` refuses to run on
anything the trained model did not flag. ``evaluate()``
(``python -m src.scam_type --evaluate``) compares its label with the hand
labels on the Singapore scams the model caught, as a sanity check only.

Runs on the Gemini API through Google AI Studio, which has a permanent free
tier — the project needs a few dozen calls, far below the daily quota. Set
``GEMINI_API_KEY`` in ``.env`` (get one at
https://aistudio.google.com/apikey). Without a key the module returns None and the bot shows the classifier's
verdict alone.

**Privacy:** on the free tier Google may use prompts and
outputs to improve its models, and the messages sent here are real ones
forwarded by users. Only messages already flagged as scams are sent, never the
legitimate ones. A billed account or a locally hosted model would remove the
limitation.
"""

from __future__ import annotations

import os
import sys
import threading
from typing import Literal

from pydantic import BaseModel, Field

from .config import CFG
from .predict import Prediction, predict

# Naming a scam type from a short message is a shallow task, so the lite
# Flash tier is enough: it is the fastest and least contended, and the free
# tier covers it. "-latest" aliases are used because Google retires dated ids
# quickly (gemini-2.5-flash already returns 404 for new keys) and the newest
# models are often overloaded.
DEFAULT_MODEL = "gemini-flash-lite-latest"
# GEMINI_MODEL in .env (or the shell) wins; a blank value means the default.
MODEL = os.environ.get("GEMINI_MODEL", "").strip() or DEFAULT_MODEL
# Tried in order when the chosen model fails, is overloaded (503) or is slow.
# A user is waiting on the reply, so each attempt is capped at TIMEOUT seconds.
FALLBACK_MODELS = [DEFAULT_MODEL, "gemini-flash-latest"]
TIMEOUT = 15.0


def _with_deadline(fn, seconds: float):
    """Run ``fn`` in a daemon thread; raise TimeoutError if it overruns.

    A daemon thread, so an abandoned slow call holds up neither the reply nor
    the process exiting.
    """
    box: dict = {}

    def run() -> None:
        try:
            box["value"] = fn()
        except Exception as exc:  # noqa: BLE001 — re-raised in the caller
            box["error"] = exc

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(seconds)
    if worker.is_alive():
        raise TimeoutError
    if "error" in box:
        raise box["error"]
    return box["value"]

# The taxonomy shown to the user. Drawn from the scam categories reported in
# the SMS-scam literature (delivery/parcel and banking impersonation lead the
# URL-based categories), and it includes every category used to hand-label
# the Singapore scam set, so ``evaluate`` can compare like with like.
SCAM_TYPES = Literal[
    "delivery_parcel",
    "banking_impersonation",
    "government_impersonation",
    "telco_impersonation",
    "ecommerce",
    "job_offer",
    "investment",
    "prize_lottery",
    "account_credential",
    "romance_social",
    "other",
]

SYSTEM = """You label SMS scam messages by type for a Singapore scam-checking bot.

A trained classifier has already decided this message is a scam. Do not \
second-guess that decision — your only job is to say what kind of scam it \
looks like, and to point at the specific phrases that indicate it.

Pick the single closest type. Use "other" when none fits rather than forcing \
a match. Keep the explanation to one short sentence a non-technical user \
would understand. Quote indicators verbatim from the message."""


class ScamType(BaseModel):
    """The enrichment result. Advisory only — nothing is scored on it."""

    scam_type: SCAM_TYPES = Field(description="The closest scam category")
    explanation: str = Field(description="One short sentence for a non-technical user")
    indicators: list[str] = Field(
        default_factory=list, description="Phrases quoted verbatim from the message"
    )


def available() -> bool:
    """Whether the second stage can run at all in this environment."""
    return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))


def classify_scam_type(message: str) -> ScamType | None:
    """Name the scam type for a message already flagged as smishing.

    Returns None when the API is unavailable or the call fails. A failure here
    must never take down the classifier's verdict — the enrichment is a bonus,
    not a dependency.
    """
    if not available():
        return None

    try:
        from google import genai
    except ImportError:
        return None

    client = genai.Client()  # reads GEMINI_API_KEY / GOOGLE_API_KEY

    def call(model: str) -> ScamType:
        interaction = client.interactions.create(
            model=model,
            input=message,
            system_instruction=SYSTEM,
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": ScamType.model_json_schema(),
            },
        )
        return ScamType.model_validate_json(interaction.output_text)

    for model in dict.fromkeys([MODEL, *FALLBACK_MODELS]):  # ordered, no repeats
        # The SDK retries overloaded (5xx) calls with backoff for up to two
        # minutes. The deadline is enforced here instead, so a busy model
        # costs the user at most TIMEOUT seconds before the fallback is tried.
        try:
            return _with_deadline(lambda m=model: call(m), TIMEOUT)
        except TimeoutError:
            print(f"[scam_type] {model} gave no answer within {TIMEOUT:.0f}s", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001 — never break the verdict path
            print(f"[scam_type] {model} unavailable: {exc}", file=sys.stderr)
    return None


def enrich(
    message: str, prediction: Prediction | None = None
) -> tuple[Prediction, ScamType | None]:
    """Classify a message, then enrich it only if it was flagged as smishing.

    This is the function the bot calls. The gate is enforced here rather than
    left to the caller, so the second stage cannot accidentally be run on
    everything — which also keeps legitimate messages off the network.
    """
    prediction = prediction or predict(message)

    if prediction.label != CFG.target_label:
        return prediction, None

    return prediction, classify_scam_type(message)


def describe(prediction: Prediction, scam: ScamType | None) -> str:
    """The full user-facing reply: the model's verdict, then the enrichment."""
    lines = [prediction.describe()]

    if scam is not None:
        pretty = scam.scam_type.replace("_", " ").title()
        lines.append(f"\nLooks like: {pretty}")
        lines.append(scam.explanation)
        if scam.indicators:
            lines.append("Watch for: " + ", ".join(f'"{s}"' for s in scam.indicators))

    return "\n".join(lines)


def evaluate() -> "pd.DataFrame | None":
    """Spot-check the scam-type labels against the hand-labelled Singapore set.

    Runs only on the Singapore scams the trained model actually called
    smishing, because those are the only ones the gate lets through in the
    product. Advisory: no model decision depends on it. Writes
    ``reports/scam_type_eval.csv``.
    """
    import pandas as pd

    if not available():
        print("GEMINI_API_KEY not set; nothing to evaluate")
        return None
    path = CFG.reports_dir / "sg_scams_predictions.csv"
    if not path.exists():
        print(f"{path.name} missing; run `python -m src.train` first")
        return None

    df = pd.read_csv(path)
    target = CFG.target_label
    flagged = df[(df["label"] == target) & (df["predicted"] == target)].reset_index(drop=True)

    rows = []
    for text, labelled in zip(flagged["text"], flagged["scam_type"]):
        result = classify_scam_type(text)
        rows.append(
            {
                "text": text,
                "labelled": labelled,
                "llm": result.scam_type if result else None,
                "agree": bool(result and result.scam_type == labelled),
            }
        )
    table = pd.DataFrame(rows)
    answered = table["llm"].notna()
    print(
        f"scam type agrees with the hand label on {table['agree'].sum()} of "
        f"{len(table)} flagged Singapore scams ({answered.sum()} answered)"
    )
    print(pd.crosstab(table["labelled"], table["llm"].fillna("no answer")).to_string())
    table.to_csv(CFG.reports_dir / "scam_type_eval.csv", index=False)
    return table


def main(argv: list[str]) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    if len(argv) < 2:
        print(__doc__)
        return 1
    if argv[1] == "--evaluate":
        evaluate()
        return 0

    message = " ".join(argv[1:])
    prediction, scam = enrich(message)
    print(describe(prediction, scam))

    if prediction.label == CFG.target_label and scam is None:
        if available():
            print("\n(scam-type enrichment failed — see the error above)")
        else:
            print(
                "\n(scam-type enrichment skipped — set GEMINI_API_KEY in .env, "
                "from https://aistudio.google.com/apikey)"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
