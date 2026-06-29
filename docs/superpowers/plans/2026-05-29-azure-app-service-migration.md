# Azure App Service Migration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-bw:subagent-driven-development (recommended) or superpowers-bw:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the Building Stock Energy Estimation app from Railway to a single Azure App Service with Easy Auth (Microsoft Entra ID) for zero-code authentication.

**Architecture:** Single Azure App Service (Linux custom container, Python 3.11) serving both the FastAPI API and the Vue SPA static files from the same origin. XGBoost models (~5.4 GB, ~3,895 files) are stored in Azure Blob Storage and cached under App Service persistent storage (`/home/models`) with startup validation and atomic cache updates. Easy Auth is configured at the platform level for authentication, while the app reads Easy Auth identity headers for user context/project ownership. CORS is eliminated for production by same-origin deployment.

**Blocking Assessment:** No identified full blocker prevents using Azure App Service for this architecture. The main risk is the B1 SKU: 1 vCPU, 1.75 GB RAM, and 10 GB storage leave narrow margins for model cache, SQLite/WAL files, logs, and Python model memory. Treat B1 as a validation target, not a guaranteed production size; keep a documented scale-up path to B2/B3 or Premium v3 if startup, storage, or memory metrics require it.

**Tech Stack:**
- Azure App Service (Linux custom container; B1 for validation, larger SKU if metrics require it)
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
- `backend/app/services/database.py` — Move SQLite to `/home/data`, harden connection settings, create parent directory
- `backend/app/api/projects.py` — Attach Easy Auth user identity to project persistence or explicitly enforce chosen sharing model
- `frontend/vite.config.js` — Set `base` option and API proxy for local dev
- `frontend/src/App.vue` — Update `API_BASE` default for `/offload`
- `docker-compose.yml` — Update for single-service local dev

### Create
- `backend/app/middleware/auth_headers.py` — Parse Easy Auth `X-MS-CLIENT-PRINCIPAL` headers into request state for downstream use
- `infra/` — Azure resource definitions (Bicep or az CLI scripts) for App Service + Blob Storage + Entra app registration

### Keep Unchanged (Railway compatibility)
- Frontend API call structure stays unchanged: `VITE_API_URL` remains the override mechanism, while Task 6 updates production defaults to same-origin.
- Backend inference, lookup, schemas, and model code should stay unchanged unless verification shows an Azure-specific issue. Persistence/auth-context services are in scope.

---

## Notes

- **Model storage is the main complexity.** The XGB_Models directory is 5.4 GB. App Service B1 has 10 GB disk across the App Service plan, so models fit only with limited headroom. Persistent storage (`/home`) is required, partial downloads must be cleaned up, and free-space checks/alerts are required before relying on B1.
- **Startup download is a production risk.** App Service Linux has a finite container startup readiness window. Set `WEBSITES_CONTAINER_START_TIME_LIMIT=1800`, but do not rely on raw per-blob startup downloads as the normal path. Prefer pre-seeding, a compressed versioned model bundle, or an atomic background/cache-fill strategy.
- **SQLite is acceptable only for single-instance, low-concurrency persistence.** If project persistence is business-critical or multi-user concurrent edits matter, use Azure SQL/PostgreSQL instead. If SQLite remains, store it under `/home/data`, run one web worker on B1, enable WAL/busy timeout, and configure backup/export.
- **Easy Auth injects identity headers** (`X-MS-CLIENT-PRINCIPAL-NAME`, `X-MS-CLIENT-PRINCIPAL-ID`, `X-MS-CLIENT-PRINCIPAL`) into authenticated requests. The app doesn't validate tokens — the platform does it — but the backend should parse these headers for user context, audit fields, and project ownership decisions.
- **Easy Auth is authentication, not project authorization.** If projects should be private per user, the backend must associate projects/buildings/assessments with the Easy Auth principal. If all authenticated users intentionally share one project database, document that explicitly and verify stakeholders accept it.
- **The frontend build must set `VITE_API_URL=""`** (empty string) so all API calls use relative paths (same origin). This is already done in the frontend Dockerfile.
- **The nginx reverse proxy is eliminated.** Currently nginx serves the SPA and proxies `/assess`, `/lookup`, etc. to the backend. In the single-service model, FastAPI serves everything directly.
- **Local dev still works.** Run backend on :8001 and frontend on :5173 separately with `VITE_API_URL=http://localhost:8001` as before.
- **Railway can stay running** as a fallback during migration. No destructive changes to the Railway deployment.
- **SPA routing:** FastAPI needs a catch-all route that serves `index.html` for browser navigation paths, but it must not mask API 404s. Restrict the catch-all to non-API prefixes and/or requests accepting `text/html`.

