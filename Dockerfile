# Pressure Index: production image (React build served by FastAPI).
#
# The analytics pipeline (main.py) is NOT run here. The image ships the outputs
# it already produced: data/processed/analytics.duckdb and outputs/metrics.json.
# After re-running `python main.py` locally, commit those two files and redeploy.

# ---- 1. build the React frontend ------------------------------------------------
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npx vite build

# ---- 2. runtime: FastAPI + DuckDB -----------------------------------------------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000
WORKDIR /app

# Apply Debian security updates (e.g. zlib) on top of the base image.
RUN apt-get update \
 && apt-get upgrade -y --no-install-recommends \
 && rm -rf /var/lib/apt/lists/*

# Install runtime deps, then remove pip/setuptools/wheel: they are only needed
# at build time and carry their own CVEs.
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt \
 && pip uninstall -y pip setuptools wheel || true

COPY backend/ backend/
COPY data/processed/analytics.duckdb data/processed/analytics.duckdb
COPY outputs/metrics.json outputs/metrics.json
COPY --from=web /web/dist frontend/dist

RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
# Render (and most hosts) inject $PORT; default to 8000 locally.
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
