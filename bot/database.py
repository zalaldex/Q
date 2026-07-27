"""
Async SQLite helper and migration utilities using aiosqlite.

Exports:
- get_db(): async context manager yielding an aiosqlite.Connection with pragmas applied
- open_db_connection(): low-level connection factory
- ensure_migrations_table(conn): create a table to track applied migrations
- get_applied_migrations(conn) -> set[str]
- mark_migration_applied(conn, name)
- execute_script(conn, sql): executes multi-statement SQL safely

This module purposefully avoids importing the migrations runner to prevent circular imports.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Optional, Set

import aiosqlite

from .constants import DB_DIR, DB_PATH, SQLITE_PRAGMAS, DEFAULT_DB_TIMEOUT_SECONDS
from .logger import get_logger

LOG = get_logger(__name__)


def _ensure_db_dir() -> None:
    Path(DB_DIR).mkdir(parents=True, exist_ok=True)


async def open_db_connection(timeout: Optional[float] = None) -> aiosqlite.Connection:
    """
    Open and return an aiosqlite connection with recommended pragmas set.

    Caller is responsible for closing the connection.
    """
    _ensure_db_dir()
    timeout = timeout or DEFAULT_DB_TIMEOUT_SECONDS
    conn = await aiosqlite.connect(DB_PATH, timeout=timeout)
    # Return rows as dict-like objects
    conn.row_factory = aiosqlite.Row

    # Apply pragmas recommended in constants. Use immediate execution so they are set per-connection.
    async with conn.execute("PRAGMA foreign_keys = ON;"):
        pass

    # Apply configured pragmas (journal_mode, synchronous, etc.)
    for key, value in SQLITE_PRAGMAS:
        # journal_mode is a special pragma that returns a result when set; execute and ignore its result
        try:
            await conn.execute(f"PRAGMA {key}={value};")
        except Exception:
            # Fallback to quoted value if previous form failed (e.g., strings)
            await conn.execute(f"PRAGMA {key}='{value}';")

    # Ensure WAL mode committed
    try:
        await conn.commit()
    except Exception:
        LOG.debug("Commit after pragmas failed (already closed?).", exc_info=True)

    return conn


@asynccontextmanager
async def get_db(timeout: Optional[float] = None) -> AsyncIterator[aiosqlite.Connection]:
    """Async context manager yielding a ready-to-use DB connection.

    Example:
        async with get_db() as conn:
            await conn.execute(...)
    """
    conn = await open_db_connection(timeout=timeout)
    try:
        yield conn
n    finally:
        try:
            await conn.close()
        except Exception:
            LOG.debug("Error while closing DB connection", exc_info=True)


async def execute_script(conn: aiosqlite.Connection, sql: str) -> None:
    """Execute a multi-statement SQL script inside a transaction."""
    # aiosqlite supports executescript which handles multiple statements.
    try:
        await conn.executescript(sql)
        await conn.commit()
    except Exception:
        await conn.rollback()
        LOG.exception("Failed to execute SQL script")
        raise


async def ensure_migrations_table(conn: aiosqlite.Connection) -> None:
    """Create the migrations table if it doesn't exist. Idempotent."""
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS __migrations_applied (
            name TEXT PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
        );
        """
    )
    await conn.commit()


async def get_applied_migrations(conn: aiosqlite.Connection) -> Set[str]:
    await ensure_migrations_table(conn)
    cur = await conn.execute("SELECT name FROM __migrations_applied")
    rows = await cur.fetchall()
    return {row[0] for row in rows}


async def mark_migration_applied(conn: aiosqlite.Connection, name: str) -> None:
    await conn.execute(
        "INSERT OR REPLACE INTO __migrations_applied (name) VALUES (?);", (name,)
    )
    await conn.commit()


# Convenience synchronous wrapper for simple scripts from outside async context
def run_sync(coro):
    """Run an async coroutine from sync code, creating and tearing down an event loop.

    Note: Use sparingly. Intended for small administrative scripts.
    """
    return asyncio.get_event_loop().run_until_complete(coro)
