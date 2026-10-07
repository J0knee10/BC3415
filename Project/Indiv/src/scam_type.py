"""LLM second stage — scam-type enrichment.

**This is not the classifier.** The trained model in ``src.predict`` makes the
ham / spam / smishing decision and is the component the project evaluates.
This module runs *only* on messages that model has already called smishing,
and only to name a likely scam type for the user-facing reply.

Why it is built this way: scam-type labels (job, investment, delivery,
banking impersonation, …) do not exist as public labelled message data. The
taxonomies live in analysis papers, not in a downloadable label column.
Training a scam-type classifier would mean inventing the labels, which would
undermine the one component the assignment weighs most. So the measurable
model gates an unmeasured one, and the boundary is stated rather than blurred.

The enrichment is explicitly **unevaluated**. No metric in this project
depends on it, and ``enrich`` refuses to run on anything the trained model did
not flag.

Runs on the Gemini API through Google AI Studio, which has a permanent free
tier — the project needs a few dozen calls, far below the daily quota. Set
``GEMINI_API_KEY`` (get one at https://aistudio.google.com/apikey; NTU
students may have this provisioned on their university Google account).
Without a key the module returns None and the bot shows the classifier's
verdict alone.

**Privacy note for the writeup:** on the free tier Google may use prompts and
outputs to improve its models, and the messages sent here are real ones
forwarded by users. Only messages already flagged as scams are sent, never the
legitimate ones — but the limitation belongs in §9 of the brief, and a billed
account or a locally hosted model would remove it.
"""

from __future__ import annotations

import os
import sys
from typing import Literal

from pydantic import BaseModel, Field

from .config import CFG
from .predict import Prediction, predict

# Flash-tier model: the free tier covers it, and naming a scam type from a
# short message is a shallow task that does not need a Pro model.
# Verify the id against https://ai.google.dev/gemini-api/docs/models if a call
# returns a 404 — Google retires model ids faster than most providers.
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")

# The taxonomy shown to the user. Drawn from the scam categories reported in
# the SMS-scam literature (delivery/parcel and banking impersonation lead the
# URL-based categories) rather than invented here.
SCAM_TYPES = Literal[
    "delivery_parcel",
    "banking_impersonation",
    "government_impersonation",
    "job_offer",
    "investment_crypto",
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

    try:
        client = genai.Client()  # reads GEMINI_API_KEY / GOOGLE_API_KEY
        interaction = client.interactions.create(
            model=MODEL,
            input=message,
            system_instruction=SYSTEM,
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": ScamType.model_json_schema(),
            },
        )
        return ScamType.model_validate_json(interaction.output_text)
    except Exception as exc:  # noqa: BLE001 — never break the verdict path
        print(f"[scam_type] enrichment unavailable: {exc}", file=sys.stderr)
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

    return "\n".join(lines)


def main(argv: list[str]) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    if len(argv) < 2:
        print(__doc__)
        return 1

    message = " ".join(argv[1:])
    prediction, scam = enrich(message)
    print(describe(prediction, scam))

    if prediction.label == CFG.target_label and scam is None:
        print(
            "\n(scam-type enrichment skipped — set GEMINI_API_KEY from "
            "https://aistudio.google.com/apikey)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
