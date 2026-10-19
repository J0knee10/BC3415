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
from src.preprocess import (
    GROUP,
    dedup_key,
    deduplicate,
    near_duplicates,
    normalise_text,
    split,
)


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


def test_near_duplicates_catches_paraphrase_not_topic():
    held = pd.Series(["This msg is for your mobile content order It has been resent as previous attempt failed"])
    cand = pd.Series(
        [
            "this msg is for your mobile content order it ingest been resent as previous attempt failed",
            "Your parcel could not be delivered, update your address at the link",
        ]
    )
    assert near_duplicates(cand, held).tolist() == [True, False]


def test_no_training_row_is_a_near_copy_of_held_out():
    splits = split(_toy_corpus())
    held = pd.concat([splits["val"]["text"], splits["test"]["text"]])
    assert not near_duplicates(splits["train"]["text"], held).any()


def test_real_splits_have_no_near_copy_across_the_boundary():
    """The guarantee on the actual data, not just the toy corpus.

    Uses its own TF-IDF weights rather than the pipeline's, so it is an
    independent check of what preprocess.split() removed. Different weights
    move a borderline pair by a few hundredths, so the check allows a 0.05
    margin above the pipeline's 0.7 threshold.
    """
    paths = {n: CFG.processed_dir / f"{n}.csv" for n in ["train", "val", "test"]}
    if not all(p.exists() for p in paths.values()):
        pytest.skip("no processed splits; run `python -m src.preprocess`")
    frames = {n: pd.read_csv(p).fillna("") for n, p in paths.items()}
    held = pd.concat([frames["val"], frames["test"]])
    for column in ["text", GROUP]:
        margin = CFG.split["near_dup_threshold"] + 0.05
        assert not near_duplicates(held[column], frames["train"][column], margin).any()


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
def test_empty_message_is_rejected():
    from src.predict import predict

    with pytest.raises(ValueError):
        predict("   ")


@needs_model
def test_llm_stage_never_sees_a_non_scam(monkeypatch):
    from src import scam_type

    def fail(_message):
        raise AssertionError("LLM called on a message the model did not flag")

    monkeypatch.setattr(scam_type, "classify_scam_type", fail)
    prediction, scam = scam_type.enrich("Eh you reaching already? I order first ah")
    assert prediction.label != CFG.target_label
    assert scam is None


@needs_model
def test_photo_caption_is_classified_when_image_has_no_text(monkeypatch):
    import asyncio
    import types

    from app import bot

    replies = []

    async def reply(text, **_):
        replies.append(text)

    async def send_action(_):
        pass

    class File:
        async def download_to_drive(self, path):
            open(path, "wb").close()

    class Bot:
        async def get_file(self, _):
            return File()

    monkeypatch.setattr(bot.scam_type, "classify_scam_type", lambda _m: None)  # no network
    monkeypatch.setattr(bot.ocr, "tesseract_available", lambda: True)
    monkeypatch.setattr(bot.ocr, "image_to_text", lambda _path: "")
    message = types.SimpleNamespace(
        caption="Your parcel is held at customs. Pay at http://sgpost-clear.co/pay",
        photo=[types.SimpleNamespace(file_id="x")],
        chat=types.SimpleNamespace(send_action=send_action),
        reply_text=reply,
    )
    update = types.SimpleNamespace(effective_message=message)
    asyncio.run(bot.on_photo(update, types.SimpleNamespace(bot=Bot())))

    assert len(replies) == 1
    # A scam verdict, not merely the word "scam" ("No scam signals found"
    # contains it too).
    assert replies[0].startswith("⚠️ Likely scam")
