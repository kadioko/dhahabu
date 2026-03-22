# ── Build stage: frontend ─────────────────────────────────────────────────────
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --prefer-offline

COPY frontend/ .
RUN npm run build


# ── Runtime stage: Python backend ─────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[dev]" || pip install --no-cache-dir \
    fastapi uvicorn[standard] sqlalchemy[asyncio] alembic asyncpg psycopg2-binary \
    apscheduler httpx aiohttp tenacity pandas numpy scipy \
    pydantic pydantic-settings python-dotenv python-telegram-bot \
    structlog rich python-dateutil pytz orjson cachetools

# Copy application
COPY backend/ ./backend/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Copy built frontend
COPY --from=frontend-builder /app/frontend/dist ./backend/static

# FastAPI serves static files from /backend/static
# Add static file serving to the main app
RUN mkdir -p backend/static

# Create non-root user
RUN useradd -m -u 1001 dhahabu && chown -R dhahabu:dhahabu /app
USER dhahabu

EXPOSE 8000

# Run migrations then start server
CMD ["sh", "-c", "alembic upgrade head && uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
