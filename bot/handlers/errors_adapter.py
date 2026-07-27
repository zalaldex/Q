"""
Error handler adapter for Application registration.

Provides register_error_handler(app) which attaches a global error handler to the
python-telegram-bot Application's error handling system.
"""
from __future__ import annotations

from telegram.ext import Application

from bot.handlers.errors import error_handler


def register_error_handler(app: Application) -> None:
    # PTB v20+ supports setting a global error handler via `Application.add_error_handler`.
    # To remain compatible, try both modern and older APIs.
    try:
        app.add_error_handler(error_handler)
    except Exception:
        # Older style: set `application.error_handler` if present (best-effort)
        try:
            setattr(app, "error_handler", error_handler)
        except Exception:
            # As a last resort, just log the inability to attach — the app will still run.
            import logging

            logging.getLogger(__name__).warning("Could not register error handler on Application")


__all__ = ["register_error_handler"]
