"""
Persistence helpers: save incoming messages and record sent messages.

Functions are best-effort: failures are logged but do not interrupt message flow.
"""
from __future__ import annotations

import json
from typing import Optional, Iterable, List

from .database import get_db
from .logger import get_logger
from .media import download_and_cache

LOG = get_logger(__name__)


async def save_incoming_message(update) -> Optional[int]:
    """Persist the incoming Telegram update to the messages/media tables.

    Returns the inserted local message id, or None on failure.
    """
    try:
        message = update.message
        if not message:
            return None

        async with get_db() as conn:
            # Insert message row
            date = message.date.isoformat() if hasattr(message, "date") else None
            user_id = getattr(message.from_user, "id", None) if message.from_user else None
            text = message.text or message.caption or None
            msg_type = "text"
            if message.photo or message.document or message.voice or message.video:
                msg_type = "media"

            cur = await conn.execute(
                "INSERT INTO messages (date, user_id, text, message_type) VALUES (?, ?, ?, ?);",
                (date, user_id, text, msg_type),
            )
            await conn.commit()
            rowid = cur.lastrowid

            # If media present, download/cache and insert into media table
            media_items = []
            if message.photo:
                # message.photo is a list of sizes, pick the largest
                file_id = message.photo[-1].file_id
                media_items.append((file_id, getattr(message.photo[-1], "file_unique_id", None), None, None))
            if message.document:
                d = message.document
                media_items.append((d.file_id, getattr(d, "file_unique_id", None), getattr(d, "file_name", None), getattr(d, "mime_type", None)))
            if message.video:
                v = message.video
                media_items.append((v.file_id, getattr(v, "file_unique_id", None), getattr(v, "file_name", None), getattr(v, "mime_type", None)))
            if message.voice:
                v = message.voice
                media_items.append((v.file_id, getattr(v, "file_unique_id", None), getattr(v, "file_name", None), getattr(v, "mime_type", None)))

            for fid, unique_id, fname, mtype in media_items:
                try:
                    local_path = await download_and_cache(update._bot, fid, file_name=fname)
                except Exception:
                    LOG.exception("Failed to download media %s", fid)
                    local_path = None
                await conn.execute(
                    "INSERT INTO media (message_id, file_unique_id, file_name, mime_type, local_path) VALUES (?, ?, ?, ?, ?);",
                    (rowid, unique_id, fname, mtype, local_path),
                )
            await conn.commit()
            return int(rowid)
    except Exception:
        LOG.exception("Failed to persist incoming message")
        return None


async def record_sent_messages(incoming_message_id: Optional[int], sent_results: Iterable[dict]) -> None:
    """Record one or more sent Telegram messages associated with an incoming message.

    sent_results: iterable of dicts with keys: telegram_message_id, chat_id, date, content
    """
    try:
        async with get_db() as conn:
            for r in sent_results:
                try:
                    await conn.execute(
                        "INSERT INTO sent_messages (incoming_message_id, telegram_message_id, chat_id, date, content) VALUES (?, ?, ?, ?, ?);",
                        (incoming_message_id, r.get("telegram_message_id"), r.get("chat_id"), r.get("date"), r.get("content")),
                    )
                except Exception:
                    LOG.exception("Failed to insert sent message record: %s", r)
            await conn.commit()
    except Exception:
        LOG.exception("Failed to record sent messages")


__all__ = ["save_incoming_message", "record_sent_messages"]
