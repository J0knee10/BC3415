"""Preprocessing: normalise, deduplicate, split.

Run with::

    python -m src.preprocess

Writes ``train.csv``, ``val.csv``, ``test.csv`` and ``shift_sg.csv`` into
``data/processed``.

Three decisions in here matter more than the code:

1. **Placeholders, not deletion.** URLs, phone numbers and amounts are replaced
   with marker tokens. Their presence is predictive even when the value is not,
   so deleting them throws away signal.
2. **Two text columns.** ``text_clean`` feeds word features; the original
   ``text`` feeds character features, because digits and punctuation are
   exactly what obfuscated smishing abuses.
3. **Deduplication before splitting, and template-aware splitting.** The
   corpora overlap — UCI absorbed part of the NUS corpus, so identical
   messages appear in both. Splitting first would put the same message in
   train and test and inflate every metric. Exact deduplication is not enough
   on its own: scam campaigns send one template with a different phone number
   or prize amount each time, and those variants survive it. The split is
   therefore made over *templates* (the normalised text), so every variant of
   a template lands on the same side.
"""

from __future__ import annotations

import re
import sys

import pandas as pd
from sklearn.model_selection import train_test_split

from .config import CFG
from .datasets import SYNTHETIC_SOURCES, load_all, load_sg_scams

# Source precedence when the same message appears in more than one corpus.
# The Mendeley smishing set wins because it carries the three-way label; a
# message it calls "smishing" is labelled only "spam" by UCI.
SOURCE_PRIORITY = ["mendeley_smishing", "uci", "nus", "mendeley_balanced"]

# --- Normalisation patterns ---------------------------------------------
# Bare domains are caught by TLD: ``sg`` because the product is for Singapore
# users, ``top`` and ``xyz`` because they are cheap and common in scam links.
RE_URL = re.compile(
    r"(https?://\S+|www\.\S+|\b\S+\.(?:com|net|org|ly|co|io|info|sg|top|xyz)\b\S*)",
    re.I,
)
RE_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")
# Phone-ish: 8+ characters of digits, optionally with +, spaces or dashes.
# Eight is the floor because a Singapore number (9123 4567) is eight digits;
# it also catches the longer UK premium-rate callbacks in the older corpora.
RE_PHONE = re.compile(r"\+?\d[\d\s\-()]{6,}\d")
RE_MONEY = re.compile(r"[£$€]\s?\d[\d,.]*|\b\d[\d,.]*\s?(?:usd|gbp|eur|sgd|pounds?|dollars?)\b", re.I)
RE_NUMBER = re.compile(r"\b\d+\b")
RE_SPACE = re.compile(r"\s+")


def normalise_text(text: str) -> str:
    """Produce the cleaned representation used by word-level features.

    Order matters: URLs and emails are consumed before phone numbers, which
    are consumed before bare numbers, so a phone number inside a URL is not
    chopped into pieces.
    """
    n = CFG.normalise
    s = str(text)
    s = RE_URL.sub(n["url_token"], s)
    s = RE_EMAIL.sub(n["email_token"], s)
    s = RE_MONEY.sub(n["money_token"], s)
    s = RE_PHONE.sub(n["phone_token"], s)
    s = RE_NUMBER.sub(n["number_token"], s)
    s = s.lower()
    s = re.sub(r"[^a-z\s]", " ", s)  # placeholders survive: they are alphabetic
    return RE_SPACE.sub(" ", s).strip()


def dedup_key(text: str) -> str:
    """Aggressive key for duplicate detection only — never used as a feature.

    Case, punctuation and whitespace are stripped so that cosmetic differences
    between corpora do not hide a genuine duplicate.
    """
    return RE_SPACE.sub("", re.sub(r"[^a-z0-9]", "", str(text).lower()))


