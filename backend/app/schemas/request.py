from pydantic import BaseModel, Field
from typing import Optional


class BuildingInput(BaseModel):
    building_type: str = Field(..., description="One of 15 building types")
    sqft: float = Field(..., gt=0)
    num_stories: int = Field(..., ge=1)
    zipcode: str = Field(..., min_length=5, max_length=5)
    year_built: int = Field(..., ge=1800, le=2030, description="Year the building was constructed")
    heating_fuel: Optional[str] = None
    dhw_fuel: Optional[str] = None
    hvac_system_type: Optional[str] = None
    wall_construction: Optional[str] = None
    window_type: Optional[str] = None
    window_to_wall_ratio: Optional[str] = None
    lighting_type: Optional[str] = None
    operating_hours: Optional[float] = None


class AssessmentRequest(BaseModel):
    buildings: list[BuildingInput]