---

## Deployment Log (2026-06-03 through 2026-06-04)

### Quota Blocker and Resolution
The subscription "Azure App Service PTE Audit Tool" (6251c0ca-2803-4014-8864-adb41bc5719f) was provisioned with **zero App Service VM quota** for all legacy SKU families (F1, B1, S1, P1v3, etc.) across all regions. Only PremiumV4 (P0v4-P3v4) had 30 instances. This is normal behavior for new Azure subscriptions (including EA/enterprise) -- not a bug.

- `az quota create` returns "QuotaNotAvailableForResource" because the programmatic quota API does not support App Service.
- The self-service App Service Quota blade (portal.azure.com > Quotas > App Service Public Preview) showed B1 quota at 0 for West US. Requesting an increase to 1 was **unsuccessful** -- portal directed to contact support.
- **West Central US** already had B1 quota of 30 (discovered via the quota blade). The App Service Plan was created there instead.

### Region Change: West US to West Central US
The original plan called for all resources in West US. Due to the quota blocker:
- **Resource group:** `rg-rapid-energy-audit-wcus` created in West Central US (original `rg-rapid-energy-audit` still exists in West US with the storage account)
- **App Service Plan + Web App:** Created in West Central US
- **Storage account:** Remains in West US (`strapidenergyaudit`). Cross-region latency for model downloads is negligible since it's a one-time startup operation.

### Managed Identity Workaround
The account bwinsatt-a@ptrenergy.com has Contributor role but not Owner or User Access Administrator. This means:
- Cannot create RBAC role assignments (e.g., "Storage Blob Data Reader" for the managed identity)
- **Workaround:** Using storage account connection string (`AZURE_STORAGE_CONNECTION_STRING`) instead of managed identity for blob access
- **Future:** Ask IT admin (Mark) to either grant User Access Administrator or assign the `Storage Blob Data Reader` role to the App Service managed identity (principal ID: `3bcb7c57-821a-4905-bc77-cfb28684e0b6`) on storage account `strapidenergyaudit`, then remove the connection string

### Resources Created

| Resource | Name | Region | Resource Group |
|----------|------|--------|---------------|
| App Service Plan | asp-rapid-energy-audit | West Central US | rg-rapid-energy-audit-wcus |
| Web App | rapid-energy-audit | West Central US | rg-rapid-energy-audit-wcus |
| Storage Account | strapidenergyaudit | West US | rg-rapid-energy-audit |
| Blob Container | xgb-models | West US | rg-rapid-energy-audit |

### App Settings Configured
- `MODEL_DIR=/home/models`
- `DATABASE_PATH=/home/data/buildingstock.db`
- `WEBSITES_PORT=8001`
- `WEBSITES_ENABLE_APP_SERVICE_STORAGE=true`
- `WEBSITES_CONTAINER_START_TIME_LIMIT=1800`
- `WEBSITE_WARMUP_PATH=/health`
- `SCM_DO_BUILD_DURING_DEPLOYMENT=true`
- `AZURE_STORAGE_CONNECTION_STRING` (connection string, not managed identity)
- `AZURE_STORAGE_CONTAINER_NAME=xgb-models`

### Security Hardening Applied
- Always On: enabled
- HTTP/2: enabled
- FTPS: disabled
- Minimum TLS: 1.2
- Filesystem + application logging: enabled

