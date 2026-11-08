# RoboTaste — container image for server deployment (e.g. a university VM).
# Pumpless / hand-served mode only: the pump service needs local USB serial
# hardware and is not run in the container.
#
#   docker build -t robotaste .
#   docker run -d --name robotaste -p 8000:8000 \
#       -v /srv/robotaste:/data \
#       -e ROBOTASTE_PASSWORD=change-me \
#       -e ROBOTASTE_PUBLIC_URL=https://robotaste.example.ac.il \
#       robotaste
#
# See docs/DEPLOYMENT.md.

# ── Stage 1: build the React frontend ──────────────────────────────────────
FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python runtime (FastAPI serves API + built frontend) ─────────
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ROBOTASTE_DB_PATH=/data/robotaste.db
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=frontend /app/frontend/dist ./frontend/dist

RUN useradd --create-home --uid 1000 robotaste \
    && mkdir -p /data /app/logs \
    && chown -R robotaste:robotaste /data /app/logs
USER robotaste

VOLUME ["/data"]
EXPOSE 8000

# Single worker: SQLite is the shared state and needs one writer process.
# --proxy-headers lets uvicorn honour X-Forwarded-Proto from nginx/Caddy.
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
