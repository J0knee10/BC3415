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
   a template lands on the same side, and then any training row that is a
   near-copy of a held-out message (a paraphrase, a changed word) is dropped.
"""

from __future__ import annotations

import re
import sys

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
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


def near_duplicates(
    candidates: pd.Series,
    reference: pd.Series,
    threshold: float | None = None,
    corpus: pd.Series | None = None,
) -> np.ndarray:
    """Mask of ``candidates`` that nearly duplicate any message in ``reference``.

    Exact templates are not enough: real corpora carry the same scam with a
    reworded phrase, a different reference number or a trailing sentence, and
    none of these share a normalised template. ``near_copies`` runs this on
    both text columns.

    Similarity is cosine over character 3-5-gram TF-IDF. At the configured
    threshold (0.7) every pair inspected was the same message with a word or
    number changed; below it, pairs start to be merely similar topics.

    ``corpus`` fixes the TF-IDF weights. The pipeline passes the whole
    deduplicated corpus, so a pair's similarity does not depend on which other
    messages happen to be compared alongside it.
    """
    threshold = CFG.split["near_dup_threshold"] if threshold is None else threshold
    if len(candidates) == 0 or len(reference) == 0:
        return np.zeros(len(candidates), dtype=bool)

    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
    vec.fit((pd.concat([candidates, reference]) if corpus is None else corpus).astype(str))
    ref = vec.transform(reference.astype(str)).T.tocsc()
    cand = vec.transform(candidates.astype(str))

    best = np.zeros(cand.shape[0])
    for start in range(0, cand.shape[0], 2000):  # chunked to bound memory
        block = (cand[start : start + 2000] @ ref).max(axis=1)
        best[start : start + 2000] = block.toarray().ravel()
    return best >= threshold


def near_copies(
    candidates: pd.DataFrame, reference: pd.DataFrame, corpus: pd.DataFrame | None = None
) -> np.ndarray:
    """Near-duplicates by raw text *or* by normalised text.

    Raw text catches reworded copies; normalised text (numbers, URLs and
    amounts replaced by tokens) catches the same campaign sent with a
    different phone number or prize, whose digits otherwise dilute the
    similarity below the threshold.
    """
    raw = near_duplicates(
        candidates["text"], reference["text"], corpus=None if corpus is None else corpus["text"]
    )
    clean = near_duplicates(
        candidates[GROUP], reference[GROUP], corpus=None if corpus is None else corpus[GROUP]
    )
    return raw | clean


def split(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Stratified, template-aware train/val/test split.

    Two kinds of rows are held out of the evaluation splits by construction:

    * **Synthetic rows** (LLM-generated) go to train only. Testing on generated
      text would measure the generator.
    * **NUS rows** form a separate Singapore shift set rather than being mixed
      in, so the local-shift result is a clean comparison and not an average.

    No message is allowed on both sides of a boundary, by template or by near
    copy: training rows (real or synthetic) that nearly duplicate a validation
    or test message are dropped, and so are shift rows that nearly duplicate a
    training message.
    """
    cfg = CFG.split

    is_nus = df["source"] == "nus"
    is_synthetic = df["source"].isin(SYNTHETIC_SOURCES)
    pool = df[~is_nus & ~is_synthetic]

    train, test = _group_split(pool, cfg["test_size"], cfg["stratify"])
    train, val = _group_split(train, cfg["val_size"], cfg["stratify"])

    # Generated rows can only join the training split (src.ablation measures
    # them; train.use_synthetic decides whether the served model uses them).
    train = pd.concat([train, df[is_synthetic]], ignore_index=True)

    held_out = pd.concat([val, test])
    same_template = train[GROUP].isin(set(held_out[GROUP])).to_numpy()
    leak = same_template | near_copies(train, held_out, corpus=df)
    dropped = train[leak]
    print(
        f"  train rows dropped (near-copy of val/test):     {len(dropped):,}  "
        f"(synthetic {dropped['source'].isin(SYNTHETIC_SOURCES).sum():,}, "
        f"real {(~dropped['source'].isin(SYNTHETIC_SOURCES)).sum():,})"
    )
    train = train[~leak]

    shift_sg = df[is_nus]
    shift_ok = shift_sg[~near_copies(shift_sg, train, corpus=df)]
    print(f"  shift rows dropped (near-copy of train):       {len(shift_sg) - len(shift_ok):,}")

    return {
        "train": train.reset_index(drop=True),
        "val": val.reset_index(drop=True),
        "test": test.reset_index(drop=True),
        "shift_sg": shift_ok.reset_index(drop=True),
    }


def build(allow_missing_target: bool = False) -> dict[str, pd.DataFrame]:
    """Run the whole pipeline and write the splits to ``data/processed``.

    Stops, before writing anything, if no smishing rows were loaded (the
    Mendeley files are missing): otherwise it would quietly overwrite the
    three-class splits with ham/spam-only ones, and the next ``src.train``
    would replace the model. ``allow_missing_target=True`` (or
    ``--allow-two-class`` on the command line) builds the two-class
    splits deliberately.
    """
    print("=== loading ===")
    df = load_all()
    print(f"  total before deduplication: {len(df):,}")

    if CFG.target_label not in set(df["label"]) and not allow_missing_target:
        raise SystemExit(
            f"\nNo '{CFG.target_label}' messages loaded — the Mendeley files are "
            "missing (see `python -m src.download`).\nNothing was written. Run "
            "`python -m src.preprocess --allow-two-class` to build a ham/spam-only "
            "model on purpose."
        )

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
        sg = sg[~near_copies(sg, splits["train"], corpus=df)]
        splits["sg_scams"] = sg.reset_index(drop=True)

    for name, frame in splits.items():
        out = CFG.processed_dir / f"{name}.csv"
        frame.to_csv(out, index=False)
        counts = frame["label"].value_counts().to_dict()
        print(f"  {name:9} {len(frame):>7,}  {counts}")

    return splits


if __name__ == "__main__":
    build(allow_missing_target="--allow-two-class" in sys.argv[1:])
    sys.exit(0)