def deduplicate(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Drop duplicate messages, keeping the row from the highest-priority source.

    Returns the deduplicated frame and a frame of the conflicts worth
    reporting: duplicates that carried *different* labels across corpora.
    """
    df = df.copy()
    df["_key"] = df["text"].map(dedup_key)
    df = df[df["_key"].str.len() > 0]

    # Conflicts: one message, more than one label. These are interesting in
    # their own right — they are the spam/smishing boundary cases.
    labels_per_key = df.groupby("_key")["label"].nunique()
    conflict_keys = labels_per_key[labels_per_key > 1].index
    conflicts = df[df["_key"].isin(conflict_keys)].sort_values("_key")

    df["_rank"] = df["source"].map({s: i for i, s in enumerate(SOURCE_PRIORITY)})
    df = df.sort_values("_rank").drop_duplicates(subset="_key", keep="first")

    return df.drop(columns=["_key", "_rank"]).reset_index(drop=True), conflicts


GROUP = "text_clean"  # the template a message belongs to; see split()


def _group_split(
    df: pd.DataFrame, test_size: float, stratify: bool
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split by template rather than by row, stratified on label.

    Each template is one unit, labelled by its first row, so the variants of a
    scam campaign cannot straddle the boundary. ``test_size`` is therefore a
    fraction of templates, which on this data is within a few rows of the same
    fraction of messages.
    """
    templates = df.groupby(GROUP)["label"].first()
    keep, hold = train_test_split(
        templates.index.to_numpy(),
        test_size=test_size,
        random_state=CFG.split["random_state"],
        stratify=templates.to_numpy() if stratify else None,
    )
    return df[df[GROUP].isin(set(keep))], df[df[GROUP].isin(set(hold))]


def split(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Stratified, template-aware train/val/test split.

    Two kinds of rows are held out of the evaluation splits by construction:

    * **Synthetic rows** (LLM-generated) go to train only. Testing on generated
      text would measure the generator.
    * **NUS rows** form a separate Singapore shift set rather than being mixed
      in, so the local-shift result is a clean comparison and not an average.

    No template is allowed on both sides of a boundary: synthetic rows that
    share a template with validation or test are dropped, and so are shift
    rows that share one with train.
    """
    cfg = CFG.split

    is_nus = df["source"] == "nus"
    is_synthetic = df["source"].isin(SYNTHETIC_SOURCES)
    pool = df[~is_nus & ~is_synthetic]

    train, test = _group_split(pool, cfg["test_size"], cfg["stratify"])
    train, val = _group_split(train, cfg["val_size"], cfg["stratify"])

    held_out = set(val[GROUP]) | set(test[GROUP])
    synthetic = df[is_synthetic]
    synthetic_ok = synthetic[~synthetic[GROUP].isin(held_out)]
    print(f"  synthetic rows dropped (template in val/test): {len(synthetic) - len(synthetic_ok):,}")

    # Synthetic augmentation joins the training split only.
    train = pd.concat([train, synthetic_ok], ignore_index=True)

    shift_sg = df[is_nus]
    shift_ok = shift_sg[~shift_sg[GROUP].isin(set(train[GROUP]))]
    print(f"  shift rows dropped (template in train):        {len(shift_sg) - len(shift_ok):,}")

    return {
        "train": train.reset_index(drop=True),
        "val": val.reset_index(drop=True),
        "test": test.reset_index(drop=True),
        "shift_sg": shift_ok.reset_index(drop=True),
    }


def build() -> dict[str, pd.DataFrame]:
    """Run the whole pipeline and write the splits to ``data/processed``."""
    print("=== loading ===")
    df = load_all()
    print(f"  total before deduplication: {len(df):,}")

    print("\n=== deduplicating ===")
    df, conflicts = deduplicate(df)
    print(f"  total after deduplication:  {len(df):,}")
    if len(conflicts):
        n_keys = conflicts["text"].map(dedup_key).nunique()
        print(f"  label conflicts across corpora: {n_keys} messages")
        conflicts.to_csv(CFG.processed_dir / "label_conflicts.csv", index=False)

    print("\n=== normalising ===")
    df["text_clean"] = df["text"].map(normalise_text)
    df = df[df["text_clean"].str.len() > 0].reset_index(drop=True)

    print("\n=== splitting ===")
    splits = split(df)

    # The Singapore scam set is evaluation-only: normalised like everything
    # else, kept clear of any template the model trains on, never split.
    try:
        sg = load_sg_scams()
    except FileNotFoundError as exc:
        print(f"  skipping sg_scams: {exc}")
    else:
        sg["text_clean"] = sg["text"].map(normalise_text)
        sg = sg[~sg[GROUP].isin(set(splits["train"][GROUP]))]
        splits["sg_scams"] = sg.reset_index(drop=True)

    for name, frame in splits.items():
        out = CFG.processed_dir / f"{name}.csv"
        frame.to_csv(out, index=False)
        counts = frame["label"].value_counts().to_dict()
        print(f"  {name:9} {len(frame):>7,}  {counts}")

    return splits


if __name__ == "__main__":
    build()
    sys.exit(0)
