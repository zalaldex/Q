# Telegram Monospace Bot

A production-ready Telegram bot that converts messages into monospace while preserving original content as closely as the Telegram Bot API allows.

- Language: Python 3.13+
- Async library: python-telegram-bot (async)
- Database: SQLite (WAL) via aiosqlite
- One environment variable: BOT_TOKEN
- Persistent reply keyboard with two buttons: Start, Settings
- Modes: Word, Sentence, Paragraph, Full
- Automatic chunking when Telegram limits are exceeded
- Backup/Restore via a single readable Conversation.txt (binary media embedded base64)

Quick links
- Repo: zalaldex/Q
- Required env: BOT_TOKEN

Table of contents
- Installation
- Local run
- Docker
- Railway
- Render
- Backup
- Restore
- Updating
- Troubleshooting
- Design & architecture
- License

Installation (local)
1. Requirements
   - Python 3.13+
   - Git
   - Optional: virtualenv / venv

2. Clone
   git clone https://github.com/zalaldex/Q.git
   cd Q

3. Create virtual environment and install
   python -m venv .venv
   source .venv/bin/activate    # macOS / Linux
   .venv\Scripts\activate       # Windows (PowerShell)
   pip install --upgrade pip
   pip install -r requirements.txt

4. Configure
   Export the bot token:
   export BOT_TOKEN="123456:ABC-DEF..."
   (Windows PowerShell)
   $env:BOT_TOKEN="123456:ABC-DEF..."

5. Run migrations (automated on startup but can be invoked)
   # The bot runs automatic migrations at startup. No manual step required.

Local run
- Start the bot:
  python run.py

- The bot is asynchronous and will keep running in the foreground. Use standard process managers (systemd, supervisord, pm2, or Docker) for production.

Docker
- Build image:
  docker build -t telegram-monospace-bot:latest .

- Run container:
  docker run -e BOT_TOKEN="123456:ABC-DEF..." --restart unless-stopped telegram-monospace-bot:latest

- The Dockerfile uses a non-root user and a slim Python image for production-friendly deployments.

Railway
- Railway can deploy with the provided railway.json. Create a new project on Railway, connect your GitHub repo Zalaldex/Q, and set the required env var BOT_TOKEN. The service is configured to run the Dockerfile and start with `python run.py`.

Render
- The included render.yaml configures a Docker web service. Deploy via Render by linking the repo and adding BOT_TOKEN in Render's Environment section.

One-click deploy notes
- Each platform requires you to add the BOT_TOKEN environment variable securely in their dashboard.
- The app runs as a Docker container on these platforms; no additional runtime configuration is required.

Usage
- Keyboard: persistent reply keyboard (Start, Settings).
- Commands:
  - /start — welcome and quick usage
  - /settings — open settings (active mode, shrink toggle, backup & restore, statistics, about)
  - Backup and Restore are accessible via Settings UI.
- Modes (exactly one active at a time):
  - Word — transform token-by-token in words
  - Sentence — transform per-sentence
  - Paragraph — transform per-paragraph
  - Full — transform entire message as a block

Chunking rules
- The bot never truncates messages.
- When Telegram size limits are exceeded, the bot splits the output automatically.
- Priority for chunking: Paragraph → Sentence → Word → Character (last resort)

Backup (Conversation.txt)
- Backup exports everything into a single readable Conversation.txt including:
  - Users, settings, messages, captions, entities, media metadata, reply relations, timestamps, Telegram file IDs
  - Binary media files are downloaded, base64 encoded, and embedded inline in Conversation.txt for portability
- To create a backup: use Settings → Backup in the bot UI
- The Conversation.txt file is UTF-8 and human-readable. Media sections include base64 with headers indicating file type and original filename.

Restore
- Use Settings → Restore and upload a previously generated Conversation.txt
- The restore attempts to reconstruct messages, captions, entities, metadata, and media metadata. Binary media will be re-uploaded where necessary and stored in the database along with Telegram file IDs when possible.
- Not all Telegram-only metadata can be fully restored (e.g., original message IDs cannot be re-used); the bot will try to preserve relations and timestamps inside its database.

Database & migrations
- SQLite with WAL mode for safety: data/monospace.db (default)
- Simple schema optimized for messages, users, settings, media metadata, and statistics.
- Automatic migrations run at startup (idempotent). No manual SQL required.

Statistics
- The bot tracks:
  - Active users (last 7/30 days)
  - Unique users
  - Messages: today, last 24h, 7d, 30d, 1 year, lifetime
- Statistics are available in Settings → Statistics

Settings
- Active Mode (Word / Sentence / Paragraph / Full)
- Shrink (ON / OFF) — universal toggle that applies in every mode
- Backup / Restore
- Statistics
- About

Logging & errors
- Structured logging is implemented.
- A global error handler captures and logs unexpected errors and returns a polite message to users.
- Logs are written to logs/ for local runs and to stdout for container deployments.

Security & privacy
- The bot stores conversation data locally (SQLite). Make sure to secure backups and the repository.
- Bot token must not be committed to the repository. Use environment variables provided by hosting platforms.

Project layout (important modules)
- run.py — entrypoint
- bot/
  - constants.py
  - logger.py
  - database.py
  - models.py
  - keyboards.py
  - utils.py
  - monospace.py
  - chunker.py
  - media.py
  - backup.py
  - restore.py
  - statistics.py
  - settings.py
  - sender.py
  - handlers/
    - commands.py
    - message.py
    - errors.py
  - services/
    - migrations.py

Updating
1. Pull latest changes:
   git pull origin main

2. Rebuild image (if using Docker):
   docker build -t telegram-monospace-bot:latest .

3. Restart your process or container with the same BOT_TOKEN.

Troubleshooting
- Bot not responding:
  - Verify BOT_TOKEN is correct and the bot is not blocked.
  - Check logs (logs/) for structured error messages.
- SQLite locked errors:
  - WAL mode is enabled. If you see locks, ensure only one process writes at a time and use the provided migrations and aiosqlite which supports async access.
- Restore failures:
  - Ensure Conversation.txt was generated by this bot version and is UTF-8 encoded.

Contributing & architecture notes
- The codebase is modular: each feature is isolated in a single module so future changes can be targeted (for example: services/backup.py or handlers/message.py).
- Tests are not included in this initial scaffold but the codebase is organized to be testable.

License
- MIT — see LICENSE

If you are ready I will commit README.md and then generate run.py (entrypoint) which will wire up startup, migrations, graceful shutdown, and the bot runner. Reply "Continue" to push README.md and continue.
