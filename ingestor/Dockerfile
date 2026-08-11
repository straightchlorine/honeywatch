FROM python:3.14-slim@sha256:d7a925f9eb9639a93e455b9f12c167569358818c0f62b51b88edbc8fcf34c421

COPY --from=ghcr.io/astral-sh/uv:0.11.12@sha256:3a59a3cdd5f7c217faa36e32dbc7fddbb0412889c2a0a5229f6d790e5a019dd7 /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ src/
RUN uv sync --frozen --no-dev

# Drop uv binary to remove vendored Rust deps from image scans.
RUN rm -f /bin/uv /bin/uvx && rm -rf /root/.cache/uv

ENV GEOIP_DATA_DIR=/data/geoip

RUN useradd --create-home --shell /bin/bash ingestor \
    && mkdir -p /data/geoip \
    && chown -R ingestor:ingestor /app /data/geoip
USER ingestor

# Avoids uv cache init overhead at runtime.
ENV PATH="/app/.venv/bin:$PATH"

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD sh -c 'test $(( $(date +%s) - $(stat -c %Y /tmp/healthy 2>/dev/null || echo 0) )) -lt 60' || exit 1

CMD ["python", "-m", "src.main"]