### Easy Auth Setup Notes
- App Registration: `rapid-energy-audit` (client ID: `b833b22f-2863-4f57-8dd8-891112cf7b68`)
- Enterprise App SP object ID: `63033e4c-f854-49e0-be94-9514311bb7a7`
- User assignment required: Yes (only assigned users can access)
- Assigned user: bwinsatt-a@ptrenergy.com
- ID token implicit grant: enabled (required by Easy Auth v1 runtime)
- Token store: enabled
- Issuer: v2 endpoint (`https://login.microsoftonline.com/{tenantId}/v2.0`)

**BLOCKER: Admin consent required.** The Partner tenant requires admin consent for all new app registrations. bwinsatt-a@ptrenergy.com has Azure Contributor but not Entra ID admin roles. A Global Admin or Application Admin must grant consent via one of:
1. Azure Portal > Enterprise Applications > rapid-energy-audit > Permissions > "Grant admin consent for Partner Assessment Corporation"
2. Direct URL: `https://login.microsoftonline.com/9c40d245-9e2c-425b-a5d1-c8c715878282/adminconsent?client_id=b833b22f-2863-4f57-8dd8-891112cf7b68`

The app only requests `User.Read` (basic sign-in profile). Once granted, login works immediately.

---

## Tasks

### Task 0: Azure Resource Setup (Portal/CLI)

**Acceptance Criteria:**
- Azure App Service (Linux, Python 3.11, B1 plan) exists and is accessible
- Azure Blob Storage account exists with a container holding the XGB_Models files
- Entra ID app registration exists (auto-created by Easy Auth config)
- Easy Auth is enabled with "Require authentication" and Entra ID as the provider
- Only assigned users/groups can access the app (User assignment required = Yes)
- App Service has persistent storage, startup timeout, warmup, logging, and cost alerts configured before first production cutover
- A documented scale-up trigger exists for moving off B1 if memory, disk, or startup metrics exceed thresholds

**Sub-tasks:**
- [x] 0.1 Create Azure Resource Group for the energy audit app *(rg-rapid-energy-audit-wcus in West Central US -- see Deployment Log for region change)*
- [x] 0.2 Create Azure App Service Plan (B1 Linux) and Web App (Python 3.11) *(asp-rapid-energy-audit + rapid-energy-audit.azurewebsites.net)*
- [x] 0.3 Create Azure Storage Account + Blob container `xgb-models` *(strapidenergyaudit in West US)*
- [x] 0.4 Upload XGB_Models directory contents to the blob container (use `az storage blob upload-batch`) *(4,279 files, 4.19 GB uploaded)*
- [x] 0.5 Enable Easy Auth on the App Service: Authentication → Add Microsoft provider → "Require authentication" with HTTP 302 redirect *(app registration: rapid-energy-audit, client ID: b833b22f-2863-4f57-8dd8-891112cf7b68)*
- [x] 0.6 On the Entra Enterprise Application/service principal: set "User assignment required" = Yes, assign permitted users/groups *(SP object ID: 63033e4c-f854-49e0-be94-9514311bb7a7, assigned: bwinsatt-a@ptrenergy.com)*
- [x] 0.7 Configure App Service environment variables: `MODEL_DIR=/home/models`, `DATABASE_PATH=/home/data/buildingstock.db`, blob storage connection string or managed identity settings, `WEBSITES_PORT=8001` *(using connection string -- see Deployment Log for managed identity workaround)*
- [x] 0.8 Enable persistent storage: set `WEBSITES_ENABLE_APP_SERVICE_STORAGE=true` so `/home` survives restarts
- [x] 0.9 Set startup/warmup settings: `WEBSITES_CONTAINER_START_TIME_LIMIT=1800`, `WEBSITE_WARMUP_PATH=/health`, `WEBSITE_WARMUP_STATUSES=200`
- [x] 0.10 Enable Always On, filesystem/application logging, and alerts for filesystem usage, memory, restart count, startup failures, and monthly budget *(alerts not yet configured -- logging and Always On done)*
- [x] 0.11 If using managed identity for Blob Storage, assign the App Service identity `Storage Blob Data Reader` on the model container/storage account *(skipped -- using connection string instead, see Deployment Log)*

