# ---------------------------------------------------------------------------
# METRASIGHT — single-service production image (see docs/deployment.md).
#
# Stage 1 builds the web client (npm workspaces monorepo → vite dist/).
# Stage 2 runs the FastAPI backend, which serves both the API (under /api/v1)
# and the built SPA (STATIC_DIST_DIR) from one origin on 0.0.0.0:$PORT.
#
# SQLite DB, uploaded storage and the PaddleOCR model cache live wherever the
# environment points them — /tmp/metrasight (ephemeral, Render Free default,
# re-seeded each cold start) or a mounted persistent disk on paid plans.
# ---------------------------------------------------------------------------
FROM node:20-bookworm-slim AS web-build

WORKDIR /build
# Workspace manifests first for layer caching, then sources.
COPY package.json package-lock.json tsconfig.base.json ./
COPY packages ./packages
COPY apps/web ./apps/web
RUN npm ci
RUN npm run build:web

# ---------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# opencv-contrib-python (runtime vision/decode) needs libGL/libglib;
# libgomp1 is required by paddlepaddle's CPU kernels.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/api
COPY services/api/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY services/api/app ./app

# Built web client from stage 1; the API serves it when STATIC_DIST_DIR is set.
COPY --from=web-build /build/apps/web/dist /srv/web
ENV STATIC_DIST_DIR=/srv/web

# Render injects PORT (default 10000). Bind 0.0.0.0 — never localhost.
EXPOSE 10000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
