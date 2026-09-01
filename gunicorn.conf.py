import os

bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"
# Force exactly 1 worker on Render to stay within the 512MB RAM limit
workers = 1
threads = int(os.environ.get('GUNICORN_THREADS', '2'))
timeout = int(os.environ.get('GUNICORN_TIMEOUT', '300'))
graceful_timeout = 30
keepalive = 5