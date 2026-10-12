"""Checks on the guarantees the evaluation depends on.

Run from the project root with::

    python -m pytest tests

The split tests use a small synthetic frame, so they run without the datasets.
The serving tests need ``artifacts/model.joblib`` and skip without it.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.config import CFG
from src.preprocess import GROUP, dedup_key, deduplicate, normalise_text, split


# --- normalisation ------------------------------------------------------
@pytest.mark.parametrize(
    "text, token",
    [
        ("Verify at http://bit.ly/x9", "urltoken"),
        ("Track at singpost.sg/track", "urltoken"),
        ("Call 91234567 now", "phonetoken"),  # an 8-digit Singapore number
        ("Call +65 9123 4567 now", "phonetoken"),
        ("You won £2000", "moneytoken"),
    ],
)
def test_normalise_replaces_with_placeholder(text, token):
    assert token in normalise_text(text).split()


def test_dedup_key_ignores_cosmetic_differences():
    assert dedup_key("Hello, World!") == dedup_key("hello world")


def test_deduplicate_keeps_finer_label():
    df = pd.DataFrame(
        {
            "text": ["Claim your prize now", "claim your prize now!"],
            "label": ["spam", "smishing"],
            "source": ["uci", "mendeley_smishing"],
        }
    )
    deduped, conflicts = deduplicate(df)
    assert len(deduped) == 1
    assert deduped.loc[0, "label"] == "smishing"  # Mendeley outranks UCI
    assert len(conflicts) == 2


# --- splitting ----------------------------------------------------------
def _toy_corpus() -> pd.DataFrame:
    """Templates with several variants each, plus synthetic and NUS rows."""
    rows = []
    for label in ["ham", "spam", "smishing"]:
        for t in range(20):
            for v in range(3):  # three variants of one template
                rows.append((f"{label} template {chr(97 + t)} call {9000 + v}", label, "mendeley_smishing"))
    rows += [(f"generated scam {chr(97 + i)}", "smishing", "mendeley_balanced") for i in range(10)]
    rows += [(f"lunch at {chr(97 + i)} later", "ham", "nus") for i in range(10)]
    df = pd.DataFrame(rows, columns=["text", "label", "source"])
    df[GROUP] = df["text"].map(normalise_text)
    return df


def test_no_template_crosses_a_split():
    splits = split(_toy_corpus())
    groups = {name: set(frame[GROUP]) for name, frame in splits.items()}
    assert not groups["train"] & groups["val"]
    assert not groups["train"] & groups["test"]
    assert not groups["val"] & groups["test"]


def test_synthetic_and_nus_rows_stay_out_of_evaluation():
    splits = split(_toy_corpus())
    for name in ["val", "test"]:
        assert not splits[name]["source"].isin(["mendeley_balanced", "nus"]).any()
    assert (splits["shift_sg"]["source"] == "nus").all()


# --- serving ------------------------------------------------------------
needs_model = pytest.mark.skipif(
    not (CFG.artifacts_dir / "model.joblib").exists(),
    reason="no trained model; run `python -m src.train`",
)


@needs_model
def test_predict_returns_a_valid_verdict():
    from src.predict import predict

    result = predict("Your DBS account is suspended. Verify at http://dbs-secure.co/login")
    assert result.label in CFG.labels
    assert 0.0 <= result.confidence <= 1.0
    assert abs(sum(result.scores.values()) - 1.0) < 1e-6


@needs_model
def test_legitimate_message_has_no_red_flags():
    from src.predict import predict

    result = predict("Eh you reaching already? I order first ah")
    assert result.label == "ham"
    assert result.red_flags == []


@needs_model
def test_llm_stage_never_sees_a_non_scam(monkeypatch):
    from src import scam_type

    def fail(_message):
        raise AssertionError("LLM called on a message the model did not flag")

    monkeypatch.setattr(scam_type, "classify_scam_type", fail)
    prediction, scam = scam_type.enrich("Eh you reaching already? I order first ah")
    assert prediction.label != CFG.target_label
    assert scam is None
