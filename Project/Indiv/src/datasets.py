"""Per-source loaders.

Each loader returns a DataFrame with the same three columns:

    text    the raw message, untouched
    label   one of ham / spam / smishing
    source  which corpus it came from

Unifying the schema here means the rest of the pipeline never has to know
which corpus a message came from, except where that is deliberately used
(the NUS rows form the Singapore shift set, the LLM-generated rows are barred
from the test split).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

from .config import CFG

COLUMNS = ["text", "label", "source"]

# Mendeley's label column uses its own vocabulary; map it onto ours.
LABEL_ALIASES = {
    "ham": "ham",
    "legitimate": "ham",
    "legit": "ham",
    "normal": "ham",
    "0": "ham",
    "spam": "spam",
    "1": "spam",
    "smishing": "smishing",
    "smish": "smishing",
    "phishing": "smishing",
    "phish": "smishing",
    "2": "smishing",
}


def _normalise_label(value: object) -> str | None:
    """Map a source-specific label onto ham / spam / smishing, or None."""
    return LABEL_ALIASES.get(str(value).strip().lower())


def _frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=COLUMNS)


# --- UCI ----------------------------------------------------------------
def load_uci() -> pd.DataFrame:
    """UCI SMS Spam Collection — 5,574 messages, ham/spam, tab separated.

    Supplies the bulk of the ham and the commercial-spam class. Contains no
    smishing label: its spam class mixes marketing with scams, which is
    exactly the conflation this project sets out to undo.
    """
    path = CFG.raw_dir / "uci" / "SMSSpamCollection"
    df = pd.read_csv(
        path,
        sep="\t",
        header=None,
        names=["label", "text"],
        encoding="latin-1",  # the file is not valid UTF-8
        quoting=3,  # csv.QUOTE_NONE — messages contain unbalanced quotes
    )
    df["label"] = df["label"].map(_normalise_label)
    df["source"] = "uci"
    return _frame(df.dropna(subset=["label", "text"]).to_dict("records"))


# --- NUS ----------------------------------------------------------------
def load_nus(singapore_only: bool = True) -> pd.DataFrame:
    """NUS SMS Corpus — Singaporean ham, used as the local-shift test set.

    The corpus is unlabelled because every message in it is legitimate: it was
    collected from volunteers, not from a spam trap. All rows are therefore
    ham by construction.

    The XML is ~44 MB, so it is streamed with iterparse rather than parsed
    into a single tree.

    Args:
        singapore_only: keep only messages whose sender profile reports
            country ``SG``. Leaving this on is what makes the shift set local.
    """
    path = CFG.raw_dir / "nus" / "smsCorpus_en_2015.03.09_all.xml"
    rows: list[dict] = []

    for _event, elem in ET.iterparse(path, events=("end",)):
        if not elem.tag.endswith("message"):
            continue

        text_el = elem.find("text")
        text = (text_el.text or "").strip() if text_el is not None else ""

        country_el = elem.find("./source/userProfile/country")
        country = (country_el.text or "").strip() if country_el is not None else ""

        if text and (not singapore_only or country.upper() == "SG"):
            rows.append({"text": text, "label": "ham", "source": "nus"})

        elem.clear()  # release the parsed element; keeps memory flat

    return _frame(rows)


# --- Mendeley -----------------------------------------------------------
def _read_mendeley_csv(folder: Path) -> pd.DataFrame:
    """Read whichever CSV was hand-placed in a Mendeley folder.

    Column names are inferred rather than hardcoded, because the published
    files use different headers across versions.
    """
    csvs = sorted(folder.glob("*.csv"))
    if not csvs:
        raise FileNotFoundError(
            f"No CSV in {folder}. Run `python -m src.download` for instructions."
        )

    df = pd.read_csv(csvs[0], encoding="latin-1", on_bad_lines="skip")

    # Find the label column: the one whose values map cleanly onto our labels.
    label_col = None
    for col in df.columns:
        mapped = df[col].astype(str).map(_normalise_label)
        if mapped.notna().mean() > 0.9:
            label_col = col
            break

    # Find the text column: the remaining object column with the longest values.
    candidates = [
        c
        for c in df.columns
        if c != label_col and df[c].dtype == object
    ]
    if not candidates:
        raise ValueError(f"No text column found in {csvs[0].name}")
    text_col = max(candidates, key=lambda c: df[c].astype(str).str.len().mean())

    if label_col is None:
        raise ValueError(
            f"No label column found in {csvs[0].name}; columns are {list(df.columns)}"
        )

    out = pd.DataFrame(
        {
            "text": df[text_col].astype(str),
            "label": df[label_col].map(_normalise_label),
        }
    )
    return out.dropna(subset=["label"])


def load_mendeley_smishing() -> pd.DataFrame:
    """Mendeley SMS Phishing (f45bkkt8pr) — the only corpus that separates
    commercial spam from smishing. This is the project's core training set."""
    df = _read_mendeley_csv(CFG.raw_dir / "mendeley_smishing")
    df["source"] = "mendeley_smishing"
    return _frame(df.to_dict("records"))


def load_mendeley_balanced() -> pd.DataFrame:
    """Mendeley Balanced Spam/Smishing (vmg875v4xs) — LLM-generated.

    Train-side augmentation only. ``preprocess`` enforces that these rows
    never reach the validation or test splits; synthetic text in a test set
    would measure the generator, not the classifier.
    """
    df = _read_mendeley_csv(CFG.raw_dir / "mendeley_balanced")
    df["source"] = "mendeley_balanced"
    return _frame(df.to_dict("records"))


# --- Registry -----------------------------------------------------------
# Sources whose rows may never enter validation or test.
SYNTHETIC_SOURCES = {"mendeley_balanced"}

LOADERS = {
    "uci": load_uci,
    "nus": load_nus,
    "mendeley_smishing": load_mendeley_smishing,
    "mendeley_balanced": load_mendeley_balanced,
}


def load_all(sources: list[str] | None = None, strict: bool = False) -> pd.DataFrame:
    """Load and concatenate every available source.

    Args:
        sources: subset to load; defaults to all registered sources.
        strict: raise if a source is missing, instead of skipping it with a
            warning. Useful once all four datasets are in place.
    """
    frames = []
    for name in sources or list(LOADERS):
        try:
            frame = LOADERS[name]()
        except FileNotFoundError as exc:
            if strict:
                raise
            print(f"  skipping {name}: {exc}")
            continue
        print(f"  loaded {name}: {len(frame):,} rows")
        frames.append(frame)

    if not frames:
        raise RuntimeError("No sources loaded; run `python -m src.download` first.")
    return pd.concat(frames, ignore_index=True)
