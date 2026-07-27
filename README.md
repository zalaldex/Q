### Persistence and storage

This bot persists incoming messages and outgoing send metadata to a local SQLite database (WAL mode). The following tables are available after migrations run:

- messages: incoming messages with columns `id, date, user_id, text, message_type`
- media: media metadata and local cache path with columns `id, message_id, file_unique_id, file_name, mime_type, local_path`
- sent_messages: outgoing messages sent by the bot with columns `id, incoming_message_id, telegram_message_id, chat_id, date, content`

Notes:
- Media files referenced in incoming messages are downloaded and cached under the configured MEDIA_DIR. Backups include cached media embedded as base64 inside Conversation.txt.
- Persistence is best-effort: failures during DB writes or media download are logged and do not block the bot from sending transformed messages.
- No automatic retention policy is configured by default; data is kept indefinitely unless you implement pruning.

Example queries

- Recently sent messages:

  SELECT id, incoming_message_id, telegram_message_id, chat_id, date, content FROM sent_messages ORDER BY id DESC LIMIT 50;

- Recently received messages with media:

  SELECT m.id, m.date, m.user_id, m.text, md.local_path
  FROM messages m
  LEFT JOIN media md ON md.message_id = m.id
  ORDER BY m.id DESC LIMIT 50;

