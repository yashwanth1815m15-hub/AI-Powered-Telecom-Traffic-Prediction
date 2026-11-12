# Multi-stage single-container image for TeleSense (Railway / Render / Docker)
FROM node:20-alpine AS frontend-builder
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS runtime
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/backend:/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch first to avoid ~2.5 GB CUDA wheels on cloud builders
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu "torch>=2.1.0" && \
    pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend/ /app/backend/
COPY ml/ /app/ml/
COPY artifacts/ /app/artifacts/
COPY docs/PROJECT_GUIDE.pdf /app/docs/PROJECT_GUIDE.pdf
COPY --from=frontend-builder /build/frontend/dist /app/frontend/dist

RUN rm -f /app/backend/.env /app/backend/data/*.db* && \
    mkdir -p /app/backend/data /app/ml/saved_models && \
    chmod -R 777 /app/backend/data /app/ml/saved_models

EXPOSE 8000

CMD ["sh", "-c", "cd /app/backend && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

