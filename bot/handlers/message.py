*** Begin Patch
*** Update File: bot/handlers/message.py
@@
 from bot.logger import get_logger
 from bot.monospace import transform_text_to_monospace
 from bot.settings import get_settings_db
 from bot.sender import send_transformed
+from bot.services.persistence import save_incoming_message, record_sent_messages
@@
 async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
@@
-    # Read settings to determine mode and shrink option
-    settings = await get_settings_db()
-    mode = settings.get("mode")
-    shrink = settings.get("shrink", False)
+    # Read settings to determine mode and shrink option
+    settings = await get_settings_db()
+    mode = settings.get("mode")
+    shrink = settings.get("shrink", False)
+
+    # Persist incoming message (best-effort)
+    try:
+        incoming_id = await save_incoming_message(update)
+    except Exception:
+        LOG.exception("Failed to save incoming message")
+        incoming_id = None
@@
-    # Send transformed text (no media)
-    try:
-        await send_transformed(context.bot, chat_id, html, media_paths=None)
-    except Exception:
-        LOG.exception("Failed to send transformed message")
-        await update.message.reply_text("Failed to send transformed message")
+    # Send transformed text (no media)
+    try:
+        sent_results = await send_transformed(context.bot, chat_id, html, media_paths=None)
+        # Persist sent message records (best-effort)
+        try:
+            await record_sent_messages(incoming_id, sent_results)
+        except Exception:
+            LOG.exception("Failed to record sent messages")
+    except Exception:
+        LOG.exception("Failed to send transformed message")
+        await update.message.reply_text("Failed to send transformed message")
*** End Patch