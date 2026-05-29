"""Gunicorn configuration for the honeywatch API.

``workers * threads`` stays <= the DB pool capacity so a
fully-saturated worker pool cannot exhaust the connection pool.
"""

from __future__ import annotations

import os

bind = "0.0.0.0:5000"

workers = int(os.environ.get("GUNICORN_WORKERS", "2"))
threads = int(os.environ.get("GUNICORN_THREADS", "4"))
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "30"))

# Drain in-flight requests on SIGTERM before the worker is killed.
graceful_timeout = int(os.environ.get("GUNICORN_GRACEFUL_TIMEOUT", "30"))

# Recycle workers to bound any slow memory growth.
max_requests = 1000
max_requests_jitter = 50

worker_tmp_dir = "/dev/shm"

accesslog = "-"
errorlog = "-"