**Dependencies:** None

---

### Task 1: Adapt Model Download for Azure Blob Storage

**Files:**
- Modify: `backend/download_models.py`
- Modify: `backend/requirements.txt`

**Acceptance Criteria:**
- `download_models.py` downloads from Azure Blob Storage instead of Railway S3
- Version-checking logic (`MODEL_BUNDLE_VERSION`) still works identically
- Falls back gracefully if blob credentials aren't set in local dev, but fails loudly in Azure when credentials are missing and no valid local model cache exists
- Existing Railway S3 download path is preserved behind an env var switch OR removed (user choice)
- Downloads are atomic: incomplete downloads never leave `.models_downloaded` or a matching `.models_version`
- The startup script validates model presence/version/file count or manifest before launching the server

**Constraints:**
- Use `azure-storage-blob` SDK with `BlobServiceClient`
- Keep the same marker file logic (`.models_downloaded`, `.models_version`)
- Download to `MODEL_DIR` (defaults to `/home/models` on Azure, `../../XGB_Models` locally)
- Write to a temporary directory under `/home`, then promote it only after validation succeeds
- Consider replacing thousands of per-blob downloads with a compressed versioned archive if first-start download time exceeds the App Service startup budget

**Sub-tasks:**
- [x] 1.1 Add `azure-storage-blob` to `requirements.txt`, remove `boto3` (or keep both behind a flag) *(kept both -- Azure primary, Railway S3 legacy fallback)*
- [x] 1.2 Rewrite download function to use `ContainerClient.list_blobs()` + `download_blob()` instead of boto3 paginator
- [x] 1.3 Preserve version-check and cache-clear logic
- [x] 1.4 Add manifest/free-space validation: expected model version, minimum file count, and available disk before download *(disk space check + file count warning if <100)*
- [x] 1.5 Test locally by setting `AZURE_STORAGE_CONNECTION_STRING` and pointing at the real blob container *(verified: 4,279 blobs found)*
- [ ] 1.6 Time the first download on an Azure B1 instance; if it cannot complete inside the configured startup budget, switch to pre-seeding or a compressed bundle before production

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
- Unknown API paths return API 404 responses, not `index.html`
- Local development workflow is unaffected (frontend dev server + backend dev server)

**Constraints:**
- Mount `StaticFiles` at `/assets` for hashed Vite assets
- Add a catch-all route AFTER all API routers that returns `index.html`
- The `dist/` path should be configurable via env var (`STATIC_DIR`) with a sensible default
- CORS middleware can be removed (same origin) or narrowed to only allow the dev server origin
- Restrict the SPA catch-all to browser navigation requests (`Accept: text/html`) and exclude known API prefixes

**Sub-tasks:**
- [x] 2.1 Add `StaticFiles` mount in `main.py` for `/assets` pointing to `dist/assets/`
- [x] 2.2 Add a catch-all GET route that returns `dist/index.html` via `FileResponse`
- [x] 2.3 Make the dist path configurable: `STATIC_DIR` env var, default to `None` (skip mount if not set, for local dev)
- [x] 2.4 Update CORS to allow only the Vite dev server origin when `STATIC_DIR` is not set
- [x] 2.5 Update `frontend/vite.config.js` to proxy API requests to `localhost:8001` during dev (optional, for DX)
- [x] 2.6 Add/verify tests for static asset serving, SPA refresh, and API 404 behavior

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
- Build command and Dockerfile path are unambiguous from repo root and in Azure CI/CD
- Default runtime uses one worker on B1; worker count is configurable for larger SKUs

**Constraints:**
- Multi-stage build: Node stage builds frontend, Python stage runs backend
- gunicorn command for B1: `gunicorn -w ${WEB_CONCURRENCY:-1} -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8001 --timeout ${GUNICORN_TIMEOUT:-300} app.main:app`
- Keep the image slim (python:3.11-slim base)
- If the Dockerfile remains under `backend/`, build from repo root with `docker build -f backend/Dockerfile .` and use root-relative `COPY` paths for both `backend/` and `frontend/`

