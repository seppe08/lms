# Multi-stage production build for LMS API
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv from official binary
COPY --from=ghcr.io/astral-sh/uv:0.6.5 /uv /uvx /bin/

# Copy lockfile and dependency specifications
COPY pyproject.toml uv.lock ./

# Install dependencies into virtualenv without dev packages
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
RUN uv sync --frozen --no-dev --no-install-project


# Production runner image
FROM python:3.12-slim AS runner

WORKDIR /app

# Security: run as non-root user
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/sh -M appuser

# Copy virtual environment from builder stage
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copy application assets
COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY app/ ./app/

# Set file ownership
RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health')" || exit 1

CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000", "-w", "2", "app.main:app"]
