*** Begin Patch
*** Update File: Dockerfile
@@
-# Install system dependencies required to build some Python packages
-# Keep them minimal; remove apt caches after install to reduce image size
-RUN apt-get update \
-    && apt-get install -y --no-install-recommends \
-       build-essential \
-       git \
-       ca-certificates \
-       libffi-dev \
-       libssl-dev \
-       curl \
-    && rm -rf /var/lib/apt/lists/*
+# Install system dependencies required to build some Python packages
+# Add extra dev packages commonly needed for cryptography, Pillow, lxml, psycopg2, etc.
+# Keep them minimal and remove apt caches after install to reduce image size.
+RUN apt-get update \
+    && apt-get install -y --no-install-recommends \
+       build-essential \
+       git \
+       ca-certificates \
+       libffi-dev \
+       libssl-dev \
+       curl \
+       gcc \
+       libc6-dev \
+       libpq-dev \
+       libxml2-dev \
+       libxslt1-dev \
+       zlib1g-dev \
+       libjpeg-dev \
+       libjpeg62-turbo-dev \
+       libfreetype6-dev \
+       libwebp-dev \
+       cargo \
+    && rm -rf /var/lib/apt/lists/*
@@
-RUN pip install --upgrade pip \
-    && pip install --no-cache-dir -r requirements.txt
+RUN python -m pip install --upgrade pip setuptools wheel \
+    && pip install --no-cache-dir -r requirements.txt
*** End Patch