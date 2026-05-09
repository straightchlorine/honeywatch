FROM python:3.13-slim@sha256:a0779d7c12fc20be6ec6b4ddc901a4fd7657b8a6bc9def9d3fde89ed5efe0a3d

COPY --from=ghcr.io/astral-sh/uv:0.11.12@sha256:3a59a3cdd5f7c217faa36e32dbc7fddbb0412889c2a0a5229f6d790e5a019dd7 /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ src/
RUN uv sync --frozen --no-dev

RUN useradd --create-home --shell /bin/bash ingestor && chown -R ingestor:ingestor /app
USER ingestor

# Use the prebuilt venv directly at runtime; avoids uv cache init at start.
ENV PATH="/app/.venv/bin:$PATH"

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD sh -c 'test $(( $(date +%s) - $(stat -c %Y /tmp/healthy 2>/dev/null || echo 0) )) -lt 60' || exit 1

CMD ["python", "-m", "src.main"]
