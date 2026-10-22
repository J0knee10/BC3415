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


def test_deduplicate_prefers_mendeley_label():
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
    """Templates with several variants each, plus synthetic and NUS rows.

    Each template's wording is random letters, so different templates are not
    near-copies of each other; the variants of one template differ only in a
    number, so they are.
    """
    import random

    rng = random.Random(0)

    def words() -> str:
        return " ".join("".join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(7)) for _ in range(4))

    rows = []
    for label in ["ham", "spam", "smishing"]:
        for _ in range(20):
            body = words()
            for v in range(3):  # three variants of one template
                rows.append((f"{body} call {9000 + v}", label, "mendeley_smishing"))
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
    independent check of what preprocess.split() keeps apart. Different weights
    move a borderline pair by a few hundredths, so the check allows a 0.05
    margin above the pipeline's 0.7 threshold.
    """
    paths = {n: CFG.processed_dir / f"{n}.csv" for n in ["train", "val", "test"]}
    if not all(p.exists() for p in paths.values()):
        pytest.skip("no processed splits; run `python -m src.preprocess`")
    frames = {n: pd.read_csv(p).fillna("") for n, p in paths.items()}
    # Messages of a word or two ("okie great" against "okie") have so few
    # character n-grams that their similarity swings with the weights; they
    # carry no campaign to leak, so the independent check skips them.
    frames = {n: f[f["text"].str.len() >= 20] for n, f in frames.items()}
    held = pd.concat([frames["val"], frames["test"]])
    margin = CFG.split["near_dup_threshold"] + 0.05
    for column in ["text", GROUP]:
        assert not near_duplicates(held[column], frames["train"][column], margin).any()
        # Splitting whole clusters also keeps validation and test apart.
        assert not near_duplicates(frames["test"][column], frames["val"][column], margin).any()


# --- evaluation ---------------------------------------------------------
def test_bootstrap_by_cluster_widens_the_interval():
    """Twenty copies of one missed campaign are one piece of evidence, not twenty."""
    from src.evaluate import bootstrap_ci

    y_true = ["smishing"] * 40
    y_pred = ["spam"] * 20 + ["smishing"] * 20
    groups = ["campaign"] * 20 + [f"t{i}" for i in range(20)]

    lo_msg, hi_msg = bootstrap_ci(y_true, y_pred, "smishing")
    lo_grp, hi_grp = bootstrap_ci(y_true, y_pred, "smishing", groups=groups)
    assert hi_grp - lo_grp > hi_msg - lo_msg


def test_review_depends_on_which_mistake_is_at_stake():
    """A 3% chance of a missed scam needs a human; a 45% ham/spam split does not."""
    from src.review import needs_review

    classes = ["ham", "smishing", "spam"]
    proba = [
        [0.97, 0.03, 0.00],  # "legitimate", small chance it is a scam: 20 x 0.03 = 0.6
        [0.55, 0.00, 0.45],  # "legitimate", torn with marketing spam: 0 (spam as ham is free)
        [0.45, 0.00, 0.55],  # "spam", torn with legitimate: 1 x 0.45 = 0.45
    ]
    labels = ["ham", "ham", "spam"]
    assert needs_review(proba, classes, labels, cost=0.5).tolist() == [True, False, False]


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
