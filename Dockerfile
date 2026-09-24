ARG PYTHON_IMAGE=3.14.7-slim

FROM ghcr.io/astral-sh/uv:0.12.18 AS uv-base

FROM python:${PYTHON_IMAGE} AS builder

WORKDIR /app

ENV UV_PYTHON_DOWNLOADS=0 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_LOCKED=1

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=from=uv-base,source=/uv,target=/bin/uv \
    uv sync --no-dev

FROM python:${PYTHON_IMAGE} AS final

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY manage.py .
COPY pixel_backup pixel_backup
COPY history history

ENV PATH="/app/.venv/bin:$PATH"

ENTRYPOINT []

CMD ["python", "manage.py", "runbolt", "--processes", "1"]
