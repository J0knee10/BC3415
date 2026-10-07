"""Telegram bot — the forward-it-to-check front end.

Run with::

    TELEGRAM_BOT_TOKEN=... python -m app.bot

Get a token from @BotFather in Telegram. The bot runs on a laptop with no
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
from src.predict import load_model, predict

# Message bodies are deliberately absent from this format string.
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO
)
log = logging.getLogger("smishing-bot")

WELCOME = (
    "👋 *Smishing Triage*\n\n"
    "Forward me a suspicious SMS or WhatsApp message — or a screenshot of one — "
    "and I'll tell you whether it looks legitimate, like marketing spam, or "
    "like a scam, and which words made me think so.\n\n"
    "I never store your messages."
)

NO_TEXT = (
    "I couldn't read any text in that image. Try a clearer screenshot, or "
    "paste the message as text."
)


async def cmd_start(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME, parse_mode="Markdown")


async def _respond(update: Update, message: str) -> None:
    """Classify a message and reply with the verdict.

    The trained model decides; the LLM stage only names a scam type, and only
    when the model already said smishing (the gate lives in ``scam_type``).
    """
    prediction, scam = scam_type.enrich(message)

    log.info(
        "classified len=%d label=%s conf=%.2f enriched=%s",
        len(message),
        prediction.label,
        prediction.confidence,
        scam is not None,
    )

    await update.message.reply_text(scam_type.describe(prediction, scam))


async def on_text(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await _respond(update, update.message.text)


async def on_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Screenshot path: download, OCR, then the same classifier."""
    if not ocr.tesseract_available():
        await update.message.reply_text(
            "Screenshot reading is unavailable on this server — "
            "paste the message as text instead."
        )
        return

    await update.message.chat.send_action("typing")

    # Highest resolution Telegram offers; OCR quality depends on it.
    photo = await ctx.bot.get_file(update.message.photo[-1].file_id)

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "shot.jpg"
        await photo.download_to_drive(path)
        try:
            text = ocr.image_to_text(path)
        except RuntimeError as exc:
            await update.message.reply_text(str(exc))
            return

    if not text:
        await update.message.reply_text(NO_TEXT)
        return

    await update.message.reply_text(f'I read: "{text}"')
    await _respond(update, text)


def main() -> int:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print(
            "TELEGRAM_BOT_TOKEN is not set.\n"
            "Create a bot with @BotFather in Telegram, then:\n"
            "  export TELEGRAM_BOT_TOKEN=...   (bash)\n"
            '  $env:TELEGRAM_BOT_TOKEN="..."   (PowerShell)',
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
