"""
Command handlers: /start, /backup, /restore, /settings

Exports:
- register_command_handlers(app)

This module uses python-telegram-bot style Application for handler registration.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from telegram import InputFile
from telegram.ext import CommandHandler, Application

from bot.logger import get_logger
from bot.backup import create_backup_from_db
from bot.settings import get_settings_db
from bot.constants import BACKUP_DIR, BACKUP_FILENAME

LOG = get_logger(__name__)


async def cmd_start(update, context) -> None:  # type: ignore[override]
    text = (
        "Hello! I'm the monospace bot. Send me text and I'll return a monospace-formatted "
        "version. Use /backup to export the DB and /restore to restore from a backup."
    )
    await update.message.reply_text(text)


async def cmd_backup(update, context) -> None:  # type: ignore[override]
    await update.message.reply_text("Preparing backup...")
    # Create backup file (call async create_backup_from_db)
    try:
        out_path = await create_backup_from_db()
    except Exception:
        LOG.exception("Backup generation failed")
        await update.message.reply_text("Backup failed")
        return

    p = Path(out_path)
    if p.exists():
        await update.message.reply_document(document=InputFile(str(p)), filename=p.name)
    else:
        await update.message.reply_text("Backup failed: file not found")


async def cmd_restore(update, context) -> None:  # type: ignore[override]
    await update.message.reply_text(
        "To restore, upload a Conversation.txt backup file as a document and run /do_restore in reply to it."
    )


async def cmd_settings(update, context) -> None:  # type: ignore[override]
    settings = await get_settings_db()
    if not settings:
        await update.message.reply_text("No settings configured.")
        return
    lines = [f"{k}: {v}" for k, v in settings.items()]
    await update.message.reply_text("\n".join(lines))


def register_command_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("backup", cmd_backup))
    app.add_handler(CommandHandler("restore", cmd_restore))
    app.add_handler(CommandHandler("settings", cmd_settings))


__all__ = ["register_command_handlers", "cmd_start", "cmd_backup", "cmd_restore", "cmd_settings"]
