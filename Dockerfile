# =============================================================
# Stage 1: Build React frontend
# =============================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Copy package files first for layer caching
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Copy source and build
COPY frontend/ ./
RUN npm run build


# =============================================================
# Stage 2: Python runtime
# =============================================================
FROM python:3.11-slim AS runtime

# Prevent .pyc files; enable real-time log output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    FBA_UI_MODE=react

WORKDIR /app

# Install Python dependencies (cached layer before copying source)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY src/ ./src/

# Copy built React assets from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Non-root user for security
RUN addgroup --system fba && adduser --system --ingroup fba fba
USER fba

EXPOSE 8080

# 2 workers sufficient for shared-cpu-1x 256MB
# 120s timeout covers slow Yahoo API calls
CMD ["gunicorn", \
     "--bind", "0.0.0.0:8080", \
     "--workers", "2", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "fba.app:app"]
