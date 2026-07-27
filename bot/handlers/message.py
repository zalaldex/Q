"""
Message handlers registration and implementation.

Provides:
- async handle_message(update, context)
- register_message_handlers(app)

The handler transforms incoming text messages to monospace HTML, then sends them
using the sender helper. It also reads settings for mode/shrink.
"""
from __future__ import annotations

from telegram.ext import MessageHandler, filters, Application
from telegram import Update
from telegram.ext import ContextTypes

from bot.logger import get_logger
from bot.monospace import transform_text_to_monospace
from bot.settings import get_settings_db
from bot.sender import send_transformed

LOG = get_logger(__name__)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    text = update.message.text
    chat_id = update.effective_chat.id if update.effective_chat else None

    # Read settings to determine mode and shrink option
    settings = await get_settings_db()
    mode = settings.get("mode")
    shrink = settings.get("shrink", False)

    try:
        html = transform_text_to_monospace(text, mode=mode, shrink=shrink)
    except Exception:
        LOG.exception("Transformation failed")
        await update.message.reply_text("Failed to transform message")
        return

    # Send transformed text (no media)
    try:
        await send_transformed(context.bot, chat_id, html, media_paths=None)
    except Exception:
        LOG.exception("Failed to send transformed message")
        await update.message.reply_text("Failed to send transformed message")


def register_message_handlers(app: Application) -> None:
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))


__all__ = ["register_message_handlers", "handle_message"]
