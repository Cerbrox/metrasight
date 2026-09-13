# Deployment (Render)

How the METRASIGHT prototype is deployed to a public HTTPS URL for SIH
judges — without changing any application logic.

Two supported targets, same single-service Docker architecture:

| | **Render Free ($0)** — prototype/demo | **Render Standard + disk** — persistent |
| --- | --- | --- |
| RAM / CPU | 512 MB / 0.1 CPU | 2 GB / 2 CPU |
| Persistent disk | ❌ none (ephemeral `/tmp`) | ✅ `/var/data` |
| Data lifetime | lost on every cold start / redeploy | survives restarts & redeploys |
| Sleep | spins down after ~15 min idle (~50s+ cold start) | always on |
| First DEMO-FOOD after boot | re-seeded via real OCR, several minutes on 0.1 CPU | once ever (then instant) |
| Use for | SIH judge demo, QR-code link | anything beyond a demo |

The current `render.yaml` in this repository is configured for **Render
Free**. The persistent-disk variant is documented in
[§ The persistent variant](#the-persistent-variant-standard--disk) below.

Architecture (identical in both):

```
Browser ──HTTPS──> Render web service (Docker)
                    ├── /api/v1/*      FastAPI (JWT + RBAC, unchanged)
                    ├── /assets/*      built SPA static files
                    └── /*             SPA shell (client-side routing)
                    data root (disk on paid · /tmp/metrasight on Free):
                    ├── legalmet.db        SQLite database
                    ├── storage/           uploaded package/evidence images
                    └── .paddlex/          PP-OCRv5 model cache
```

Why one service: the frontend's API client already defaults to the relative
base `/api/v1` (`VITE_API_BASE_URL`), and every protected image/report is
fetched with the bearer token as a Blob (`fetchObjectUrl`,
`api.exportReport`) — same-origin serving keeps all of that working with
**no CORS configuration and no public storage**, exactly as in local dev.

## Render Free deploy ($0)

> **Read this first — Free is a prototype tier, not infrastructure.**
>
> - The filesystem is **ephemeral**: the SQLite database, uploaded evidence
>   and generated reports are wiped on every cold start, restart and
>   redeploy. Nothing user-generated survives.
> - The service **sleeps after ~15 minutes without traffic**; the next
>   request pays a ~50s+ cold start, after which DEMO-FOOD is **re-seeded
>   through the real OCR engine** — on the Free tier's 0.1 CPU that takes
>   several minutes (watch logs for `demo_inspections_seeded`). Until then
>   the app is live but the demo inspection list is empty.
> - 512 MB RAM is at the edge of what PaddlePaddle CPU inference needs.
>   `render.yaml` caps the footprint (`PERCEPTION_OCR_CPU_THREADS=1`,
>   `PERCEPTION_OCR_ENABLE_MKLDNN=false`), but an OOM during OCR is still
>   possible on Free. **The OCR is never mocked or faked** — if memory does
>   not fit, the fix is a bigger instance, not fake results.
> - Free services share 750 instance-hours/month; one always-awake service
>   ≈ a full month.
> - This is **NOT production infrastructure**. A real deployment needs
>   persistent managed storage/database (see the persistent variant below,
>   and the PostgreSQL upgrade note at the end).

Steps:

1. Push this repository to GitHub (the `render.yaml` blueprint must be on
   the default branch).
2. <https://dashboard.render.com> → **New** → **Blueprint** → select the
   repo. Render proposes one service (`metrasight`, plan **Free**).
3. **Apply**. First build takes several minutes (PaddlePaddle wheels). The
   service binds its port in seconds and passes the health check
   (`DEFER_HEAVY_STARTUP` defers the OCR work), then seeds DEMO-FOOD in the
   background — check **Events/Logs** for `demo_inspections_seeded`.
4. **Demo-day tip:** ping `https://<service>.onrender.com/api/v1/health`
   every ~10 minutes (any uptime pinger) for the hours you need the demo
   awake — this prevents the 15-minute sleep and keeps the seeded data warm.

## Environment variables (Render Free)

| Key | Value | Notes |
| --- | --- | --- |
| `ENVIRONMENT` | `production` | |
| `DATABASE_URL` | `sqlite:////tmp/metrasight/legalmet.db` | ephemeral; four slashes = absolute path |
| `STORAGE_DIR` | `/tmp/metrasight/storage` | ephemeral evidence/package image store |
| `PADDLE_PDX_CACHE_HOME` | `/tmp/metrasight/.paddlex` | PP-OCRv5 models re-downloaded (~20 MB) each cold start |
| `SECRET_KEY` | generated | Render `generateValue` — never committed |
| `DEFER_HEAVY_STARTUP` | `true` | bind port first, seed in background |
| `SEED_DEMO_DATA` / `SEED_REGULATORY_DATA` / `SEED_COMPLIANCE_RULES` / `SEED_DEMO_INSPECTIONS` | `true` | demo dataset (re-seeds every cold start) |
| `DEMO_INSPECTION_REFS` | `DEMO-FOOD` | the judge-demo inspection |
| `PERCEPTION_OCR_BACKEND` | `paddle` | real OCR (never the mock) |
| `PERCEPTION_OCR_CPU_THREADS` | `1` | memory cap for 512 MB |
| `PERCEPTION_OCR_ENABLE_MKLDNN` | `false` | memory cap for 512 MB |
| `PERCEPTION_OCR_TIMEOUT_SECONDS` | `900` | 0.1 CPU inference is slow |

`CORS_ORIGINS` is intentionally left at its localhost default: the deployed
frontend talks to the same origin, so no cross-origin request ever happens.
Set it only if you later split the frontend onto its own domain.

## Demo credentials

The seeded demo accounts (clearly-labelled demo values, already in
`services/api/.env.example`):

- Inspector: `inspector@legalmet.local` / `changeme-inspector`
- Admin: `admin@legalmet.local` / `changeme-admin`

## The persistent variant (Standard + disk)

To keep data across restarts (paid): change the service to **Standard
(2 GB RAM)** in Render, attach a **5 GB disk at `/var/data`**, and switch the
three data env vars to `sqlite:////var/data/legalmet.db`,
`/var/data/storage`, `/var/data/.paddlex`. Everything else is identical;
the seed runs once and later boots take seconds (`DEMO-FOOD=already-present`).
Standard is also the comfortable RAM level for PaddleOCR.

## Redeploy after future pushes

```bash
git push origin main          # autoDeploy=true → Render rebuilds + redeploys
```

Manual: Render Dashboard → `metrasight` → **Manual Deploy** → **Deploy
latest commit**.

## Notes & limitations

- **SQLite is kept** (least-risk for the hackathon prototype). On Free it is
  re-created on every cold start. PostgreSQL remains the documented
  production upgrade — set `DATABASE_URL` to a `postgresql+psycopg2://…` URL
  (the driver is already installed) and run Alembic; no code change needed.
- **The demo reset scripts** (`scripts/reset-demo.sh` / `.ps1`,
  `npm run reset:demo`) operate on the paths from the environment — they
  work against the local dev layout and make no persistent-disk assumption.
- Protected endpoints (inspections, evidence, storage, reports, analytics)
  still return 401/403 without a valid token; citizen endpoints stay
  public-by-design. Nothing was opened up for the deployment.
- `/docs` (Swagger) remains public — it exposes API shapes only, all
  endpoints still require auth.
- On Free, an interactive citizen scan (upload + real OCR in-request) may
  exceed the platform's request timeout on the 0.1 CPU instance; the
  inspector pipeline seeds and analyzes in the background and is not
  request-timeout-bound.
