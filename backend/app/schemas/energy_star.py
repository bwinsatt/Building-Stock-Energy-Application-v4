from pydantic import BaseModel
from typing import Optional

from app.schemas.request import BuildingInput
from app.schemas.response import BaselineResult


class EnergyStarRequest(BaseModel):
    building: BuildingInput
    baseline: BaselineResult
    address: Optional[str] = None


class EnergyStarResponse(BaseModel):
    score: Optional[int] = None
    eligible: bool
    median_eui_kbtu_sf: Optional[float] = None
    target_eui_kbtu_sf: Optional[float] = None
    design_eui_kbtu_sf: Optional[float] = None
    percentile_text: Optional[str] = None
    espm_property_type: str
    reasons_for_no_score: Optional[list[str]] = None
