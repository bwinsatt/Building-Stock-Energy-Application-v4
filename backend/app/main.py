import os
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.inference.model_manager import ModelManager
from app.inference.imputation_service import ImputationService
from app.services.cost_calculator import CostCalculatorService
from app.services.database import Database
from app.middleware.auth_headers import EasyAuthMiddleware

STATIC_DIR = os.environ.get("STATIC_DIR")

model_manager = ModelManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    model_manager.load_all()
    app.state.model_manager = model_manager
    app.state.cost_calculator = CostCalculatorService()

    model_root = os.environ.get(
        "MODEL_DIR",
        os.path.join(os.path.dirname(__file__), "..", "..", "XGB_Models"),
    )
    imputation_dir = os.path.join(model_root, "Imputation")
    imputation_service = ImputationService(imputation_dir)
    imputation_service.load()
    app.state.imputation_service = imputation_service

    db = Database()
    db.init()
    app.state.database = db

    yield


app = FastAPI(title="Energy Audit Tool", lifespan=lifespan)
app.add_middleware(EasyAuthMiddleware)

if not STATIC_DIR:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

from app.api.routes import router  # noqa: E402
from app.api.projects import router as projects_router  # noqa: E402

app.include_router(router)
app.include_router(projects_router)

if STATIC_DIR:
    static_path = Path(STATIC_DIR)
    assets_path = static_path / "assets"
    if assets_path.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_path)), name="static-assets")

    @app.get("/{full_path:path}")
    async def spa_catch_all(request: Request, full_path: str):
        index = static_path / "index.html"
        if index.is_file():
            return FileResponse(str(index))
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Not found")
