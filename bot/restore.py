"""
Restore utilities to read Conversation.txt backups and re-ingest messages and
embedded media into the local database and media cache.

Primary export:
- async restore_from_backup(path, *, db_path=None, bot=None)

Behavior:
- Parses the simple text format created by bot/backup.py
- Writes embedded base64 media blocks to MEDIA_DIR (avoids overwriting existing files by
  appending numeric suffixes when necessary)
- Inserts (or replaces) rows into `messages` and `media` tables. If tables are missing,
  they are created with a simple defensive schema compatible with the exporter.

This routine is intentionally best-effort: if a part of the backup cannot be parsed or a
media file fails to write, the function logs a warning and continues processing the rest
of the backup.
"""
from __future__ import annotations

import base64
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import aiosqlite

from .constants import (
    BACKUP_DIR,
    BACKUP_FILENAME,
    BACKUP_MEDIA_MARKER_PREFIX,
    BACKUP_MEDIA_MARKER_SUFFIX,
    MEDIA_DIR,
)
from .logger import get_logger
from .models import MessageModel, MediaModel
from .media import cached_path_for
from .utils import ensure_dirs

LOG = get_logger(__name__)

_MARKER_RE = re.compile(r'===MEDIA BASE64\s+filename="(?P<filename>[^"]+)"(?:\s+mime="(?P<mime>[^"]+)")?')


def _unique_path(dest: Path) -> Path:
    """Return a Path that does not overwrite existing files by appending suffixes."""
    if not dest.exists():
        return dest
    stem = dest.stem
    suffix = dest.suffix
    i = 1
    while True:
        candidate = dest.with_name(f"{stem}-{i}{suffix}")
        if not candidate.exists():
            return candidate
        i += 1


def _parse_backup(path: str) -> List[Tuple[dict, List[Tuple[str, str, str]]]]:
    """Parse the backup file and return a list of (message_dict, list_of_media).

    message_dict: contains keys id, date, user, type, text
    list_of_media: list of tuples (filename, mime, local_written_path)

    We don't write media here; this parser only extracts structured blocks.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Backup file not found: {path}")

    blocks: List[Tuple[dict, List[Tuple[str, str, str]]]] = []

    with open(p, "r", encoding="utf-8") as f:
        lines = f.readlines()

    i = 0
    cur_msg = None
    cur_media: List[Tuple[str, str, str]] = []

    while i < len(lines):
        line = lines[i].rstrip("\n")
        if line.strip() == "===MESSAGE===":
            # flush previous if present
            if cur_msg is not None:
                blocks.append((cur_msg, cur_media))
                cur_media = []
            cur_msg = {"text": ""}
            i += 1
            # read message metadata lines until a blank line or next marker
            while i < len(lines):
                l = lines[i].rstrip("\n")
                if l.strip() == "":
                    i += 1
                    break
                # key: value
                if l.startswith("text:"):
                    # rest of file until blank line or media marker is the text
                    # text block may span multiple lines
                    # Consume next lines until a blank line or media marker or ===MESSAGE===
                    i += 1
                    text_lines = []
                    while i < len(lines):
                        nl = lines[i]
                        if nl.strip() == "":
                            i += 1
                            break
                        if nl.startswith(BACKUP_MEDIA_MARKER_PREFIX) or nl.startswith("===MESSAGE==="):
                            break
                        text_lines.append(nl.rstrip("\n"))
                        i += 1
                    cur_msg["text"] = "\n".join(text_lines)
                    continue
                # parse simple key: value
                if ":" in l:
                    k, v = l.split(":", 1)
                    cur_msg[k.strip()] = v.strip()
                i += 1
            continue

        if line.startswith(BACKUP_MEDIA_MARKER_PREFIX):
            # parse filename and mime if present
            m = _MARKER_RE.match(line)
            if not m:
                # Try a looser parse (older format)
                fname = line[len(BACKUP_MEDIA_MARKER_PREFIX) :].strip()
                mime = None
            else:
                fname = m.group("filename")
                mime = m.group("mime")
            # Read base64 lines until suffix
            i += 1
            b64_lines = []
            while i < len(lines):
                l = lines[i].rstrip("\n")
                if l.strip() == BACKUP_MEDIA_MARKER_SUFFIX:
                    i += 1
                    break
                b64_lines.append(l)
                i += 1
            b64 = "".join(b64_lines)
            cur_media.append((fname, mime or "application/octet-stream", b64))
            continue

        # otherwise skip
        i += 1

    # flush last
    if cur_msg is not None:
        blocks.append((cur_msg, cur_media))

    return blocks


async def _ensure_schema(conn: aiosqlite.Connection) -> None:
    """Create messages and media tables if they don't exist (defensive)."""
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY,
            date TEXT NOT NULL,
            user_id INTEGER,
            text TEXT,
            message_type TEXT
        );
        """
    )
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            file_unique_id TEXT,
            file_name TEXT,
            mime_type TEXT,
            local_path TEXT,
            FOREIGN KEY(message_id) REFERENCES messages(id) ON DELETE CASCADE
        );
        """
    )
    await conn.commit()