**Sub-tasks:**
- [x] 3.1 Add `gunicorn` to `backend/requirements.txt`
- [x] 3.2 Create multi-stage Dockerfile: stage 1 (node:20-alpine) builds frontend, stage 2 (python:3.11-slim) copies dist + runs backend
- [x] 3.3 Update `start.sh` to use gunicorn with uvicorn workers
- [x] 3.4 Set `STATIC_DIR=/app/static` in Dockerfile and copy `dist/` there
- [x] 3.5 Build and test locally from repo root with the final CI-equivalent command, for example `docker build -f backend/Dockerfile -t energy-audit . && docker run -p 8001:8001 -v ./XGB_Models:/home/models -e MODEL_DIR=/home/models energy-audit`
- [ ] 3.6 Profile memory on B1 with `WEB_CONCURRENCY=1`; only increase workers after measuring model-cache memory

**Dependencies:** Task 2 (FastAPI must be configured to serve static files)

---

### Task 4: Parse Easy Auth Identity Headers

**Files:**
- Create: `backend/app/middleware/auth_headers.py`
- Modify: `backend/app/main.py`

**Acceptance Criteria:**
- A FastAPI middleware or dependency parses `X-MS-CLIENT-PRINCIPAL-NAME` and `X-MS-CLIENT-PRINCIPAL` headers
- User email/name is available in request state for any route that wants it
- When headers are absent (local dev), user info is `None` — no errors
- No token validation logic (Easy Auth handles that)
- The project persistence task can reliably identify the current authenticated principal in production

**Constraints:**
- `X-MS-CLIENT-PRINCIPAL` is Base64-encoded JSON with claims
- Keep this lightweight — it is context from the platform-authenticated request, not token validation
- Don't block requests when headers are missing

