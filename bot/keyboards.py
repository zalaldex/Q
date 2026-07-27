"""
Reply and inline keyboards for the bot UI.

Includes:
- persistent_reply_keyboard(): ReplyKeyboardMarkup with Start and Settings (persistent)
- settings_keyboard(): InlineKeyboardMarkup listing settings items
- mode_keyboard(current_mode): InlineKeyboardMarkup to select active mode
- shrink_keyboard(current_shrink): InlineKeyboardMarkup to toggle shrink option

Callback data strings follow these forms:
- settings:<item_key>  (e.g., settings:backup)
- set_mode:<mode_value> (e.g., set_mode:paragraph)
- set_shrink:0|1
- settings:back

This module keeps UI labels and callback formats centralized for handlers to use.
"""
from __future__ import annotations

from typing import List

from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

from .constants import (
    REPLY_KEYBOARD,
    SETTINGS_ITEMS,
    SHRINK_ON_LABEL,
    SHRINK_OFF_LABEL,
    Mode,
)


def persistent_reply_keyboard() -> ReplyKeyboardMarkup:
    """Return the persistent reply keyboard (Start, Settings)."""
    # REPLY_KEYBOARD is a list-of-lists of button labels
    return ReplyKeyboardMarkup(REPLY_KEYBOARD, resize_keyboard=True, one_time_keyboard=False)


def settings_keyboard() -> InlineKeyboardMarkup:
    """Return an InlineKeyboardMarkup with all settings items as separate rows.

    Callback format: settings:<item_key>
    """
    buttons: List[InlineKeyboardButton] = []
    for item in SETTINGS_ITEMS:
        key = item.lower().replace(" ", "_")
        buttons.append(InlineKeyboardButton(text=item, callback_data=f"settings:{key}"))
    # One button per row
    rows = [[b] for b in buttons]
    rows.append([InlineKeyboardButton(text="Back", callback_data="settings:back")])
    return InlineKeyboardMarkup(rows)


def mode_keyboard(current_mode: Mode) -> InlineKeyboardMarkup:
    """Return a keyboard allowing the user to choose the active Mode.

    The current mode is marked with a checkmark.
    Callback format: set_mode:<mode_value>
    """
    rows: List[List[InlineKeyboardButton]] = []

    for mode in Mode:
        label = mode.value.capitalize()
        if mode == current_mode:
            label = f"✅ {label}"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"set_mode:{mode.value}")])

    rows.append([InlineKeyboardButton(text="Back", callback_data="settings:back")])
    return InlineKeyboardMarkup(rows)


def shrink_keyboard(current_shrink: bool) -> InlineKeyboardMarkup:
    """Return a keyboard to toggle the shrink option.

    Callback format: set_shrink:0  or set_shrink:1
    """
    on_label = SHRINK_ON_LABEL
    off_label = SHRINK_OFF_LABEL
    if current_shrink:
        on_label = f"✅ {on_label}"
    else:
        off_label = f"✅ {off_label}"

    rows = [
        [InlineKeyboardButton(text=on_label, callback_data="set_shrink:1")],
        [InlineKeyboardButton(text=off_label, callback_data="set_shrink:0")],
        [InlineKeyboardButton(text="Back", callback_data="settings:back")],
    ]
    return InlineKeyboardMarkup(rows)


__all__ = [
    "persistent_reply_keyboard",
    "settings_keyboard",
    "mode_keyboard",
    "shrink_keyboard",
]
