FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /uvx /bin/

RUN groupadd -r honeywatch && useradd -r -g honeywatch -d /home/honeywatch -m honeywatch

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN chown -R honeywatch:honeywatch /app

USER honeywatch

# Use the prebuilt venv directly at runtime. No `uv run` needed, which
# avoids uv trying to init a cache dir at startup.
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health').read()" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
