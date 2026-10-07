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
3. **Deduplication before splitting.** The corpora overlap — UCI absorbed part
   of the NUS corpus, so identical messages appear in both. Splitting first
   would put the same message in train and test and inflate every metric.
"""

from __future__ import annotations

import re
import sys

import pandas as pd
from sklearn.model_selection import train_test_split

from .config import CFG
from .datasets import SYNTHETIC_SOURCES, load_all

# Source precedence when the same message appears in more than one corpus.
# The Mendeley smishing set wins because it carries the three-way label; a
# message it calls "smishing" is labelled only "spam" by UCI.
SOURCE_PRIORITY = ["mendeley_smishing", "uci", "nus", "mendeley_balanced"]

# --- Normalisation patterns ---------------------------------------------
RE_URL = re.compile(r"(https?://\S+|www\.\S+|\b\S+\.(?:com|net|org|ly|co|io|info)\b\S*)", re.I)
RE_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")
# Phone-ish: 8+ digits, optionally with +, spaces or dashes. Matches UK/SG
# shortcodes and the long numbers smishing uses as callbacks.
RE_PHONE = re.compile(r"\+?\d[\d\s\-()]{7,}\d")
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


def split(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Stratified train/val/test split.

    Two rows are held out of the evaluation splits by construction:

    * **Synthetic rows** (LLM-generated) go to train only. Testing on generated
      text would measure the generator.
    * **NUS rows** form a separate Singapore shift set rather than being mixed
      in, so the local-shift result is a clean comparison and not an average.
    """
    cfg = CFG.split

    shift_sg = df[df["source"] == "nus"].reset_index(drop=True)
    synthetic = df[df["source"].isin(SYNTHETIC_SOURCES)].reset_index(drop=True)
    pool = df[(df["source"] != "nus") & (~df["source"].isin(SYNTHETIC_SOURCES))]

    strat = pool["label"] if cfg["stratify"] else None
    train_pool, test = train_test_split(
        pool,
        test_size=cfg["test_size"],
        random_state=cfg["random_state"],
        stratify=strat,
    )

    strat = train_pool["label"] if cfg["stratify"] else None
    train, val = train_test_split(
        train_pool,
        test_size=cfg["val_size"],
        random_state=cfg["random_state"],
        stratify=strat,
    )

    # Synthetic augmentation joins the training split only.
    train = pd.concat([train, synthetic], ignore_index=True)

    return {
        "train": train.reset_index(drop=True),
        "val": val.reset_index(drop=True),
        "test": test.reset_index(drop=True),
        "shift_sg": shift_sg,
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
    for name, frame in splits.items():
        out = CFG.processed_dir / f"{name}.csv"
        frame.to_csv(out, index=False)
        counts = frame["label"].value_counts().to_dict()
        print(f"  {name:9} {len(frame):>7,}  {counts}")

    return splits


if __name__ == "__main__":
    build()
    sys.exit(0)
