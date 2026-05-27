FROM python:3.13-slim@sha256:b04b5d7233d2ad9c379e22ea8927cd1378cd15c60d4ef876c065b25ea8fb3bf3

COPY --from=ghcr.io/astral-sh/uv:0.11.12@sha256:3a59a3cdd5f7c217faa36e32dbc7fddbb0412889c2a0a5229f6d790e5a019dd7 /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ src/
RUN uv sync --frozen --no-dev

# GeoLite2 mmdb files - fetched into data/ by scripts/fetch-mmdb.sh.
RUN mkdir -p /data/geoip
COPY data/ /data/geoip/
ENV GEOIP_DATA_DIR=/data/geoip

RUN useradd --create-home --shell /bin/bash ingestor \
    && chown -R ingestor:ingestor /app /data/geoip
USER ingestor

# Use the prebuilt venv directly at runtime; avoids uv cache init at start.
ENV PATH="/app/.venv/bin:$PATH"

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD sh -c 'test $(( $(date +%s) - $(stat -c %Y /tmp/healthy 2>/dev/null || echo 0) )) -lt 60' || exit 1

CMD ["python", "-m", "src.main"]
