# Multi-stage application image (§3.13). Build args from versions.env via Compose.
ARG PYTHON_IMAGE=python:3.12.13-slim-bookworm

FROM ${PYTHON_IMAGE} AS builder

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY src ./src
COPY configs ./configs
COPY scripts/__init__.py ./scripts/__init__.py

RUN uv sync --locked --no-dev

FROM ${PYTHON_IMAGE} AS runtime

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 --create-home appuser

WORKDIR /app

COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appuser /app/src /app/src
COPY --from=builder --chown=appuser:appuser /app/configs /app/configs
COPY --from=builder --chown=appuser:appuser /app/scripts/__init__.py /app/scripts/__init__.py

ENV PATH="/app/.venv/bin:${PATH}"

USER appuser
