"""
Settings storage helpers. Provides a small DB-backed key/value store for
application settings with JSON-encoded values and convenience accessors.

Exports:
- async ensure_settings_table(conn)
- async get_setting(conn, key, default=None) -> Any
- async set_setting(conn, key, value) -> None
- async get_all_settings(conn) -> dict
- async get_settings_db(db_path=None) -> dict  # convenience wrapper that opens a connection
- async set_setting_db(key, value, db_path=None) -> None  # convenience wrapper that opens a connection
- async apply_default_settings(defaults: dict, db_path=None) -> None

The module stores settings as JSON text to allow structured values (e.g., mode and shrink).
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

import aiosqlite

from .constants import DB_PATH
from .logger import get_logger

LOG = get_logger(__name__)


async def ensure_settings_table(conn: aiosqlite.Connection) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )
    await conn.commit()


async def get_setting(conn: aiosqlite.Connection, key: str, default: Any = None) -> Any:
    await ensure_settings_table(conn)
    cur = await conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = await cur.fetchone()
    if not row:
        return default
    try:
        return json.loads(row[0])
    except Exception:
        # Fall back to raw string if JSON decode fails
        return row[0]


async def set_setting(conn: aiosqlite.Connection, key: str, value: Any) -> None:
    await ensure_settings_table(conn)
    text = json.dumps(value)
    await conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, text))
    await conn.commit()


async def get_all_settings(conn: aiosqlite.Connection) -> Dict[str, Any]:
    await ensure_settings_table(conn)
    cur = await conn.execute("SELECT key, value FROM settings")
    rows = await cur.fetchall()
    out: Dict[str, Any] = {}
    for r in rows:
        key = r[0]
        try:
            out[key] = json.loads(r[1])
        except Exception:
            out[key] = r[1]
    return out


# Convenience wrappers that open the DB themselves
async def get_settings_db(db_path: Optional[str] = None) -> Dict[str, Any]:
    path = db_path or DB_PATH
    try:
        conn = await aiosqlite.connect(path)
    except Exception:
        LOG.exception("Failed to open DB for get_settings_db")
        return {}
    async with conn:
        return await get_all_settings(conn)


async def set_setting_db(key: str, value: Any, db_path: Optional[str] = None) -> None:
    path = db_path or DB_PATH
    try:
        conn = await aiosqlite.connect(path)
    except Exception:
        LOG.exception("Failed to open DB for set_setting_db")
        return
    async with conn:
        await set_setting(conn, key, value)


async def apply_default_settings(defaults: Dict[str, Any], db_path: Optional[str] = None) -> None:
    """Write default values for keys that are not present in the DB yet."""
    path = db_path or DB_PATH
    try:
        conn = await aiosqlite.connect(path)
    except Exception:
        LOG.exception("Failed to open DB for apply_default_settings")
        return
    async with conn:
        await ensure_settings_table(conn)
        for k, v in defaults.items():
            cur = await conn.execute("SELECT 1 FROM settings WHERE key = ?", (k,))
            row = await cur.fetchone()
            if not row:
                await set_setting(conn, k, v)


__all__ = [
    "ensure_settings_table",
    "get_setting",
    "set_setting",
    "get_all_settings",
    "get_settings_db",
    "set_setting_db",
    "apply_default_settings",
]
