# gunicorn.conf.py
import os

# Get the port from the environment variable, default to 8080
port = os.environ.get("PORT", "8080")

# Gunicorn config variables
bind = f"0.0.0.0:{port}"
workers = int(os.environ.get("WEB_CONCURRENCY", 1))
