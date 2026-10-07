"""Dataset acquisition.

Two of the four sources download without authentication and are fetched here.
The two Mendeley sets sit behind a bot check, so they are downloaded by hand
once and this module only verifies that they arrived in the right place.

Run with::

    python -m src.download
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import requests

from .config import CFG

# A browser-ish user agent; some academic hosts reject the default one.
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# --- Automatic sources --------------------------------------------------
AUTO_SOURCES = {
    "uci": {
        "url": "https://archive.ics.uci.edu/static/public/228/sms+spam+collection.zip",
        "archive": "sms_spam_collection.zip",
        "extract_to": "uci",
    },
    "nus": {
        # English half of the NUS SMS Corpus — Singaporean ham, used as the
        # local-shift test set.
        "url": (
            "https://raw.githubusercontent.com/kite1988/nus-sms-corpus/master/"
            "smsCorpus_en_xml_2015.03.09_all.zip"
        ),
        "archive": "nus_sms_en.zip",
        "extract_to": "nus",
    },
}

# --- Manual sources -----------------------------------------------------
# Mendeley serves its files through a bot check, so these cannot be scripted.
MANUAL_SOURCES = {
    "mendeley_smishing": {
        "page": "https://data.mendeley.com/datasets/f45bkkt8pr/1",
        "what": "SMS Phishing Dataset for Machine Learning and Pattern Recognition",
        "why": "the core 3-class training set (ham / spam / smishing)",
        "expect": "a .csv file containing a text column and a LABEL column",
    },
    "mendeley_balanced": {
        "page": "https://data.mendeley.com/datasets/vmg875v4xs/1",
        "what": "A Balanced Dataset for Spam and Smishing Detection using LLMs",
        "why": "train-side augmentation only — LLM-generated, never used for testing",
        "expect": "a .csv file of spam / smishing messages",
    },
}


def _download(url: str, dest: Path) -> Path:
    """Stream a URL to disk, skipping the work if the file is already there."""
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  already present: {dest.name}")
        return dest

    print(f"  downloading {url}")
    with requests.get(url, headers=HEADERS, stream=True, timeout=120) as r:
        r.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as fh:
            for chunk in r.iter_content(chunk_size=1 << 16):
                fh.write(chunk)
    print(f"  saved {dest.name} ({dest.stat().st_size / 1024:.0f} KB)")
    return dest


def fetch_auto() -> None:
    """Download and unpack the two freely scriptable sources."""
    for name, spec in AUTO_SOURCES.items():
        print(f"[{name}]")
        archive = _download(spec["url"], CFG.raw_dir / spec["archive"])
        target = CFG.raw_dir / spec["extract_to"]
        if target.exists() and any(target.iterdir()):
            print(f"  already extracted to {target.name}/")
            continue
        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(target)
        print(f"  extracted to {target.name}/")


def fetch_tessdata() -> Path | None:
    """Fetch the English language data Tesseract needs for the OCR path.

    The Tesseract binary ships separately from its language models, and a
    system install often has none. Rather than modify the system install, the
    model is kept inside the project and pointed at with TESSDATA_PREFIX.
    """
    dest = CFG.path("tessdata") / "eng.traineddata"
    if dest.exists() and dest.stat().st_size > 0:
        print(f"[tessdata] already present: {dest}")
        return dest

    # tessdata_fast: the smaller, quicker models. Accuracy on clean screenshot
    # text is close enough to the full models to not matter here.
    url = (
        "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/"
        "eng.traineddata"
    )
    print("[tessdata]")
    try:
        return _download(url, dest)
    except requests.RequestException as exc:
        print(f"  could not fetch language data: {exc}")
        return None


def check_manual() -> bool:
    """Report whether the hand-downloaded Mendeley files are in place.

    Returns True when every manual source has at least one CSV present.
    """
    all_ready = True
    for name, spec in MANUAL_SOURCES.items():
        folder = CFG.raw_dir / name
        folder.mkdir(parents=True, exist_ok=True)
        csvs = list(folder.glob("*.csv"))
        if csvs:
            print(f"[{name}] ready — {', '.join(f.name for f in csvs)}")
        else:
            all_ready = False
            print(f"[{name}] MISSING")
            print(f"    what:  {spec['what']}")
            print(f"    why:   {spec['why']}")
            print(f"    page:  {spec['page']}")
            print(f"    place: {folder}")
            print(f"    expect: {spec['expect']}")
    return all_ready


def main() -> int:
    print("=== automatic downloads ===")
    fetch_auto()
    fetch_tessdata()
    print("\n=== manual downloads ===")
    ready = check_manual()
    if not ready:
        print(
            "\nDownload the files listed above from their Mendeley pages and drop "
            "them into the folders shown, then re-run this module."
        )
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())
