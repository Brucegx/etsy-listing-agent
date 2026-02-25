# Build context: repo root (set via docker-compose `context: .`)
#
# ── Stage 1: dependency builder ───────────────────────────────────────────────
FROM python:3.11-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /build

# Copy the root engine package (local editable dep of the backend)
COPY pyproject.toml uv.lock ./
COPY src/ ./src/

# Copy backend package files
COPY backend/pyproject.toml backend/uv.lock ./backend/

# Create venv and install all backend deps.
# We install the root engine package as a regular wheel first, then the backend.
RUN uv venv /venv --python python3.11
RUN uv pip install --python /venv/bin/python .
RUN uv pip install --python /venv/bin/python ./backend

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copy the installed virtualenv from the builder stage
COPY --from=builder /venv /venv

# Copy backend application source
COPY backend/app ./app

# Activate the virtualenv
ENV PATH="/venv/bin:$PATH"
ENV PYTHONPATH="/app"

# Runtime data directories — these will be bind-mounted as Docker volumes
RUN mkdir -p /data/storage

# Sensible defaults (all overridden via docker-compose environment / .env)
ENV DATABASE_URL="sqlite:////data/etsy_agent.db"
ENV STORAGE_PATH="/data/storage"
ENV LOG_LEVEL="info"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
