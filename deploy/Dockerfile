# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:0.13.3 AS uv
FROM python:3.12.15-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    HISTORY_AGENT_PROJECT_ROOT=/app

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 start1921 \
    && useradd --uid 10001 --gid 10001 --create-home start1921

COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
# Cache third-party dependencies independently of source changes.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --extra app --extra vector --no-dev --no-install-project

COPY app ./app
COPY config/*.json ./config/
COPY deploy/healthcheck.py ./deploy/healthcheck.py
# Keep the editable package at /app/app/history_agent. Settings also explicitly
# points at /app so config, data and docs retain the repository layout.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --extra app --extra vector --no-dev \
    && mkdir -p /app/data /app/docs \
    && chown start1921:start1921 /app/data /app/docs

USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "history_agent.web.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
