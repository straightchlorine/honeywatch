FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN groupadd -r honeywatch && useradd -r -g honeywatch honeywatch

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN chown -R honeywatch:honeywatch /app

USER honeywatch

EXPOSE 5000

ENTRYPOINT ["/entrypoint.sh"]
