# Stage 1: Build frontend
FROM node:22-alpine AS frontend-builder
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --frozen-lockfile
COPY frontend/ ./
RUN npm run build

# Stage 2: Python dependencies (wheels)
FROM python:3.12-alpine AS backend-deps
WORKDIR /build/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 3: Production image
FROM python:3.12-alpine
LABEL org.opencontainers.image.title="JellyNews"
LABEL org.opencontainers.image.description="Self-hosted newsletter service for Jellyfin"
LABEL org.opencontainers.image.licenses="MIT"

RUN addgroup -S jellynews && adduser -S jellynews -G jellynews

RUN mkdir -p /app /app/static /app/data && \
    chown -R jellynews:jellynews /app

WORKDIR /app

COPY --from=backend-deps /root/.local /home/jellynews/.local
COPY --from=frontend-builder /build/frontend/dist /app/static
COPY backend/ /app/
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

ENV PATH="/home/jellynews/.local/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

USER jellynews
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/healthz').raise_for_status()"

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
