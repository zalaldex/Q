#!/usr/bin/env python3
"""
Entrypoint for the Telegram Monospace Bot.

Responsibilities:
- Validate required environment variables
- Configure logging
- Run DB migrations
- Build and run the python-telegram-bot Application
- Register handlers (commands, messages, errors)
- Graceful shutdown on signals
"""

import asyncio
import logging
import os
import signal
import sys
from typing import Optional

from telegram import __version__ as ptb_version  # for debug/info
from telegram.constants import ParseMode

# Application imports (modular components)
# These modules will be created in the bot/ package.
from bot.logger import configure_logging, get_logger
from bot.services.migrations import run_migrations
from bot.handlers.commands import register_command_handlers
from bot.handlers.message import register_message_handlers
from bot.handlers.errors import register_error_handler
from bot.constants import BOT_TOKEN_ENV

from telegram.ext import Application, ApplicationBuilder

LOG = get_logger(__name__)


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


async def _main() -> int:
    # Validate environment
    try:
        bot_token = require_env(BOT_TOKEN_ENV)
    except Exception as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    # Configure logging (structured/loguru via bot.logger)
    configure_logging()

    LOG.info("Starting Telegram Monospace Bot", ptb_version=ptb_version, python_version=sys.version)

    # Run migrations before starting the bot (idempotent)
    try:
        LOG.info("Running database migrations")
        await run_migrations()
        LOG.info("Migrations completed")
    except Exception as exc:
        LOG.exception("Database migrations failed: %s", exc)
        return 3

    # Build the Application
    LOG.debug("Building telegram Application")
    app: Application = ApplicationBuilder().token(bot_token).parse_mode(ParseMode.HTML).build()

    # Register handlers
    LOG.debug("Registering handlers")
    register_command_handlers(app)
    register_message_handlers(app)
    register_error_handler(app)

    # Start the bot with polling. This is portable across Docker/cloud hosts.
    # Application.run_polling handles startup, idle, and graceful shutdown internally,
    # but we'll still attach signal handlers to allow external control if needed.
    LOG.info("Starting polling. Press Ctrl-C to stop.")

    # Use run_polling which is high-level and will block until stop is requested.
    # We wrap it so we can manage signals from the outer event loop if needed.
    try:
        await app.initialize()
        await app.start()
        await app.updater.start_polling()  # safe low-level start to ensure concurrency
        # Idle keeps the process running until a stop is requested.
        await app.updater.idle()
    except asyncio.CancelledError:
        LOG.info("Shutdown requested (cancelled).")
    except Exception:
        LOG.exception("Unexpected exception while running the bot.")
    finally:
        LOG.info("Stopping application and cleaning up.")
        try:
            await app.updater.stop()
        except Exception:
            LOG.debug("updater.stop() raised while stopping", exc_info=True)
        try:
            await app.stop()
            await app.shutdown()
        except Exception:
            LOG.debug("Error during app.stop/shutdown", exc_info=True)

    LOG.info("Bot stopped gracefully")
    return 0


def _handle_exit(sig: int, frame) -> None:
    # This function will be used if the synchronous signal handler is triggered
    LOG.info("Received signal %s, exiting...", sig)
    # Cancel the running loop tasks or stop gracefully by raising CancelledError
    loop = asyncio.get_event_loop()
    for task in asyncio.all_tasks(loop):
        task.cancel()


def main() -> int:
    """
    Synchronous wrapper used by Docker ENTRYPOINT or direct python run.
    Returns an exit code.
    """
    # Ensure BOT_TOKEN env is present for quick failures
    if os.getenv(BOT_TOKEN_ENV) is None:
        print(f"Error: required environment variable {BOT_TOKEN_ENV} is not set.", file=sys.stderr)
        return 2

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Attach basic signal handlers to initiate graceful shutdown
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda s=sig: _handle_exit(s, None))
        except NotImplementedError:
            # Not all platforms support loop.add_signal_handler (e.g., Windows)
            signal.signal(sig, lambda s, f: _handle_exit(s, f))

    try:
        return loop.run_until_complete(_main())
    except KeyboardInterrupt:
        LOG.info("KeyboardInterrupt received, exiting.")
        return 0
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        finally:
            loop.close()


if __name__ == "__main__":
    raise SystemExit(main())
