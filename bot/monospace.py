"""
Monospace transformation utilities.

Provides:
- transform_text_to_monospace(text, mode, shrink) -> str
- shrink_text(text, max_repeat=3) -> str

Behavior:
- Mode.FULL: the entire text is returned inside a single <pre>...</pre> block (HTML-safe).
- Mode.PARAGRAPH: each paragraph is preserved; paragraphs are wrapped in <pre> blocks
  separated by a blank line.
- Mode.SENTENCE: each sentence is wrapped in an inline <code>...</code> element and
  sentences are joined with a single space (preserves sentence boundaries).
- Mode.WORD: each word is wrapped in <code>...</code> and words are joined with
  a single space (preserves token boundaries).

- shrink=True:
  - collapses runs of horizontal whitespace (spaces/tabs) to a single space
  - reduces runs of the same character longer than `max_repeat` to `max_repeat`
    (e.g., "!!!!!!!!!" -> "!!!"). Newlines are preserved for paragraph/sentence modes.

Notes:
- All text is HTML-escaped before embedding into <pre> / <code> to ensure safety
  when using parse_mode=HTML in python-telegram-bot.
"""
from __future__ import annotations

import re
from typing import List

from .constants import Mode
from .utils import normalize_whitespace, safe_html_escape

# Regexes
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_SPLIT_RE = re.compile(r"(\s+)")


def shrink_text(text: str, max_repeat: int = 3) -> str:
    """
    Reduce excessive repeated characters and collapse horizontal whitespace runs.

    - Replaces runs of the same character longer than max_repeat with max_repeat copies.
    - Collapses spaces/tabs into a single space (does not remove newlines).
    """
    if not text:
        return ""
    # Collapse runs of horizontal whitespace (space, tab, vertical tabs not included)
    # Preserve newlines by operating per-line for the whitespace collapse
    lines = text.splitlines(keepends=True)
    collapsed_lines = []
    for line in lines:
        # Only collapse runs of spaces/tabs in each line (preserves line structure)
        line = re.sub(r"[ \t\f\v]+", " ", line)
        collapsed_lines.append(line)
    collapsed = "".join(collapsed_lines)

    # Reduce repeated characters longer than max_repeat
    if max_repeat > 0:
        # Use a backreference to collapse runs like "aaaaaa" -> "aaa"
        collapsed = re.sub(r"(.)\1{" + str(max_repeat) + r",}", lambda m: m.group(1) * max_repeat, collapsed)
    return collapsed


def _split_paragraphs(text: str) -> List[str]:
    # Paragraphs are separated by one or more blank lines
    parts = re.split(r"\n\s*\n+", text)
    return [p for p in parts if p is not None]


def _split_sentences(text: str) -> List[str]:
    # Splits text into sentences by punctuation followed by whitespace.
    parts = _SENTENCE_SPLIT_RE.split(text)
    return [p.strip() for p in parts if p.strip()]


def _split_words_preserve_whitespace(text: str) -> List[str]:
    # Split into words but keep separators so we can preserve spacing where needed.
    # The pattern splits but returns the separators as separate list entries.
    parts = re.split(_WORD_SPLIT_RE, text)
    return [p for p in parts if p is not None]


def _wrap_code_inline(s: str) -> str:
    # Use <code> for inline monospace fragments. Escape first.
    return f"<code>{safe_html_escape(s)}</code>"


def _wrap_pre_block(s: str) -> str:
    # Use <pre> for block monospace. Escape first.
    return f"<pre>{safe_html_escape(s)}</pre>"


def transform_text_to_monospace(text: str, mode: Mode = Mode.PARAGRAPH, shrink: bool = False) -> str:
    """
    Transform input text into a monospace-safe HTML string according to mode.

    Returns a string ready to send with parse_mode=HTML.
    """
    if text is None:
        return ""

    # Normalize whitespace for consistent behavior
    working = normalize_whitespace(text)

    if shrink:
        working = shrink_text(working)

    if mode == Mode.FULL:
        # Entire text as a single pre block (preserve newlines)
        return _wrap_pre_block(working)

    if mode == Mode.PARAGRAPH:
        paragraphs = _split_paragraphs(working)
        blocks = []
        for p in paragraphs:
            # Each paragraph becomes a pre block to preserve internal newlines
            blocks.append(_wrap_pre_block(p))
        # Separate paragraphs with a blank line to keep readability
        return "\n\n".join(blocks)

    if mode == Mode.SENTENCE:
        sentences = _split_sentences(working)
        wrapped = []
        for s in sentences:
            wrapped.append(_wrap_code_inline(s))
        # Join with a single space (sentences already have punctuation)
        return " ".join(wrapped)

    if mode == Mode.WORD:
        parts = _split_words_preserve_whitespace(working)
        out_parts = []
        for part in parts:
            if part.isspace():
                # preserve original spacing in normalized form (single space)
                out_parts.append(" ")
            else:
                out_parts.append(_wrap_code_inline(part))
        return "".join(out_parts)

    # Fallback: full pre block
    return _wrap_pre_block(working)
