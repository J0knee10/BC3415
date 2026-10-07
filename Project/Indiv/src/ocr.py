"""Screenshot → text.

Users forward screenshots far more readily than they retype a message, so the
bot accepts images. This module turns one into text for the classifier.

It is a genuine weak point and the writeup should say so: OCR errors land
*upstream* of the model, so a misread character becomes a feature the
classifier never saw in training. Dark mode, low resolution and the chat
bubble's own UI text all degrade it.

Needs the Tesseract binary on the system (the ``pytesseract`` package is only
a wrapper). ``tesseract_available()`` reports whether it is there.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path

# Common install locations on Windows, checked when tesseract is not on PATH.
WINDOWS_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"C:\msys64\ucrt64\bin\tesseract.exe",
    r"C:\msys64\mingw64\bin\tesseract.exe",
]

# Lines a screenshot picks up from the chat app rather than the message:
# timestamps, delivery ticks, and the typical UI furniture.
STATUS = r"(?:delivered|read|sent|seen|forwarded|online|typing\.{0,3})"
TIMESTAMP = r"(?:\d{1,2}[:.]\d{2}\s*(?:am|pm)?)"
# A noise line is any combination of a timestamp and a status word, in either
# order, with nothing else on it — which is what the footer of a chat bubble
# looks like once OCR has flattened it onto one line.
UI_NOISE = re.compile(
    rf"^\s*(?:today|yesterday|{TIMESTAMP}|{STATUS})"
    rf"(?:\s+(?:{TIMESTAMP}|{STATUS}))*\s*$",
    re.I,
)


def _configure() -> bool:
    """Point pytesseract at the binary and the language data.

    A system Tesseract often ships without English language data, so the
    project keeps its own copy (fetched by ``src.download``) and points
    TESSDATA_PREFIX at it rather than touching the system install.
    """
    import pytesseract

    from .config import CFG

    found = shutil.which("tesseract")
    if not found:
        found = next((p for p in WINDOWS_PATHS if Path(p).exists()), None)
    if not found:
        return False

    pytesseract.pytesseract.tesseract_cmd = found

    local = CFG.path("tessdata")
    if (local / "eng.traineddata").exists():
        os.environ["TESSDATA_PREFIX"] = str(local)

    return True


def tesseract_available() -> bool:
    """Whether OCR can run in this environment."""
    try:
        return _configure()
    except ImportError:
        return False


def _prepare(image):
    """Light preprocessing — greyscale and upscale small images.

    Tesseract is trained on roughly 300 DPI text; phone screenshots are often
    well below that, and upscaling alone recovers a surprising amount.
    """
    from PIL import Image

    image = image.convert("L")
    if image.width < 1000:
        scale = 1000 / image.width
        image = image.resize(
            (int(image.width * scale), int(image.height * scale)), Image.LANCZOS
        )
    return image


def clean_ocr_text(text: str) -> str:
    """Strip chat-app furniture so the classifier sees the message, not the UI."""
    lines = [ln.strip() for ln in text.splitlines()]
    kept = [ln for ln in lines if ln and not UI_NOISE.match(ln)]
    return " ".join(kept).strip()


def image_to_text(path: str | Path, clean: bool = True) -> str:
    """Extract the message text from a screenshot.

    Raises RuntimeError when Tesseract is missing, so the bot can tell the user
    to paste the text instead rather than failing silently.
    """
    import pytesseract
    from PIL import Image

    if not _configure():
        raise RuntimeError(
            "Tesseract is not installed or not on PATH. Install it, or paste "
            "the message text instead of a screenshot."
        )

    with Image.open(path) as image:
        text = pytesseract.image_to_string(_prepare(image))

    return clean_ocr_text(text) if clean else text.strip()


def main(argv: list[str]) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    if len(argv) < 2:
        print("usage: python -m src.ocr <image path>")
        return 1

    text = image_to_text(argv[1])
    print(f"extracted: {text!r}\n")

    from .predict import predict

    print(predict(text).describe())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
