"""
Backup utilities to export conversations to a single text file with embedded
base64-encoded media blocks. The format is deliberately simple and human
readable so backups can be inspected or edited.

Exports
- create_backup_from_messages(messages, out_path)
- create_backup_from_db(out_path, *, db_timeout_seconds=None)

Format (simple):

===MESSAGE===
id: <id>
date: <ISO8601>
user: <json-encoded user object>
type: <message_type>
text:
<text block>

===MEDIA_BASE64 filename="..." mime="..."===
<base64 data>
===END MEDIA===

Each message block is separated by a single blank line.

This module is defensive: if the expected DB schema is not present it will
log a warning and write whatever it can. The DB export routine will attempt
to read `messages` and `media` tables if present.
"""
from __future__ import annotations

import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

import aiosqlite

from .constants import BACKUP_DIR, BACKUP_FILENAME, BACKUP_MEDIA_MARKER_PREFIX, BACKUP_MEDIA_MARKER_SUFFIX
from .logger import get_logger
from .models import MessageModel, MediaModel, UserModel
from .media import cached_path_for
from .utils import ensure_dirs

LOG = get_logger(__name__)


def _media_marker_start(filename: str, mime: Optional[str] = None) -> str:
    if mime:
        return f"{BACKUP_MEDIA_MARKER_PREFIX} filename=\"{filename}\" mime=\"{mime}\""
    return f"{BACKUP_MEDIA_MARKER_PREFIX} filename=\"{filename}\""


def _write_media_block(f, media_path: str, filename: str, mime: Optional[str] = None) -> None:
    # Read binary and write base64 block
    with open(media_path, "rb") as fh:
        data = fh.read()
    b64 = base64.b64encode(data).decode("ascii")

    f.write(_media_marker_start(filename, mime) + "\n")
    # Write base64 with 76-char lines for readability
    for i in range(0, len(b64), 76):
        f.write(b64[i : i + 76] + "\n")
    f.write(BACKUP_MEDIA_MARKER_SUFFIX + "\n")


def _format_message_block(msg: MessageModel) -> str:
    lines: List[str] = []
    lines.append("===MESSAGE===")
    lines.append(f"id: {msg.id}")
    iso = msg.date.isoformat() if hasattr(msg.date, "isoformat") else str(msg.date)
    lines.append(f"date: {iso}")
    # user as json
    try:
        user_json = json.dumps(msg.user_id if not getattr(msg, 'user', None) else msg.user.dict())
    except Exception:
        user_json = json.dumps({"id": msg.user_id})
    lines.append(f"user: {user_json}")
    lines.append(f"type: {msg.message_type}")
    lines.append("text:")
    lines.append(msg.text or "")
    return "\n".join(lines)


def create_backup_from_messages(messages: Iterable[MessageModel], out_path: Optional[str] = None) -> str:
    """Create a backup file from an iterable of MessageModel objects.

    Returns the path to the created backup file.
    """
    ensure_dirs(BACKUP_DIR)
    out_path = out_path or str(Path(BACKUP_DIR) / BACKUP_FILENAME)
    p = Path(out_path)

    with open(p, "w", encoding="utf-8") as f:
        for msg in messages:
            block = _format_message_block(msg)
            f.write(block + "\n\n")
            # Write associated media if present
            if getattr(msg, "media", None):
                for m in msg.media:
                    # Determine cached path for media if file_unique_id present
                    try:
                        media_path = cached_path_for(getattr(m, "file_unique_id", None), getattr(m, "file_name", None))
                        if Path(media_path).exists():
                            _write_media_block(f, media_path, getattr(m, "file_name", m.file_id), getattr(m, "mime_type", None))
                        else:
                            LOG.warning("Media file for message %s not found in cache: %s", msg.id, media_path)
                    except Exception:
                        LOG.exception("Failed to write media block for message %s", msg.id)
            f.write("\n")
    LOG.info("Backup written to %s", str(p))
    return str(p)


async def create_backup_from_db(out_path: Optional[str] = None, *, db_path: Optional[str] = None) -> str:
    """Create a backup by reading messages from the database.

    This function expects a `messages` table with columns (id, date, user_id, text, message_type)
    and a `media` table with columns (message_id, file_unique_id, file_name, mime_type).
    If these tables are absent the function will log a warning and write an empty backup.
    """
    ensure_dirs(BACKUP_DIR)
    out_path = out_path or str(Path(BACKUP_DIR) / BACKUP_FILENAME)
    db_path = db_path or None

    messages: List[MessageModel] = []
    try:
        # Use aiosqlite directly to avoid import cycles with database helper
        conn_path = db_path or None
        if conn_path is None:
            # default DB location from constants if not provided
            from .constants import DB_PATH as _DB_PATH

            conn_path = _DB_PATH
        async with aiosqlite.connect(conn_path) as conn:
            conn.row_factory = aiosqlite.Row
            # Minimal defensive query; catch if table missing
            try:
                cur = await conn.execute("SELECT id, date, user_id, text, message_type FROM messages ORDER BY date ASC;")
                rows = await cur.fetchall()
                for r in rows:
                    # Parse date permissively
                    try:
                        date = datetime.fromisoformat(r["date"]) if isinstance(r["date"], str) else r["date"]
                    except Exception:
                        date = datetime.utcnow()
                    # Attempt to load media for this message
                    media_list = []
                    try:
                        mcur = await conn.execute("SELECT file_unique_id, file_name, mime_type FROM media WHERE message_id = ?", (r["id"],))
                        mrows = await mcur.fetchall()
                        for mr in mrows:
                            media_list.append(MediaModel(file_id=mr["file_unique_id"] or mr["file_name"], file_unique_id=mr["file_unique_id"], file_name=mr["file_name"], mime_type=mr["mime_type"]))
                    except Exception:
                        # No media table or other error — continue without media
                        media_list = []
                    msg = MessageModel(id=r["id"], telegram_message_id=None, chat_id=None, user_id=r["user_id"], text=r["text"], message_type=r["message_type"], date=date, media=media_list)
                    messages.append(msg)
            except Exception:
                LOG.exception("Unable to query messages table from DB; writing empty backup")
                messages = []
    except Exception:
        LOG.exception("Failed opening DB for backup. Writing empty backup at %s", out_path)
        messages = []

    # Delegate to create_backup_from_messages for file writing
    return create_backup_from_messages(messages, out_path)


__all__ = ["create_backup_from_messages", "create_backup_from_db"]
