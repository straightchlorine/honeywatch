FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928

COPY --from=ghcr.io/astral-sh/uv:0.11.12@sha256:3a59a3cdd5f7c217faa36e32dbc7fddbb0412889c2a0a5229f6d790e5a019dd7 /uv /uvx /bin/

RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

RUN groupadd -r honeywatch && useradd -r -g honeywatch -d /home/honeywatch -m honeywatch

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

# Keeping Rust uv deps out of scans
RUN rm -f /bin/uv /bin/uvx && rm -rf /root/.cache/uv

# The venv is prebuilt and nothing installs at runtime.
# Images bundled stuff contribute to CVE scan.
RUN rm -rf /usr/local/lib/python3.*/site-packages/pip \
    /usr/local/lib/python3.*/site-packages/pip-* \
    /usr/local/lib/python3.*/site-packages/setuptools \
    /usr/local/lib/python3.*/site-packages/setuptools-* \
    /usr/local/lib/python3.*/site-packages/pkg_resources \
    /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.*

RUN chown -R honeywatch:honeywatch /app

USER honeywatch

# Use the prebuilt venv directly at runtime; avoids uv cache init at start.
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health').read()" || exit 1

ENTRYPOINT ["gunicorn", "-c", "gunicorn.conf.py", "src.app:create_app()"]
