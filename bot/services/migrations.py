"""
Database migration runner and migration definitions.

Exports:
- async apply_migrations(db_path=None)

The migrations are incremental SQL statements applied in order and tracked in
an _migrations table.
"""
from __future__ import annotations

import aiosqlite
from typing import List, Tuple

from ..logger import get_logger
from ..constants import DB_PATH

LOG = get_logger(__name__)

MIGRATIONS: List[Tuple[str, str]] = [
    (
        "001_initial",
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            user_id INTEGER,
            text TEXT,
            message_type TEXT
        );
        CREATE TABLE IF NOT EXISTS media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            file_unique_id TEXT,
            file_name TEXT,
            mime_type TEXT,
            local_path TEXT,
            FOREIGN KEY(message_id) REFERENCES messages(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS _migrations (
            id TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        );
        """,
    ),
]


async def _ensure_migrations_table(conn: aiosqlite.Connection) -> None:
    await conn.execute(
        "CREATE TABLE IF NOT EXISTS _migrations (id TEXT PRIMARY KEY, applied_at TEXT NOT NULL);"
    )
    await conn.commit()


async def apply_migrations(db_path: str | None = None) -> None:
    path = db_path or DB_PATH
    async with aiosqlite.connect(path) as conn:
        await _ensure_migrations_table(conn)
        for mid, sql in MIGRATIONS:
            cur = await conn.execute("SELECT 1 FROM _migrations WHERE id = ?", (mid,))
            row = await cur.fetchone()
            if row:
                LOG.debug("Migration %s already applied", mid)
                continue
            LOG.info("Applying migration %s", mid)
            await conn.executescript(sql)
            await conn.execute("INSERT INTO _migrations (id, applied_at) VALUES (?, datetime('now'))", (mid,))
            await conn.commit()


__all__ = ["apply_migrations", "MIGRATIONS"]
