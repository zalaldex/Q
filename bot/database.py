*** Begin Patch
*** Update File: bot/database.py
@@
     try:
         yield conn
- n    finally:
+    finally:
         try:
             await conn.close()
         except Exception:
             LOG.debug("Error while closing DB connection", exc_info=True)
*** End Patch