async def restore_from_backup(path: Optional[str] = None, *, db_path: Optional[str] = None) -> Tuple[int, int]:
    """Restore messages and embedded media from a backup file into the DB and media cache.

    Returns (messages_imported, media_imported)
    """
    ensure_dirs(BACKUP_DIR, MEDIA_DIR)
    path = path or str(Path(BACKUP_DIR) / BACKUP_FILENAME)

    blocks = _parse_backup(path)

    msg_count = 0
    media_count = 0

    # Determine DB path
    conn_path = db_path or None
    if conn_path is None:
        from .constants import DB_PATH as _DB_PATH

        conn_path = _DB_PATH

    async with aiosqlite.connect(conn_path) as conn:
        conn.row_factory = aiosqlite.Row
        await _ensure_schema(conn)

        for msg_dict, medias in blocks:
            try:
                mid = int(msg_dict.get("id") or 0)
            except Exception:
                mid = None
            date_raw = msg_dict.get("date")
            try:
                date = datetime.fromisoformat(date_raw) if date_raw else datetime.utcnow()
            except Exception:
                date = datetime.utcnow()

            user_val = msg_dict.get("user")
            user_id = None
            try:
                # user field may be json or a numeric id
                if user_val:
                    parsed = json.loads(user_val)
                    if isinstance(parsed, dict) and parsed.get("id"):
                        user_id = int(parsed.get("id"))
                    elif isinstance(parsed, int):
                        user_id = parsed
            except Exception:
                try:
                    user_id = int(user_val)
                except Exception:
                    user_id = None

            text = msg_dict.get("text")
            mtype = msg_dict.get("type")

            # Insert or replace message (id if available)
            if mid:
                await conn.execute(
                    "INSERT OR REPLACE INTO messages (id, date, user_id, text, message_type) VALUES (?, ?, ?, ?, ?)",
                    (mid, date.isoformat(), user_id, text, mtype),
                )
            else:
                cur = await conn.execute(
                    "INSERT INTO messages (date, user_id, text, message_type) VALUES (?, ?, ?, ?)",
                    (date.isoformat(), user_id, text, mtype),
                )
                mid = cur.lastrowid
            await conn.commit()
            msg_count += 1

            # Handle media blocks: decode base64 and write to cache, then insert into media table
            for fname, mime, b64 in medias:
                try:
                    data = base64.b64decode(b64)
                except Exception:
                    LOG.exception("Failed to decode base64 for media %s on message %s", fname, mid)
                    continue
                # Determine a safe path
                dest = Path(MEDIA_DIR) / fname
                dest = _unique_path(dest)
                try:
                    with open(dest, "wb") as fh:
                        fh.write(data)
                except Exception:
                    LOG.exception("Failed to write media file %s", dest)
                    continue
                # Try to extract a file_unique_id from filename if present (pattern: <unique>_<name>)
                fu = None
                if "_" in dest.name:
                    maybe = dest.name.split("_", 1)[0]
                    if maybe.isalnum():
                        fu = maybe
                await conn.execute(
                    "INSERT INTO media (message_id, file_unique_id, file_name, mime_type, local_path) VALUES (?, ?, ?, ?, ?)",
                    (mid, fu, dest.name, mime, str(dest)),
                )
                await conn.commit()
                media_count += 1

    LOG.info("Restore complete: %d messages, %d media imported", msg_count, media_count)
    return msg_count, media_count


__all__ = ["restore_from_backup"]
