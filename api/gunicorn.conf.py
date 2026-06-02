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

# Drop %(h)s (the remote address) from the access log. Behind ProxyFix(x_for=1)
# %(h)s resolves to the real attacker IP, which would otherwise reach the shared
# stdout sink on every request -- contradicting the src_ip-suppression policy
# (see tests/test_no_src_ip_on_all_endpoints.py). Keep the request line, status,
# byte length, latency (%(L)s) and the propagated request id so traces stay
# correlatable without ever logging the source IP.
access_log_format = '"%(r)s" %(s)s %(b)s %(L)s req=%({x-request-id}i)s'

# Route gunicorn's own access/error records through the app's dictConfig so the
# gunicorn.access / gunicorn.error loggers emit the same JSON stream as the
# Flask app (see src.logging_config). Without this gunicorn installs its own
# plaintext handlers and prod logs become two mismatched formats.
from src.logging_config import build_logging_config  # noqa: E402

logconfig_dict = build_logging_config()
