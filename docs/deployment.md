# Deployment (Render, single service)

How the METRASIGHT prototype is deployed to a public HTTPS URL for SIH
judges — without changing any application logic.

Architecture: **one Docker web service** on Render serves both the built
React SPA and the FastAPI API from a single origin.

```
Browser ──HTTPS──> Render web service (Docker)
                    ├── /api/v1/*      FastAPI (JWT + RBAC, unchanged)
                    ├── /assets/*      built SPA static files
                    └── /*             SPA shell (client-side routing)
                    disk /var/data:
                    ├── legalmet.db        SQLite database
                    ├── storage/           uploaded package/evidence images
                    └── .paddlex/          PP-OCRv5 model cache
```

Why one service: the frontend's API client already defaults to the relative
base `/api/v1` (`VITE_API_BASE_URL`), and every protected image/report is
fetched with the bearer token as a Blob (`fetchObjectUrl`,
`api.exportReport`) — same-origin serving keeps all of that working with
**no CORS configuration and no public storage**, exactly as in local dev.

## What was added

| File | Purpose |
| --- | --- |
| `Dockerfile` | Stage 1: `npm ci` + `vite build` (Node 20). Stage 2: Python 3.11 + `services/api/requirements.txt`, copies the built SPA to `/srv/web`, runs uvicorn on `0.0.0.0:$PORT`. |
| `.dockerignore` | Keeps the build context free of `node_modules`, `.venv`, local DBs, storage, `.git`. |
| `render.yaml` | Render Blueprint: Docker web service, health check `/api/v1/health`, persistent disk at `/var/data`, all values via environment variables. |
| `app/core/config.py` | Two new settings: `STATIC_DIST_DIR` (serve a built SPA; empty = off), `DEFER_HEAVY_STARTUP` (run the OCR-dependent seed + prewarm in a background thread after the port binds). |
| `app/main.py` | Env-gated SPA mount (`_mount_static_site`) and deferred heavy-startup thread. Both are no-ops with default settings — local dev and tests are unchanged. |

Nothing else in the application was modified. Authentication, RBAC, the
rule engine, OCR pipeline, storage auth (`GET /api/v1/storage/{key}` still
requires a bearer token) and the demo seed all run exactly as locally.

## Deploy (Render Dashboard)

1. Push the repository to GitHub (the `render.yaml` blueprint must be on the
   default branch).
2. On <https://dashboard.render.com> → **New** → **Blueprint**, select the
   GitHub repo. Render reads `render.yaml` and proposes one service
   (`metrasight`).
3. Check the plan (**Standard — 2 GB RAM**; PaddleOCR CPU inference will OOM
   on 512 MB instances) and the 5 GB disk, then **Apply**.
4. First deploy: the image build takes several minutes (PaddlePaddle
   wheels). The service then binds its port in seconds (`DEFER_HEAVY_STARTUP`
   is on) and passes the health check; DEMO-FOOD seeding (real OCR + model
   download) finishes in the background — watch the logs for
   `demo_inspection` / `app_startup` lines, roughly 2–5 minutes after
   boot. Subsequent deploys boot in seconds (seed is idempotent and the
   model cache persists on the disk).

Manual equivalent (no blueprint): **New** → **Web Service** → repo →
runtime **Docker** → instance **Standard** → add the same environment
variables from `render.yaml` (generate `SECRET_KEY` yourself, e.g.
`python -c "import secrets; print(secrets.token_urlsafe(48))"`), attach a
disk at `/var/data`, set Health Check Path `/api/v1/health`.

## Environment variables (Render)

| Key | Value | Notes |
| --- | --- | --- |
| `ENVIRONMENT` | `production` | |
| `DATABASE_URL` | `sqlite:////var/data/legalmet.db` | four slashes = absolute path on the disk |
| `STORAGE_DIR` | `/var/data/storage` | evidence/package image store |
| `PADDLE_PDX_CACHE_HOME` | `/var/data/.paddlex` | PP-OCRv5 model cache (paddlex reads this env var) |
| `SECRET_KEY` | generated | Render `generateValue` — never committed |
| `DEFER_HEAVY_STARTUP` | `true` | bind port first, seed in background |
| `SEED_DEMO_DATA` / `SEED_REGULATORY_DATA` / `SEED_COMPLIANCE_RULES` / `SEED_DEMO_INSPECTIONS` | `true` | demo dataset |
| `DEMO_INSPECTION_REFS` | `DEMO-FOOD` | the judge-demo inspection |
| `PERCEPTION_OCR_BACKEND` | `paddle` | real OCR (not the mock) |

`CORS_ORIGINS` is intentionally left at its localhost default: the deployed
frontend talks to the same origin, so no cross-origin request ever happens.
Set it only if you later split the frontend onto its own domain.

## Demo credentials

The seeded demo accounts (clearly-labelled demo values, already in
`services/api/.env.example`):

- Inspector: `inspector@legalmet.local` / `changeme-inspector`
- Admin: `admin@legalmet.local` / `changeme-admin`

## Redeploy after future pushes

```bash
git push origin main          # autoDeploy=true → Render rebuilds + redeploys
```

Manual: Render Dashboard → `metrasight` → **Manual Deploy** → **Deploy
latest commit**. Or with the Render CLI:

```bash
render deploys create <service-id>   # or: render deploys create metrasight
```

## Notes & limitations

- **SQLite is kept** (least-risk for the hackathon prototype). The disk
  makes it persistent across deploys and restarts. PostgreSQL remains the
  documented production upgrade — set `DATABASE_URL` to a
  `postgresql+psycopg2://…` URL (the driver is already installed) and run
  Alembic; no code change is needed.
- First boot after a disk wipe re-seeds and re-downloads OCR models
  (~2–5 min). The API is live during this; DEMO-FOOD appears when the seed
  finishes.
- Protected endpoints (inspections, evidence, storage, reports, analytics)
  still return 401/403 without a valid token; citizen endpoints stay
  public-by-design. Nothing was opened up for the deployment.
- `/docs` (Swagger) remains public — it exposes API shapes only, all
  endpoints still require auth.
- Instance RAM: **Standard (2 GB) or larger.** Free/Starter (512 MB) will
  likely be OOM-killed during PaddleOCR inference.
