# BuildingStock Energy Estimation — Docker Setup

## Prerequisites

- Docker Desktop installed and running
- Git access to the repo

## Steps

### 1. Clone the repo

```bash
git clone https://github.com/bwinsatt/BuildingStock-Energy-Estimator.git
cd BuildingStock-Energy-Estimator
```

### 2. Add the models

Download `XGB_Models/` from Google Drive and place it in the repo root so the structure looks like:

```
BuildingStock-Energy-Estimator/
├── XGB_Models/          ← downloaded from Google Drive
│   ├── ComStock_Rates/
│   ├── ComStock_Sizing/
│   ├── ComStock_Upgrades_2025_R3/
│   ├── Imputation/
│   ├── ResStock_Rates/
│   ├── ResStock_Sizing/
│   └── ResStock_Upgrades_2025_R1/
├── backend/
├── frontend/
├── docker-compose.yml
└── ...
```

### 3. Build and start

```bash
docker compose up --build
```

First build takes ~2 minutes. Model loading takes ~30-45 seconds on startup.

### 4. Open the app

- **Frontend**: http://localhost:3000
- **Backend API (direct)**: http://localhost:8001

All API calls from the frontend are proxied through nginx, so you only need to open port 3000.

### 5. Stop

```bash
docker compose down
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Frontend loads but API calls fail | Wait for backend to finish loading models — check with `docker compose logs backend` and look for "Application startup complete" |
| "XGB_Models not found" or model errors | Make sure `XGB_Models/` is in the repo root (same level as `docker-compose.yml`) |
| Port conflict on 3000 or 8001 | Edit `docker-compose.yml` ports mapping (e.g., change `"3000:80"` to `"8080:80"`) |
| Need to rebuild after code changes | `docker compose up --build` |
