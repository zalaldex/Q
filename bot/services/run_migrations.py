"""
Adapter shims for migration runner compatibility.

This module provides `run_migrations` as a thin wrapper around `apply_migrations` so
external callers (e.g., run.py) can use the `run_migrations` name.
"""
from __future__ import annotations

from .migrations import apply_migrations


async def run_migrations(db_path: str | None = None) -> None:
    await apply_migrations(db_path)


__all__ = ["run_migrations"]
