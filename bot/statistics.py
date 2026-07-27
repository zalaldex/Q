"""
Statistics helpers for aggregation and reporting.

Exports:
- async get_overview(db_path=None) -> dict
    Returns total_messages, unique_users, active_users_7d, active_users_30d
- async messages_per_day(days=30, db_path=None) -> List[Tuple[str,int]]
    Returns list of (day_iso, count) for the past `days` days (only days with messages)
- async top_users(limit=10, db_path=None) -> List[Tuple[int,int]]
    Returns list of (user_id, message_count) ordered by count desc

These functions are defensive: if the expected tables are missing they return zeros/empty lists
and log warnings instead of raising, so callers can show graceful UI messages.
"""
from __future__ import annotations

import aiosqlite
from typing import List, Tuple, Dict

from .logger import get_logger
from .constants import DB_PATH

LOG = get_logger(__name__)


async def _get_conn(db_path: str | None) -> aiosqlite.Connection:
    path = db_path or DB_PATH
    conn = await aiosqlite.connect(path)
    conn.row_factory = aiosqlite.Row
    return conn


async def get_overview(db_path: str | None = None) -> Dict[str, int]:
    """Return a dict with total_messages, unique_users, active_users_7d, active_users_30d."""
    try:
        conn = await _get_conn(db_path)
    except Exception:
        LOG.exception("Failed to open DB for statistics")
        return {
            "total_messages": 0,
            "unique_users": 0,
            "active_users_7d": 0,
            "active_users_30d": 0,
        }

    try:
        async with conn:
            cur = await conn.execute("SELECT COUNT(*) as c FROM messages;")
            row = await cur.fetchone()
            total = row["c"] if row else 0

            cur = await conn.execute("SELECT COUNT(DISTINCT user_id) as c FROM messages WHERE user_id IS NOT NULL;")
            row = await cur.fetchone()
            unique = row["c"] if row else 0

            cur = await conn.execute("SELECT COUNT(DISTINCT user_id) as c FROM messages WHERE user_id IS NOT NULL AND date >= datetime('now', '-7 days');")
            row = await cur.fetchone()
            active7 = row["c"] if row else 0

            cur = await conn.execute("SELECT COUNT(DISTINCT user_id) as c FROM messages WHERE user_id IS NOT NULL AND date >= datetime('now', '-30 days');")
            row = await cur.fetchone()
            active30 = row["c"] if row else 0

            return {
                "total_messages": int(total),
                "unique_users": int(unique),
                "active_users_7d": int(active7),
                "active_users_30d": int(active30),
            }
    except Exception:
        LOG.exception("Failed to query statistics")
        return {"total_messages": 0, "unique_users": 0, "active_users_7d": 0, "active_users_30d": 0}


async def messages_per_day(days: int = 30, db_path: str | None = None) -> List[Tuple[str, int]]:
    """Return list of (YYYY-MM-DD, count) for days with messages in the past `days` days."""
    try:
        conn = await _get_conn(db_path)
    except Exception:
        LOG.exception("Failed to open DB for messages_per_day")
        return []

    try:
        async with conn:
            cur = await conn.execute(
                """
                SELECT substr(date, 1, 10) as day, COUNT(*) as cnt
                FROM messages
                WHERE date >= datetime('now', ?)
                GROUP BY day
                ORDER BY day ASC;
                """,
                (f"-{days} days",),
            )
            rows = await cur.fetchall()
            return [(r["day"], int(r["cnt"])) for r in rows]
    except Exception:
        LOG.exception("Failed to query messages per day")
        return []


async def top_users(limit: int = 10, db_path: str | None = None) -> List[Tuple[int, int]]:
    """Return list of (user_id, message_count) ordered by message_count desc."""
    try:
        conn = await _get_conn(db_path)
    except Exception:
        LOG.exception("Failed to open DB for top_users")
        return []

    try:
        async with conn:
            cur = await conn.execute(
                "SELECT user_id, COUNT(*) as cnt FROM messages WHERE user_id IS NOT NULL GROUP BY user_id ORDER BY cnt DESC LIMIT ?;",
                (limit,),
            )
            rows = await cur.fetchall()
            return [(int(r["user_id"]), int(r["cnt"])) for r in rows]
    except Exception:
        LOG.exception("Failed to query top users")
        return []
