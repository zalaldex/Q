"""
Chunking helpers that preserve HTML tag boundaries (<pre>, <code>) when splitting
messages to respect Telegram size limits.

Primary export:
- chunk_monospace_message(html_text: str, max_len: int) -> List[str]

Strategy:
- Tokenize the input into <pre> blocks, <code> inline fragments, and plain-text
  separators.
- Greedily pack tokens into output chunks while keeping HTML tags intact.
- If a single token exceeds max_len (e.g., very large <pre> block), split its
  inner text using the safe splitting utility and rewrap the pieces.

This module depends on bot.utils.split_text_by_max_length to perform safe
split operations at paragraph/sentence/word/character granularity.
"""
from __future__ import annotations

import re
from typing import List, Tuple

from .utils import split_text_by_max_length
from .constants import TELEGRAM_MAX_MESSAGE_LENGTH
from .logger import get_logger

LOG = get_logger(__name__)

# Regex to find <pre>...</pre> and <code>...</code> tokens. DOTALL so pre blocks can contain newlines.
_PRE_CODE_RE = re.compile(r"(<pre>.*?</pre>)|(<code>.*?</code>)", re.DOTALL | re.IGNORECASE)


def _tokenize_html_preserve(html_text: str) -> List[Tuple[str, str]]:
    """Tokenize html_text into a list of (type, content) tuples.

    type is one of: 'pre', 'code', 'text'. Content is the full HTML fragment for pre/code
    (including tags) or the raw text for 'text'.
    """
    tokens: List[Tuple[str, str]] = []
    last_end = 0
    for m in _PRE_CODE_RE.finditer(html_text):
        start, end = m.span()
        if start > last_end:
            tokens.append(("text", html_text[last_end:start]))
        pre_group, code_group = m.group(1), m.group(2)
        if pre_group:
            tokens.append(("pre", pre_group))
        elif code_group:
            tokens.append(("code", code_group))
        last_end = end
    if last_end < len(html_text):
        tokens.append(("text", html_text[last_end:]))
    return tokens


def _unwrap_tag(tagged: str, tag: str) -> str:
    """Return the inner text of <tag>...</tag>. If not matched, return original."""
    pattern = re.compile(rf"^<{tag}>(.*)</{tag}>$", re.DOTALL | re.IGNORECASE)
    m = pattern.match(tagged)
    if not m:
        return tagged
    return m.group(1)


def _wrap_tag(inner: str, tag: str) -> str:
    return f"<{tag}>{inner}</{tag}>"


def _split_large_token(token_type: str, token_content: str, max_len: int) -> List[str]:
    """Split a single large token (pre or code) into smaller wrapped tokens.

    Uses split_text_by_max_length on the inner text and rewraps the pieces with the same tag.
    For 'text' tokens we just split by characters as fallback.
    """
    if token_type == "pre":
        inner = _unwrap_tag(token_content, "pre")
        pieces = split_text_by_max_length(inner, max_len)
        return [ _wrap_tag(p, "pre") for p in pieces ]

    if token_type == "code":
        inner = _unwrap_tag(token_content, "code")
        pieces = split_text_by_max_length(inner, max_len)
        return [ _wrap_tag(p, "code") for p in pieces ]

    # text fallback: naive slicing
    res = []
    t = token_content
    for i in range(0, len(t), max_len):
        res.append(t[i:i+max_len])
    return res


def chunk_monospace_message(html_text: str, max_len: int = TELEGRAM_MAX_MESSAGE_LENGTH) -> List[str]:
    """Split a transformed HTML monospace message into a list of messages each <= max_len.

    The function attempts to preserve HTML tag boundaries (<pre> and <code>) so we never
    send a chunk that cuts in the middle of a tag. If a single tag-wrapped fragment is
    already larger than max_len, it will be split safely using split_text_by_max_length.
    """
    if not html_text:
        return []

    if len(html_text) <= max_len:
        return [html_text]

    tokens = _tokenize_html_preserve(html_text)

    chunks: List[str] = []
    buf_parts: List[str] = []
    buf_len = 0

    def flush_buf():
        nonlocal buf_parts, buf_len
        if not buf_parts:
            return
        chunk = "".join(buf_parts)
        chunks.append(chunk)
        buf_parts = []
        buf_len = 0

    for typ, content in tokens:
        c_len = len(content)
        # If token fits in current buffer, append
        if buf_len + c_len <= max_len:
            buf_parts.append(content)
            buf_len += c_len
            continue

        # Token does not fit in current buffer
        # If the token itself is small enough to fit into an empty buffer, flush current buffer and place it
        if c_len <= max_len:
            # flush current buffer first
            flush_buf()
            buf_parts.append(content)
            buf_len += c_len
            continue

        # Token is larger than max_len and must be split internally
        LOG.debug("Token larger than max_len, splitting token", token_type=typ, token_length=c_len)
        # Split the token into smaller wrapped pieces
        pieces = _split_large_token(typ, content, max_len)
        # Place pieces one by one into buffers
        for piece in pieces:
            p_len = len(piece)
            if p_len > max_len:
                # As a last resort, forcibly slice piece (should rarely occur)
                for i in range(0, p_len, max_len):
                    part = piece[i:i+max_len]
                    if buf_len + len(part) > max_len:
                        flush_buf()
                    buf_parts.append(part)
                    buf_len += len(part)
                    if buf_len >= max_len:
                        flush_buf()
                continue

            if buf_len + p_len > max_len:
                flush_buf()
            buf_parts.append(piece)
            buf_len += p_len
            if buf_len >= max_len:
                flush_buf()

    # flush remaining buffer
    if buf_parts:
        flush_buf()

    # As a safety, ensure no chunk exceeds max_len (trim if necessary)
    final_chunks: List[str] = []
    for ch in chunks:
        if len(ch) <= max_len:
            final_chunks.append(ch)
        else:
            # force-split by characters as last resort
            for i in range(0, len(ch), max_len):
                final_chunks.append(ch[i:i+max_len])

    return final_chunks


__all__ = ["chunk_monospace_message"]
