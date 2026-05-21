# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: Build React frontend
# Uses full Node image (not alpine) to avoid build-tool compatibility issues
# ─────────────────────────────────────────────────────────────────────────────
FROM node:22.16.0 AS frontend-builder

WORKDIR /app/frontend

# Increase Node heap to avoid OOM on large dependency trees
ENV NODE_OPTIONS="--max-old-space-size=2048"

COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
RUN npm run build


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: Production image
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-alpine

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# wget for health checks; SQLite is bundled in Python's stdlib on alpine
RUN apk add --no-cache wget

WORKDIR /app

# Install Python dependencies
# Build deps (gcc etc.) are needed only at install time — removed afterwards
COPY requirements.txt .
RUN apk add --no-cache --virtual .build-deps \
        gcc \
        musl-dev \
        libffi-dev \
        openssl-dev \
    && pip install --no-cache-dir -r requirements.txt \
    && apk del .build-deps

# Note: Selenium mode is NOT supported in this image (requires Chrome).
# Use the default requests-based scraper, which needs no browser.

# Non-root user
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

# Copy application code
COPY backend/      ./backend/
COPY fgt_upgrade/  ./fgt_upgrade/

# Copy built frontend (served by FastAPI as static files)
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Create persistent-data directories so named volumes can be mounted here
RUN mkdir -p /app/data /app/uploads

# Ensure appuser can create/write the SQLite database at runtime
RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8000/docs || exit 1

# Run from /app so that `import fgt_upgrade` and `import backend` both resolve
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
