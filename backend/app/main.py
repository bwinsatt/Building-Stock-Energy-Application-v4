import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.inference.model_manager import ModelManager
from app.inference.imputation_service import ImputationService
from app.services.cost_calculator import CostCalculatorService
from app.services.database import Database

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.routes import router  # noqa: E402
from app.api.projects import router as projects_router  # noqa: E402

app.include_router(router)
app.include_router(projects_router)
