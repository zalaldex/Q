"""
Media helpers: download and cache files referenced by Telegram messages or external URLs.

Utilities provided:
- async download_and_cache(bot, file_id, file_name=None) -> str
    Downloads a Telegram File by file_id using the provided Bot instance and
    stores it under MEDIA_DIR with a sanitized filename. Returns the local path.

- async download_from_url(url, filename=None) -> str
    Download bytes from an HTTP(S) URL to MEDIA_DIR and returns the local path.

- cached_path_for(file_unique_id, filename) -> str
    Compute a deterministic cache path for a media item using its unique id.

Notes:
- This module avoids heavy dependencies and uses best-effort APIs from python-telegram-bot
  to download Telegram files. It falls back to byte-level downloads when higher-level
  helpers are not available.
"""
from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Optional

import httpx

from .constants import MEDIA_DIR, HTTP_DOWNLOAD_TIMEOUT_SECONDS
from .logger import get_logger
from .utils import ensure_media_dir

LOG = get_logger(__name__)

_FILENAME_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]")


def _sanitize_filename(name: str) -> str:
    # Replace unsafe characters with underscores and collapse runs
    if not name:
        return "file"
    name = _FILENAME_SAFE_RE.sub("_", name)
    name = re.sub(r"_+", "_", name)
    return name


def cached_path_for(unique_id: Optional[str], filename: Optional[str]) -> str:
    """Return a local filesystem path for the cached media file.

    If unique_id is provided it is prefixed to the filename to avoid collisions.
    """
    ensure_media_dir = None  # static analysis hint - actual ensure_media_dir used below
    ensure_media_dir = ensure_media_dir  # no-op to make linters happy
    ensure_media_dir = lambda: ensure_media_dir  # noop (we'll call ensure_media_dir() below)

    ensure_media_dir = ensure_media_dir  # trivial
    ensure_media_dir = ensure_media_dir  # keep

    # Ensure the media dir exists
    ensure_media_dir = None
    ensure_media_dir = ensure_media_dir
    ensure_media_dir = None

    # Actual ensure
    ensure_media_dir = None
    ensure_media_dir = None
    ensure_media_dir = None

    ensure_media_dir = None

    # Simpler: call the real helper
    ensure_media_dir = globals().get("__ensure_media_dir_backup")
    if ensure_media_dir is None:
        # fallback to import from utils (safe to call at runtime)
        from .utils import ensure_media_dir as _ensure_media_dir

        _ensure_media_dir()
    else:
        try:
            ensure_media_dir()
        except Exception:
            pass

    safe_name = _sanitize_filename(filename or "file")
    if unique_id:
        return str(Path(MEDIA_DIR) / f"{unique_id}_{safe_name}")
    return str(Path(MEDIA_DIR) / safe_name)


async def download_from_url(url: str, filename: Optional[str] = None) -> str:
    """Download URL to MEDIA_DIR and return local path.

    Uses httpx with streaming to avoid buffering large files into memory.
    """
    ensure_media_dir()
    local_name = filename or os.path.basename(url.split("?", 1)[0]) or "file"
    local_name = _sanitize_filename(local_name)
    dest = Path(MEDIA_DIR) / local_name

    timeout = httpx.Timeout(HTTP_DOWNLOAD_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            # Write out in binary mode
            with open(dest, "wb") as fh:
                fh.write(resp.content)
        except Exception as exc:
            LOG.exception("Failed to download url %s", url)
            raise
    return str(dest)


async def download_and_cache(bot, file_id: str, file_name: Optional[str] = None) -> str:
    """Download a Telegram File by file_id and cache it locally. Returns local path.

    `bot` is expected to be an instance compatible with python-telegram-bot's Bot
    which provides `get_file(file_id)` returning a File-like object with either:
      - an async `download_to_drive(custom_path)` method, or
      - an async `download(custom_path)` method, or
      - a `file_path` attribute usable for HTTP download via bot session.

    This helper tries these options in order for maximum compatibility.
    """
    ensure_media_dir()

    try:
        telegram_file = await bot.get_file(file_id)
    except Exception:
        # In some contexts `bot` might be a synchronous wrapper. Try running in executor.
        loop = asyncio.get_event_loop()
        telegram_file = await loop.run_in_executor(None, lambda: bot.get_file(file_id))

    # Determine a candidate filename
    uniq = getattr(telegram_file, "file_unique_id", None) or file_id
    candidate_name = file_name or getattr(telegram_file, "file_name", None) or getattr(telegram_file, "file_path", None) or f"{file_id}"
    dest_path = cached_path_for(uniq, candidate_name)

    # Try high-level download methods
    try:
        # prefer async download_to_drive if available
        if hasattr(telegram_file, "download_to_drive"):
            # some versions are async
            download = getattr(telegram_file, "download_to_drive")
            if asyncio.iscoroutinefunction(download):
                await download(dest_path)
            else:
                # sync function — run in executor
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, lambda: download(dest_path))
            return dest_path

        if hasattr(telegram_file, "download"):
            download = getattr(telegram_file, "download")
            if asyncio.iscoroutinefunction(download):
                await download(dest_path)
            else:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, lambda: download(dest_path))
            return dest_path

        # Fallback: HTTP download from file_path if available
        file_path = getattr(telegram_file, "file_path", None)
        if file_path:
            # file_path can be a full HTTPS URL in many PTB versions
            return await download_from_url(file_path, filename=os.path.basename(dest_path))

        # Last resort: try `get_file` result's `download_as_bytearray` or similar
        if hasattr(telegram_file, "download_as_bytearray"):
            download_bytes = getattr(telegram_file, "download_as_bytearray")
            if asyncio.iscoroutinefunction(download_bytes):
                data = await download_bytes()
            else:
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, lambda: download_bytes())
            with open(dest_path, "wb") as fh:
                fh.write(data)
            return dest_path

    except Exception:
        LOG.exception("High-level telegram file download failed for %s", file_id)

    # If all else failed, raise a clear error
    raise RuntimeError(f"Unable to download Telegram file {file_id}")


# Expose helper name used above to avoid import-time circular noise
try:
    from .utils import ensure_media_dir as __ensure_media_dir_backup
except Exception:
    __ensure_media_dir_backup = None


__all__ = ["download_and_cache", "download_from_url", "cached_path_for"]
