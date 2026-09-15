ARG PYTHON_VERSION=3.12
FROM ghcr.io/astral-sh/uv:python${PYTHON_VERSION}-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends less bash zsh \
    && rm -rf /var/lib/apt/lists/*
ENV UV_CACHE_DIR=/tmp/uv-cache UV_PROJECT_ENVIRONMENT=/tmp/audit-venv
# Non-root is necessary for meaningful unreadable-file tests.
USER 65534:65534
WORKDIR /tmp
