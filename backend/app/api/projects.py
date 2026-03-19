"""Project/building/assessment CRUD endpoints."""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/projects", tags=["projects"])


class CreateProjectRequest(BaseModel):
    name: str


class CreateBuildingRequest(BaseModel):
    address: str
    building_input: dict
    utility_data: dict | None = None
    lookup_data: dict | None = None


class SaveAssessmentRequest(BaseModel):
    result: dict
    calibrated: bool


@router.post("")
def create_project(req: CreateProjectRequest, request: Request):
    return request.app.state.database.create_project(req.name)


@router.get("")
def list_projects(request: Request):
    return request.app.state.database.list_projects()


@router.get("/{project_id}")
def get_project(project_id: int, request: Request):
    project = request.app.state.database.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}")
def delete_project(project_id: int, request: Request):
    request.app.state.database.delete_project(project_id)
    return {"ok": True}


@router.post("/{project_id}/buildings")
def create_building(project_id: int, req: CreateBuildingRequest, request: Request):
    project = request.app.state.database.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return request.app.state.database.create_building(
        project_id=project_id,
        address=req.address,
        building_input=req.building_input,
        utility_data=req.utility_data,
        lookup_data=req.lookup_data,
    )


@router.get("/{project_id}/buildings/{building_id}")
def get_building(project_id: int, building_id: int, request: Request):
    building = request.app.state.database.get_building(project_id, building_id)
    if building is None:
        raise HTTPException(status_code=404, detail="Building not found")
    return building


@router.post("/{project_id}/buildings/{building_id}/assessments")
def save_assessment(
    project_id: int, building_id: int,
    req: SaveAssessmentRequest, request: Request,
):
    return request.app.state.database.save_assessment(
        building_id=building_id,
        result=req.result,
        calibrated=req.calibrated,
    )
