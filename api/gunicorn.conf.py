"""Gunicorn configuration for the API.

Keep `workers * threads` <= the DB pool size (`src/extensions.py`) so a
fully saturated worker pool cannot exhaust the connection pool. Not enforced
in code - if you bump the env vars below, bump the pool size too.
"""

from __future__ import annotations

import os

from src.logging_config import build_logging_config

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

# %(h)s (client IP) is intentionally omitted so attacker IPs never hit the log.
access_log_format = '"%(r)s" %(s)s %(b)s %(L)s req=%({x-request-id}i)s'

logconfig_dict = build_logging_config()
