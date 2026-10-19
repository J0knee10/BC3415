"""Telegram bot — the forward-it-to-check front end.

Run with::

    python -m app.bot

with ``TELEGRAM_BOT_TOKEN`` set in ``.env`` (see ``.env.example``) or in the
shell. Get a token from @BotFather in Telegram. The bot runs on a laptop with no
approval process and no registered phone number, which is why it is the demo
channel rather than WhatsApp — WhatsApp is end-to-end encrypted with no read
API, so a bot there would need a Meta Business account and still only see
messages forwarded to it. The interaction is identical either way: the user
forwards a suspicious message, the bot answers.

Privacy: message bodies are never written to a log. Only the verdict label and
a length are recorded, which is enough to debug and to chart usage without
retaining anyone's personal messages.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import tempfile
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src import ocr, scam_type
from src.config import CFG
from src.predict import load_model

# Message bodies are deliberately absent from this format string.
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO
)
log = logging.getLogger("smishing-bot")
# httpx logs every request URL at INFO, and Telegram's API puts the bot token
# in the URL. Keep it out of the console and any log file.
logging.getLogger("httpx").setLevel(logging.WARNING)

WELCOME = (
    "👋 *Smishing Triage*\n\n"
    "Forward me a suspicious SMS or WhatsApp message — or a screenshot of one — "
    "and I'll tell you whether it shows signs of a scam, looks like marketing "
    "spam, or shows no scam signals, and which words made me think so.\n\n"
    "I never store your messages."
)

NO_TEXT = (
    "I couldn't read any text in that image. Try a clearer screenshot, or "
    "paste the message as text."
)


async def cmd_start(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(WELCOME, parse_mode="Markdown")


async def _respond(update: Update, message: str) -> None:
    """Classify a message and reply with the verdict.

    The trained model decides; the LLM stage only names a scam type, and only
    when the model already said smishing (the gate lives in ``scam_type``).
    The model, LIME and the Gemini call are blocking, so they run in a worker
    thread rather than stalling every other chat while one is classified.
    """
    await update.effective_message.chat.send_action("typing")
    prediction, scam = await asyncio.to_thread(scam_type.enrich, message)

    log.info(
        "classified len=%d label=%s conf=%.2f enriched=%s",
        len(message),
        prediction.label,
        prediction.confidence,
        scam is not None,
    )

    await update.effective_message.reply_text(scam_type.describe(prediction, scam))


async def on_text(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await _respond(update, update.effective_message.text)


async def on_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Screenshot path: OCR the image, add any caption, then the same classifier.

    A forwarded message can carry both an image and text (the caption), and
    the scam may sit in either. Both are classified together; if the image
    has no readable text, or OCR is unavailable, the caption alone is used.
    """
    msg = update.effective_message
    caption = (msg.caption or "").strip()
    image_text = ""

    if ocr.tesseract_available():
        await msg.chat.send_action("typing")
        # Highest resolution Telegram offers; OCR quality depends on it.
        photo = await ctx.bot.get_file(msg.photo[-1].file_id)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "shot.jpg"
            await photo.download_to_drive(path)
            try:
                image_text = await asyncio.to_thread(ocr.image_to_text, path)
            except RuntimeError:
                image_text = ""
    elif not caption:
        await msg.reply_text(
            "Screenshot reading is unavailable on this server — "
            "paste the message as text instead."
        )
        return

    if not image_text and not caption:
        await msg.reply_text(NO_TEXT)
        return

    if image_text:
        await msg.reply_text(f'I read from the image: "{image_text}"')
    text = "\n".join(t for t in [caption, image_text] if t)
    await _respond(update, text)


def main() -> int:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print(
            "TELEGRAM_BOT_TOKEN is not set.\n"
            "Create a bot with @BotFather in Telegram, then put the token in\n"
            ".env at the project root (copy .env.example):\n"
            "  TELEGRAM_BOT_TOKEN=...",
            file=sys.stderr,
        )
        return 1

    # Fail fast on a missing model rather than on the first message.
    load_model()

    if not scam_type.available():
        log.warning(
            "GEMINI_API_KEY not set — scam-type enrichment disabled, "
            "the classifier still runs"
        )
    else:
        log.info("scam-type enrichment on — model %s", scam_type.MODEL)

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))

    log.info("bot running — labels: %s", ", ".join(CFG.labels))
    app.run_polling()
    return 0


if __name__ == "__main__":
    sys.exit(main())
