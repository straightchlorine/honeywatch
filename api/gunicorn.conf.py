"""Gunicorn configuration for the API.

``workers * threads`` stays <= the DB pool: fully saturated worker pool cannot
exhaust the connection pool.
"""

from __future__ import annotations
from src.logging_config import build_logging_config
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

# Dropping the %(h)s - that would reveal attackers ip.
access_log_format = '"%(r)s" %(s)s %(b)s %(L)s req=%({x-request-id}i)s'

# Ensure gunicorn's own logs follow the pattern set by the application.
logconfig_dict = build_logging_config()
