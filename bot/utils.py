"""
Utility helpers used across the bot.

- ensure_dirs: create required directories
- normalize_whitespace: collapse repeated whitespace
- safe_html_escape: escape text for HTML parse_mode
- split_text_by_max_length: split text into chunks not exceeding a given length,
  attempting to preserve paragraphs, sentences, and words in that order.
- chunk_message_for_send: convenience wrapper using TELEGRAM_MAX_MESSAGE_LENGTH
"""
from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Iterable, List

from .constants import TELEGRAM_MAX_MESSAGE_LENGTH, MEDIA_DIR

_PARAGRAPH_DELIM = "\n\n"
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_SPLIT_RE = re.compile(r"\s+")


def ensure_dirs(*paths: str) -> None:
    """
    Ensure a list of directories exists (no-op if already present).
    Example: ensure_dirs('data', 'logs', MEDIA_DIR)
    """
    for p in paths:
        Path(p).mkdir(parents=True, exist_ok=True)


def normalize_whitespace(text: str) -> str:
    """Collapse runs of whitespace into single spaces, but preserve line breaks."""
    # Replace CRLF with LF, normalize multiple blank lines to two, and collapse inline whitespace.
    if text is None:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse multiple blank lines into exactly one blank line (two newlines).
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    # Collapse other whitespace sequences into a single space, but preserve newlines.
    lines = [re.sub(r"[ \t\f\v]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(lines).strip()


def safe_html_escape(text: str) -> str:
    """Escape text for HTML parse mode (keeps it safe to send as HTML)."""
    if text is None:
        return ""
    return html.escape(text, quote=False)


def _split_by_delimiter(text: str, delim: str) -> List[str]:
    if not text:
        return []
    if delim == _PARAGRAPH_DELIM:
        return [p.strip() for p in text.split(_PARAGRAPH_DELIM) if p.strip()]
    if delim == "sentence":
        # Use regex to split into sentences; keep delimiters by post-processing.
        parts = _SENTENCE_SPLIT_RE.split(text)
        return [p.strip() for p in parts if p.strip()]
    if delim == "word":
        return [w for w in _WORD_SPLIT_RE.split(text) if w]
    # Fallback: split by single characters
    return [c for c in text]


def _join_with_separator(parts: Iterable[str], sep: str) -> str:
    if sep == "sentence":
        # join sentences with a space
        return " ".join(parts)
    if sep == "word":
        return " ".join(parts)
    return sep.join(parts)


def split_text_by_max_length(
    text: str, max_len: int = TELEGRAM_MAX_MESSAGE_LENGTH, delimiters=None
) -> List[str]:
    """
    Split text into chunks <= max_len. Strategy:
      1) Try splitting by paragraphs (\n\n)
      2) Then split oversize paragraphs by sentences
      3) Then split by words
      4) Finally split by characters as last resort

    Returns a list of chunks in original order.
    """
    if text is None:
        return []

    if len(text) <= max_len:
        return [text]

    if delimiters is None:
        delimiters = [_PARAGRAPH_DELIM, "sentence", "word", "char"]

    # Start with the coarse-grained split
    segments = _split_by_delimiter(text, _PARAGRAPH_DELIM)

    def _rechunk(segments_list: List[str], delim_index: int) -> List[str]:
        delim = delimiters[delim_index]
        result: List[str] = []
        for seg in segments_list:
            if not seg:
                continue
            if len(seg) <= max_len:
                result.append(seg)
                continue
            # If at last delimiter and still oversize, do character-level slicing
            if delim == "char" or delim_index == len(delimiters) - 1:
                # slice into max_len pieces
                for i in range(0, len(seg), max_len):
                    result.append(seg[i : i + max_len])
                continue
            # Split this segment further using the next delimiter
            parts = _split_by_delimiter(seg, "sentence" if delim == _PARAGRAPH_DELIM else ("word" if delim == "sentence" else "char"))
            # If splitting produced no smaller parts (edge-case), fallback to character slices
            if not parts or (len(parts) == 1 and parts[0] == seg):
                for i in range(0, len(seg), max_len):
                    result.append(seg[i : i + max_len])
                continue
            # Attempt to pack parts into chunks not exceeding max_len
            buf: List[str] = []
            buf_len = 0
            sep = "sentence" if delim == _PARAGRAPH_DELIM else ("word" if delim == "sentence" else "")
            for part in parts:
                part_text = part.strip()
                if not part_text:
                    continue
                add_len = len(part_text) + (1 if buf else 0)
                if buf_len + add_len <= max_len:
                    buf.append(part_text)
                    buf_len += add_len
                else:
                    # flush buffer
                    if buf:
                        result.append(_join_with_separator(buf, sep))
                    # if single part is larger than max_len, it will be further split in deeper recursion
                    if len(part_text) > max_len:
                        # recursively rechunk this single large part with next delimiter
                        deeper = _rechunk([part_text], delim_index + 1)
                        result.extend(deeper)
                        buf = []
                        buf_len = 0
                    else:
                        buf = [part_text]
                        buf_len = len(part_text)
            if buf:
                result.append(_join_with_separator(buf, sep))
        return result

    # Apply recursive rechunk starting from the first delimiter
    final_chunks = _rechunk(segments, 0)

    # As a safety, ensure every chunk is <= max_len. If not, force char split.
    safe_chunks: List[str] = []
    for chunk in final_chunks:
        if len(chunk) <= max_len:
            safe_chunks.append(chunk)
        else:
            for i in range(0, len(chunk), max_len):
                safe_chunks.append(chunk[i : i + max_len])
    return safe_chunks


def chunk_message_for_send(text: str, max_len: int = TELEGRAM_MAX_MESSAGE_LENGTH) -> List[str]:
    """
    Public helper that normalizes whitespace and returns safe chunks for sending.
    """
    if not text:
        return []
    normalized = normalize_whitespace(text)
    return split_text_by_max_length(normalized, max_len)


# Ensure media dir exists on-demand
def ensure_media_dir() -> None:
    ensure_dirs(MEDIA_DIR)
