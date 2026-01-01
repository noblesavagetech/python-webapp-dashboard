# gunicorn.conf.py
import os

# Bind to the port Railway provides, default to 8080
port = os.environ.get("PORT", "8080")
bind = f"0.0.0.0:{port}"

# Worker configuration
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
threads = 2
worker_class = "sync"

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Timeout
timeout = 120
keepalive = 5
