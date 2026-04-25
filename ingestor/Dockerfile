FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /uvx /bin/

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
    CMD python -c "import pathlib,sys; sys.exit(0 if 'State:\tR' in pathlib.Path('/proc/1/status').read_text() or 'State:\tS' in pathlib.Path('/proc/1/status').read_text() else 1)" || exit 1

CMD ["python", "-m", "src.main"]
