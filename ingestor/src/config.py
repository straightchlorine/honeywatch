from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str
    postgres_port: int
    log_path: str

    # Reliability knobs. Three attempts at 1/2/4s totals ~7s before declaring
    # failure; 50 consecutive failures trips the breaker for 30s before probing.
    retry_attempts: int = 3
    retry_initial_backoff: float = 1.0
    fuse_threshold: int = 50
    fuse_sleep: float = 30.0

    # Suppress cowrie's docker healthcheck dials in prod; dev enables them.
    drop_loopback: bool = True

    # Bounded producer/consumer queue. Backpressure blocks the tail; cowrie's
    # file still holds the line so no data loss until disk fills.
    queue_max: int = 10000

    # Liveness file touched from the consumer loop iteration (not from a
    # successful write) so DB stalls don't trigger pod restart mid-backlog.
    healthcheck_path: Path = Path("/tmp/healthy")

    # node_exporter conventionally takes 9100; pick the next free port.
    metrics_port: int = 9101

    # Off by default; counters still populate. Flip on when a scraper is wired.
    metrics_enabled: bool = False

    @classmethod
    def from_env(cls) -> Config:
        """Build a Config from environment variables.

        Returns:
            A populated, frozen `Config`.

        Raises:
            KeyError: If a required variable (`POSTGRES_USER`, `POSTGRES_PASSWORD`,
                `POSTGRES_DB`) is unset.
        """
        return cls(
            postgres_user=os.environ["POSTGRES_USER"],
            postgres_password=os.environ["POSTGRES_PASSWORD"],
            postgres_db=os.environ["POSTGRES_DB"],
            postgres_host=os.environ.get("POSTGRES_HOST", "postgres"),
            postgres_port=int(os.environ.get("POSTGRES_PORT", "5432")),
            log_path=os.environ.get("LOG_PATH", "/logs/cowrie.json"),
            retry_attempts=int(os.environ.get("RETRY_ATTEMPTS", "3")),
            retry_initial_backoff=float(os.environ.get("RETRY_INITIAL_BACKOFF", "1.0")),
            fuse_threshold=int(os.environ.get("FUSE_THRESHOLD", "50")),
            fuse_sleep=float(os.environ.get("FUSE_SLEEP", "30.0")),
            drop_loopback=os.environ.get("DROP_LOOPBACK", "1") == "1",
            queue_max=int(os.environ.get("QUEUE_MAX", "10000")),
            healthcheck_path=Path(os.environ.get("HEALTHCHECK_PATH", "/tmp/healthy")),
            metrics_port=int(os.environ.get("METRICS_PORT", "9101")),
            metrics_enabled=os.environ.get("METRICS_ENABLED", "0") == "1",
        )

    @property
    def conninfo(self) -> str:
        # sslmode=disable: postgres reachable only on the internal docker bridge net.
        return (
            f"host={self.postgres_host} "
            f"port={self.postgres_port} "
            f"dbname={self.postgres_db} "
            f"user={self.postgres_user} "
            f"password={self.postgres_password} "
            f"sslmode=disable"
        )