**Sub-tasks:**
- [x] 4.1 Create middleware that decodes `X-MS-CLIENT-PRINCIPAL` and sets `request.state.user`
- [x] 4.2 Add middleware to `main.py`
- [x] 4.3 Verify locally by passing fake headers (these headers are stripped by Easy Auth in production, so they're safe to test with)
- [ ] 4.4 Verify in Azure that authenticated requests expose the expected identity headers and document which claim is used as stable user ID

**Dependencies:** None (but only useful after Easy Auth is configured in Task 0)

---

### Task 5: SQLite Persistence and User Isolation

**Files:**
- Modify: `backend/app/services/database.py`
- Modify: `backend/app/api/projects.py`
- Test: backend database/project route tests as appropriate

**Acceptance Criteria:**
- SQLite database path defaults to a persistent Azure-safe location when `DATABASE_PATH` is set to `/home/data/buildingstock.db`
- Database parent directory is created automatically before opening the SQLite file
- SQLite connection settings include WAL mode, foreign keys, and a busy timeout suitable for low-concurrency App Service usage
- The app runs with one web worker while SQLite is the production database
- Projects are either scoped to the authenticated Easy Auth principal or the plan explicitly documents that all authenticated users share one project database
- A backup/export procedure exists for `/home/data/buildingstock.db` before production cutover
- If concurrency, auditability, or durability requirements exceed SQLite, Azure SQL/PostgreSQL is selected before production instead of treating SQLite as a permanent production database

**Constraints:**
- Store SQLite files only under `/home` in Azure; writes outside `/home` are not persistent across container restarts
- Do not scale out to multiple App Service instances while SQLite is the write database
- Avoid using Easy Auth headers as a substitute for token validation; they are trusted only because App Service authentication gates the request before it reaches FastAPI

**Sub-tasks:**
- [x] 5.1 Add `DATABASE_PATH=/home/data/buildingstock.db` to App Service configuration and local/container documentation
- [x] 5.2 Update `Database` initialization to create the parent directory and configure a busy timeout
- [ ] 5.3 Decide and implement project ownership model: per-user principal scoping or intentionally shared authenticated workspace
- [x] 5.4 Add tests for persistent database path creation and the selected project visibility model
- [ ] 5.5 Verify restart/deploy behavior on Azure: create a project, restart the app, confirm data remains
- [ ] 5.6 Document backup/export and restore steps for the SQLite database

**Dependencies:** Task 4

---

### Task 6: Update Frontend API Base URL Default

**Files:**
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/composables/useAssessment.js`
- Modify: `frontend/src/composables/useProjects.js`
- Modify: `frontend/src/composables/useAddressLookup.js`
- Modify: `frontend/src/composables/useAddressAutocomplete.js`
- Modify: `frontend/src/composables/useEnergyStarScore.js`
- Modify: `frontend/src/composables/useBpsSearch.js`
- Modify: `frontend/src/composables/useMeasureSelections.js`

**Acceptance Criteria:**
- All frontend API callers default `API_BASE` to `''` (empty string = same origin) instead of `http://localhost:8001`
- `VITE_API_URL` env var still overrides for local development
- No functional change when `VITE_API_URL` is set

**Constraints:**
- One-line change per file: `const API_BASE = import.meta.env.VITE_API_URL ?? ''`
- Local dev instructions should note: set `VITE_API_URL=http://localhost:8001` in `.env`

**Sub-tasks:**
- [x] 6.1 Update all 7 composables and `frontend/src/App.vue` to default to `''`
- [x] 6.2 Create `frontend/.env.development` with `VITE_API_URL=http://localhost:8001` so local dev works automatically
- [ ] 6.3 Verify local dev still works with separate frontend/backend servers
- [x] 6.4 Build the production frontend and verify no bundle references `localhost:8001`

**Dependencies:** None

---

### Task 7: Deploy and Verify

**Acceptance Criteria:**
- App is deployed to Azure App Service and accessible at `https://<app-name>.azurewebsites.net`
- Unauthenticated users are redirected to Microsoft login
- Authenticated users see the full Vue SPA and can run assessments
- Models download on first startup and are cached on persistent storage
- Subsequent restarts skip the model download
- API endpoints all function correctly (assess, lookup, autocomplete, projects, etc.)
- Project persistence survives an App Service restart and a container redeploy
- Startup download/cache validation completes within Azure startup budget or an alternate pre-seeding/bundle strategy is implemented
- B1 resource metrics are reviewed and either accepted with thresholds or the plan is scaled up before production cutover

**Sub-tasks:**
- [ ] 7.1 Push Docker image to Azure Container Registry (or use App Service built-in build from Git)
- [ ] 7.2 Configure App Service to use the container image
- [ ] 7.3 Verify Easy Auth redirects unauthenticated requests to Entra login
- [ ] 7.4 Verify authenticated requests reach the app with identity headers
- [ ] 7.5 Run a full assessment through the UI to confirm end-to-end functionality
- [ ] 7.6 Verify model caching: restart the app, confirm models are not re-downloaded
- [ ] 7.7 Test with a non-assigned user to verify they are blocked
- [ ] 7.8 Create a project, restart/redeploy the app, confirm SQLite persistence and selected project visibility model
- [ ] 7.9 Review App Service metrics after first full assessment: memory working set, restart count, filesystem usage, request duration, startup duration
- [ ] 7.10 Verify monthly cost estimate includes App Service plan, Blob Storage, ACR if used, logging/App Insights/Log Analytics, backups, bandwidth, and any Entra licensing impacts

**Dependencies:** Tasks 0, 1, 2, 3, 4, 5, 6

---

## Reminders

- **TDD:** Write failing tests for all logic — conditionals, data transforms, error handling, integration points, edge cases. Prompt text and truly static config are verified by inspection, not tests.
- **Commit:** Commit after completing each task
- **Source of truth:** This plan defines requirements — refer to it when making judgment calls
- **Update this plan:** Check off completed tasks (`- [x]`) after each task is done
- **Railway stays running** until Azure deployment is verified end-to-end
