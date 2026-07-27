"""
Sending helpers: send transformed monospace HTML messages safely by chunking,
handling retries, and optionally sending media groups with captions.

Exports:
- async send_with_retries(fn, *args, attempts=3, backoff_base=1.5)
- async send_text_chunks(bot, chat_id, chunks, parse_mode='HTML') -> List[Message]
- async send_transformed(bot, chat_id, html_text, *, media_paths=None, parse_mode='HTML') -> List[Message]

Notes:
- This module uses python-telegram-bot style Bot methods: send_message, send_media_group.
  It is best-effort and catches transient network errors, retrying with exponential backoff.
- Returned Message objects are the objects returned by the Bot API when sending.
"""
from __future__ import annotations

import asyncio
import random
from typing import Any, Iterable, List, Optional, Callable, Awaitable

from .chunker import chunk_monospace_message
from .constants import TELEGRAM_MAX_MESSAGE_LENGTH, SENDER_RETRY_ATTEMPTS, SENDER_BACKOFF_BASE
from .logger import get_logger

LOG = get_logger(__name__)


async def send_with_retries(
    fn: Callable[..., Awaitable[Any]],
    *args,
    attempts: int = SENDER_RETRY_ATTEMPTS,
    backoff_base: float = SENDER_BACKOFF_BASE,
    **kwargs,
) -> Any:
    """Call async function `fn(*args, **kwargs)` with retries and exponential backoff.

    On success returns fn(...) result. On persistent failure re-raises the last exception.
    """
    last_exc = None
    for attempt in range(1, max(1, attempts) + 1):
        try:
            result = await fn(*args, **kwargs)
            return result
        except Exception as exc:
            last_exc = exc
            wait = backoff_base * (2 ** (attempt - 1))
            # jitter in range +/-10%
            jitter = (random.random() - 0.5) * 0.2 * wait
            wait = max(0.1, wait + jitter)
            LOG.warning("Send attempt %s failed, retrying in %.2fs: %s", attempt, wait, exc)
            await asyncio.sleep(wait)
    # If we get here, re-raise the last exception
    raise last_exc


async def send_text_chunks(bot, chat_id: int, chunks: Iterable[str], parse_mode: str = "HTML") -> List[Any]:
    """Send each chunk as a separate message. Returns list of Message objects.

    This helper preserves order and tries to send each chunk with retries.
    """
    results: List[Any] = []
    for chunk in chunks:
        if not chunk:
            continue

        async def _send():
            return await bot.send_message(chat_id=chat_id, text=chunk, parse_mode=parse_mode)

        try:
            msg = await send_with_retries(_send)
            results.append(msg)
        except Exception:
            LOG.exception("Failed to send message chunk to chat %s", chat_id)
            # continue with remaining chunks; return what we sent so far
            break
    return results


async def send_transformed(
    bot,
    chat_id: int,
    html_text: str,
    *,
    media_paths: Optional[List[str]] = None,
    parse_mode: str = "HTML",
) -> List[Any]:
    """Send transformed HTML-safe monospace text, chunking it to fit limits.

    If media_paths is provided (list of local file paths), the function will attempt to
    send them as a media group with the first chunk used as the caption for the first media
    item when possible (caption size limited to TELEGRAM_MAX_MESSAGE_LENGTH). Remaining chunks
    (or when no media_paths) are sent as regular messages.

    Returns a list of Message objects for all successfully sent messages.
    """
    if not html_text:
        return []

    chunks = chunk_monospace_message(html_text, TELEGRAM_MAX_MESSAGE_LENGTH)

    sent: List[Any] = []

    # If there are media files and at least one chunk, try to send a media group with caption
    if media_paths:
        try:
            # Import PTB media classes dynamically to avoid hard dependency
            from telegram import InputMediaPhoto, InputMediaDocument

            media_objs = []
            file_objs = []
            for p in media_paths:
                f = open(p, "rb")
                file_objs.append(f)
                if str(p).lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp")):
                    media_objs.append(InputMediaPhoto(media=f))
                else:
                    media_objs.append(InputMediaDocument(media=f))

            # attach first chunk as caption if fits
            if chunks:
                caption = chunks[0]
                if len(caption) > TELEGRAM_MAX_MESSAGE_LENGTH:
                    caption = caption[:TELEGRAM_MAX_MESSAGE_LENGTH]
                media_objs[0].caption = caption
                media_objs[0].parse_mode = parse_mode

            async def _send_media():
                return await bot.send_media_group(chat_id=chat_id, media=media_objs)

            try:
                res = await send_with_retries(_send_media)
                # send_media_group returns list of messages (one per media)
                sent.extend(res)
            except Exception:
                LOG.exception("Failed to send media group to chat %s", chat_id)
                # fallback: try sending files individually with caption on first
                for idx, p in enumerate(media_paths):
                    async def _send_file(path=p, caption_text=(chunks[0] if idx == 0 and chunks else None)):
                        return await bot.send_document(chat_id=chat_id, document=open(path, "rb"), caption=caption_text, parse_mode=parse_mode if caption_text else None)
                    try:
                        msg = await send_with_retries(_send_file)
                        sent.append(msg)
                    except Exception:
                        LOG.exception("Failed to send file %s to chat %s", p, chat_id)
            finally:
                # ensure we close opened file objects
                for fh in file_objs:
                    try:
                        fh.close()
                    except Exception:
                        pass
            # consume first chunk since used as caption
            if chunks:
                chunks = chunks[1:]
        except Exception:
            LOG.exception("Unable to send media group; continuing to send text chunks")

    # send remaining chunks as text messages
    text_msgs = await send_text_chunks(bot, chat_id, chunks, parse_mode=parse_mode)
    sent.extend(text_msgs)
    return sent


__all__ = ["send_transformed", "send_text_chunks", "send_with_retries"]
