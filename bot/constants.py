"""
Application-wide constants and lightweight enums.

This file contains constants only (no side-effects) so it can be safely imported
by any module (migrations, handlers, backup, restore, etc.) without changing
runtime state.
"""
from enum import Enum
from typing import Final, Tuple, List, Set

# Environment
BOT_TOKEN_ENV: Final[str] = "BOT_TOKEN"

# Database
DB_DIR: Final[str] = "data"
DB_FILENAME: Final[str] = "monospace.db"
DB_PATH: Final[str] = f"{DB_DIR}/{DB_FILENAME}"
# Use WAL for safer concurrent reading/writing
SQLITE_PRAGMAS: Final[Tuple[Tuple[str, str], ...]] = (
    ("journal_mode", "WAL"),
    ("synchronous", "NORMAL"),
    ("foreign_keys", "ON"),
)

# Backup
BACKUP_FILENAME: Final[str] = "Conversation.txt"
BACKUP_DIR: Final[str] = "backups"

# App metadata
APP_NAME: Final[str] = "Telegram Monospace Bot"
APP_VERSION: Final[str] = "0.1.0"

# Telegram API limits (as of current stable API)
# - Maximum characters in a text message
TELEGRAM_MAX_MESSAGE_LENGTH: Final[int] = 4096
# - Maximum caption length for media
TELEGRAM_MAX_CAPTION_LENGTH: Final[int] = 1024
# - Photos / media file size limits are platform-dependent; we treat them transparently
#   and rely on Telegram's errors when sending too-large files.

# Bot modes (exactly four modes, one active at a time)
class Mode(str, Enum):
    WORD = "word"
    SENTENCE = "sentence"
    PARAGRAPH = "paragraph"
    FULL = "full"

# Default settings
DEFAULT_MODE: Final[Mode] = Mode.PARAGRAPH
DEFAULT_SHRINK: Final[bool] = False

# Chunking priority (must be from most coarse to most fine)
# The chunker will attempt to split by these granularity levels in order.
CHUNK_PRIORITY: Final[Tuple[Mode, ...]] = (
    Mode.PARAGRAPH,
    Mode.SENTENCE,
    Mode.WORD,
)
# Character-level split is the absolute last resort (not represented by a Mode)
CHARACTER_FALLBACK = "character"

# Persistent reply keyboard (exact buttons required by spec)
BUTTON_START: Final[str] = "Start"
BUTTON_SETTINGS: Final[str] = "Settings"
REPLY_KEYBOARD: Final[List[List[str]]] = [
    [BUTTON_START, BUTTON_SETTINGS]
]

# Settings menu items (Settings -> options)
SETTINGS_ITEMS: Final[Tuple[str, ...]] = (
    "Active Mode",
    "Shrink",
    "Backup",
    "Restore",
    "Statistics",
    "About",
)

# Shrink options (boolean toggle labels used in UI)
SHRINK_ON_LABEL: Final[str] = "ON"
SHRINK_OFF_LABEL: Final[str] = "OFF"

# File types and media handling hints
ALLOWED_MEDIA_MIME_PREFIXES: Final[Tuple[str, ...]] = (
    "image/",
    "video/",
    "audio/",
    "application/",
)
# Friendly set of supported Telegram message types for internal routing
SUPPORTED_MESSAGE_TYPES: Final[Set[str]] = frozenset(
    (
        "text",
        "photo",
        "video",
        "audio",
        "voice",
        "sticker",
        "animation",
        "document",
        "contact",
        "location",
        "poll",
        "venue",
    )
)

# Database schema versioning (increment when migrations add changes)
SCHEMA_VERSION: Final[int] = 1

# Limits and timeouts
DEFAULT_DB_TIMEOUT_SECONDS: Final[int] = 30
HTTP_DOWNLOAD_TIMEOUT_SECONDS: Final[int] = 60

# Backup embedding configuration
# When embedding binary media inside Conversation.txt we use base64 with a marker
BACKUP_MEDIA_MARKER_PREFIX: Final[str] = "===MEDIA BASE64"
BACKUP_MEDIA_MARKER_SUFFIX: Final[str] = "===END MEDIA"

# Statistics time windows (in days) used by statistics module
STAT_WINDOW_DAYS: Final[Tuple[int, ...]] = (0, 1, 7, 30, 365)  # 0 => today

# Logger / structured logging defaults
LOG_DEFAULT_LEVEL: Final[str] = "INFO"
LOG_ROTATION: Final[str] = "10 MB"
LOG_RETENTION: Final[str] = "7 days"
LOG_DIR: Final[str] = "logs"

# File storage for downloaded media (local cache)
MEDIA_DIR: Final[str] = "data/media"

# Migrations directory path (relative)
MIGRATIONS_DIR: Final[str] = "bot/services/migrations"

# Misc
MAX_MESSAGE_SPLIT_ATTEMPTS: Final[int] = 10  # guard for chunker infinite loop
