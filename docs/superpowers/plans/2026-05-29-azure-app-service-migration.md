# Azure App Service Migration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-bw:subagent-driven-development (recommended) or superpowers-bw:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the Building Stock Energy Estimation app from Railway to a single Azure App Service with Easy Auth (Microsoft Entra ID) for zero-code authentication.

**Architecture:** Single Azure App Service (Linux, Python 3.11) serving both the FastAPI API and the Vue SPA static files from the same origin. XGBoost models (~5.4 GB, ~3,895 files) stored in Azure Blob Storage, downloaded to App Service persistent storage on startup. Easy Auth configured at the platform level — no auth code in the application. CORS eliminated by same-origin deployment.

**Tech Stack:**
- Azure App Service (B1 Linux, ~$13/mo)
- Azure Blob Storage (model files)
- Azure Easy Auth + Microsoft Entra ID
- gunicorn + uvicorn (ASGI worker)
- FastAPI `StaticFiles` mount for Vue SPA

**Dependencies to Install:**
- `gunicorn` — ASGI server for production (replaces bare uvicorn)
- `azure-storage-blob` — Replace boto3/S3 model download with Azure Blob SDK
- `azure-identity` — DefaultAzureCredential for managed identity access to Blob Storage (optional, can use connection string)

**Azure References:**
- [App Service Easy Auth: Configure Entra ID](https://learn.microsoft.com/en-us/azure/app-service/configure-authentication-provider-aad)
- [Deploy Python FastAPI to App Service Linux](https://learn.microsoft.com/en-us/azure/app-service/quickstart-python)
- [App Service Persistent Storage](https://learn.microsoft.com/en-us/azure/app-service/configure-custom-container?pivots=container-linux#use-persistent-shared-storage)
- [Easy Auth Architecture (sidecar)](https://learn.microsoft.com/en-us/azure/app-service/overview-authentication-authorization)
- [Restrict app to assigned users](https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/assign-user-or-group-access-portal)

---

## Relevant Files

### Modify
- `backend/app/main.py` — Add StaticFiles mount for Vue dist, adjust CORS for single-origin
- `backend/download_models.py` — Replace Railway S3 (boto3) with Azure Blob Storage SDK
- `backend/requirements.txt` — Add gunicorn, azure-storage-blob; remove boto3
- `backend/Dockerfile` — Update for combined deployment (copy frontend dist, install gunicorn)
- `backend/start.sh` — Switch from bare uvicorn to gunicorn with uvicorn workers
- `frontend/vite.config.js` — Set `base` option and API proxy for local dev
- `docker-compose.yml` — Update for single-service local dev

### Create
- `backend/app/middleware/auth_headers.py` — Optional: parse Easy Auth `X-MS-CLIENT-PRINCIPAL` headers into request state for downstream use
- `infra/` — Azure resource definitions (Bicep or az CLI scripts) for App Service + Blob Storage + Entra app registration

### Keep Unchanged (Railway compatibility)
- All composables (`useAssessment.js`, `useProjects.js`, etc.) — `VITE_API_URL` stays, but defaults to `''` (same-origin) instead of `localhost:8001`
- All backend services, schemas, models, tests — no changes needed

---

## Notes

- **Model storage is the main complexity.** The XGB_Models directory is 5.4 GB. App Service B1 has 10 GB disk, so models fit, but startup download time matters. Consider using App Service persistent storage (`/home` mount) so models survive restarts.
- **Easy Auth injects identity headers** (`X-MS-CLIENT-PRINCIPAL-NAME`, `X-MS-CLIENT-PRINCIPAL-ID`, `X-MS-CLIENT-PRINCIPAL`) into every authenticated request. The app doesn't need to validate tokens — the platform does it. Optionally parse these headers to show user info in the UI.
- **The frontend build must set `VITE_API_URL=""`** (empty string) so all API calls use relative paths (same origin). This is already done in the frontend Dockerfile.
- **The nginx reverse proxy is eliminated.** Currently nginx serves the SPA and proxies `/assess`, `/lookup`, etc. to the backend. In the single-service model, FastAPI serves everything directly.
- **Local dev still works.** Run backend on :8001 and frontend on :5173 separately with `VITE_API_URL=http://localhost:8001` as before.
- **Railway can stay running** as a fallback during migration. No destructive changes to the Railway deployment.
- **SPA routing:** FastAPI needs a catch-all route that serves `index.html` for any path not matching an API route, so browser refreshes on SPA routes work.

---

## Tasks

### Task 0: Azure Resource Setup (Portal/CLI)

**Acceptance Criteria:**
- Azure App Service (Linux, Python 3.11, B1 plan) exists and is accessible
- Azure Blob Storage account exists with a container holding the XGB_Models files
- Entra ID app registration exists (auto-created by Easy Auth config)
- Easy Auth is enabled with "Require authentication" and Entra ID as the provider
- Only assigned users/groups can access the app (User assignment required = Yes)

**Sub-tasks:**
- [ ] 0.1 Create Azure Resource Group for the energy audit app
- [ ] 0.2 Create Azure App Service Plan (B1 Linux) and Web App (Python 3.11)
- [ ] 0.3 Create Azure Storage Account + Blob container `xgb-models`
- [ ] 0.4 Upload XGB_Models directory contents to the blob container (use `az storage blob upload-batch`)
- [ ] 0.5 Enable Easy Auth on the App Service: Authentication → Add Microsoft provider → "Require authentication" with HTTP 302 redirect
- [ ] 0.6 On the Entra ID app registration: set "User assignment required" = Yes, assign permitted users/groups
- [ ] 0.7 Configure App Service environment variables: `MODEL_DIR=/home/models`, blob storage connection string, `WEBSITES_PORT=8001`
- [ ] 0.8 Enable persistent storage: set `WEBSITES_ENABLE_APP_SERVICE_STORAGE=true` so `/home` survives restarts

**Dependencies:** None

---

### Task 1: Adapt Model Download for Azure Blob Storage

**Files:**
- Modify: `backend/download_models.py`
- Modify: `backend/requirements.txt`

**Acceptance Criteria:**
- `download_models.py` downloads from Azure Blob Storage instead of Railway S3
- Version-checking logic (`MODEL_BUNDLE_VERSION`) still works identically
- Falls back gracefully if blob credentials aren't set (local dev without Azure)
- Existing Railway S3 download path is preserved behind an env var switch OR removed (user choice)

**Constraints:**
- Use `azure-storage-blob` SDK with `BlobServiceClient`
- Keep the same marker file logic (`.models_downloaded`, `.models_version`)
- Download to `MODEL_DIR` (defaults to `/home/models` on Azure, `../../XGB_Models` locally)

**Sub-tasks:**
- [ ] 1.1 Add `azure-storage-blob` to `requirements.txt`, remove `boto3` (or keep both behind a flag)
- [ ] 1.2 Rewrite download function to use `ContainerClient.list_blobs()` + `download_blob()` instead of boto3 paginator
- [ ] 1.3 Preserve version-check and cache-clear logic
- [ ] 1.4 Test locally by setting `AZURE_STORAGE_CONNECTION_STRING` and pointing at the real blob container

**Dependencies:** Task 0 (blob container must exist with uploaded models)

---

### Task 2: FastAPI Serves the Vue SPA

**Files:**
- Modify: `backend/app/main.py`
- Modify: `frontend/vite.config.js`

**Acceptance Criteria:**
- FastAPI serves the Vue `dist/` directory as static files
- Requests to `/assets/*` serve the Vite-built JS/CSS/images
- Requests to any non-API path return `index.html` (SPA catch-all)
- API routes (`/assess`, `/health`, `/lookup`, `/autocomplete`, `/metadata`, `/offload`, `/projects/*`, `/bps/*`, `/energy-star/*`) still work
- Local development workflow is unaffected (frontend dev server + backend dev server)

**Constraints:**
- Mount `StaticFiles` at `/assets` for hashed Vite assets
- Add a catch-all route AFTER all API routers that returns `index.html`
- The `dist/` path should be configurable via env var (`STATIC_DIR`) with a sensible default
- CORS middleware can be removed (same origin) or narrowed to only allow the dev server origin

**Sub-tasks:**
- [ ] 2.1 Add `StaticFiles` mount in `main.py` for `/assets` pointing to `dist/assets/`
- [ ] 2.2 Add a catch-all GET route that returns `dist/index.html` via `FileResponse`
- [ ] 2.3 Make the dist path configurable: `STATIC_DIR` env var, default to `None` (skip mount if not set, for local dev)
- [ ] 2.4 Update CORS to allow only the Vite dev server origin when `STATIC_DIR` is not set
- [ ] 2.5 Update `frontend/vite.config.js` to proxy API requests to `localhost:8001` during dev (optional, for DX)

**Dependencies:** None

---

### Task 3: Unified Dockerfile

**Files:**
- Modify: `backend/Dockerfile`
- Modify: `backend/start.sh`

**Acceptance Criteria:**
- Single Dockerfile builds both the frontend (Vite) and backend (FastAPI)
- Frontend `dist/` is copied into the backend image at a known path
- Container starts with gunicorn + uvicorn workers
- Container exposes port 8001
- `download_models.py` runs before the server starts (same as Railway)
- `STATIC_DIR` env var points to the copied dist directory

**Constraints:**
- Multi-stage build: Node stage builds frontend, Python stage runs backend
- gunicorn command: `gunicorn -w 2 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8001 app.main:app`
- Keep the image slim (python:3.11-slim base)

**Sub-tasks:**
- [ ] 3.1 Add `gunicorn` to `backend/requirements.txt`
- [ ] 3.2 Create multi-stage Dockerfile: stage 1 (node:20-alpine) builds frontend, stage 2 (python:3.11-slim) copies dist + runs backend
- [ ] 3.3 Update `start.sh` to use gunicorn with uvicorn workers
- [ ] 3.4 Set `STATIC_DIR=/app/static` in Dockerfile and copy `dist/` there
- [ ] 3.5 Build and test locally: `docker build -t energy-audit . && docker run -p 8001:8001 -v ./XGB_Models:/home/models energy-audit`

**Dependencies:** Task 2 (FastAPI must be configured to serve static files)

---

### Task 4: Optional — Parse Easy Auth Identity Headers

**Files:**
- Create: `backend/app/middleware/auth_headers.py`
- Modify: `backend/app/main.py`

**Acceptance Criteria:**
- A FastAPI middleware or dependency parses `X-MS-CLIENT-PRINCIPAL-NAME` and `X-MS-CLIENT-PRINCIPAL` headers
- User email/name is available in request state for any route that wants it
- When headers are absent (local dev), user info is `None` — no errors
- No token validation logic (Easy Auth handles that)

**Constraints:**
- `X-MS-CLIENT-PRINCIPAL` is Base64-encoded JSON with claims
- Keep this lightweight — it's optional context, not a security gate
- Don't block requests when headers are missing

**Sub-tasks:**
- [ ] 4.1 Create middleware that decodes `X-MS-CLIENT-PRINCIPAL` and sets `request.state.user`
- [ ] 4.2 Add middleware to `main.py`
- [ ] 4.3 Verify locally by passing fake headers (these headers are stripped by Easy Auth in production, so they're safe to test with)

**Dependencies:** None (but only useful after Easy Auth is configured in Task 0)

---

### Task 5: Deploy and Verify

**Acceptance Criteria:**
- App is deployed to Azure App Service and accessible at `https://<app-name>.azurewebsites.net`
- Unauthenticated users are redirected to Microsoft login
- Authenticated users see the full Vue SPA and can run assessments
- Models download on first startup and are cached on persistent storage
- Subsequent restarts skip the model download
- API endpoints all function correctly (assess, lookup, autocomplete, projects, etc.)

**Sub-tasks:**
- [ ] 5.1 Push Docker image to Azure Container Registry (or use App Service built-in build from Git)
- [ ] 5.2 Configure App Service to use the container image
- [ ] 5.3 Verify Easy Auth redirects unauthenticated requests to Entra login
- [ ] 5.4 Verify authenticated requests reach the app with identity headers
- [ ] 5.5 Run a full assessment through the UI to confirm end-to-end functionality
- [ ] 5.6 Verify model caching: restart the app, confirm models are not re-downloaded
- [ ] 5.7 Test with a non-assigned user to verify they are blocked

**Dependencies:** Tasks 0, 1, 2, 3

---

### Task 6: Update Frontend API Base URL Default

**Files:**
- Modify: `frontend/src/composables/useAssessment.js`
- Modify: `frontend/src/composables/useProjects.js`
- Modify: `frontend/src/composables/useAddressLookup.js`
- Modify: `frontend/src/composables/useAddressAutocomplete.js`
- Modify: `frontend/src/composables/useEnergyStarScore.js`
- Modify: `frontend/src/composables/useBpsSearch.js`
- Modify: `frontend/src/composables/useMeasureSelections.js`

**Acceptance Criteria:**
- All composables default `API_BASE` to `''` (empty string = same origin) instead of `http://localhost:8001`
- `VITE_API_URL` env var still overrides for local development
- No functional change when `VITE_API_URL` is set

**Constraints:**
- One-line change per file: `const API_BASE = import.meta.env.VITE_API_URL ?? ''`
- Local dev instructions should note: set `VITE_API_URL=http://localhost:8001` in `.env`

**Sub-tasks:**
- [ ] 6.1 Update all 7 composables to default to `''`
- [ ] 6.2 Create `frontend/.env.development` with `VITE_API_URL=http://localhost:8001` so local dev works automatically
- [ ] 6.3 Verify local dev still works with separate frontend/backend servers

**Dependencies:** None

---

## Reminders

- **TDD:** Write failing tests for all logic — conditionals, data transforms, error handling, integration points, edge cases. Prompt text and truly static config are verified by inspection, not tests.
- **Commit:** Commit after completing each task
- **Source of truth:** This plan defines requirements — refer to it when making judgment calls
- **Update this plan:** Check off completed tasks (`- [x]`) after each task is done
- **Railway stays running** until Azure deployment is verified end-to-end
