FROM python:3.14-alpine AS builder

WORKDIR /app

ENV UV_PYTHON_DOWNLOADS=0 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_LOCKED=1

COPY src src

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=from=ghcr.io/astral-sh/uv:latest,source=/uv,target=/bin/uv \
    uv sync --no-dev

FROM python:3.14-alpine

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

ENV PATH="/app/.venv/bin:$PATH"

ENTRYPOINT []

CMD ["pixel-backup", "--permanent"]
