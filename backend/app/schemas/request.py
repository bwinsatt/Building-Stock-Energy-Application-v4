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
    hvac_heating_efficiency: Optional[str] = None
    hvac_cooling_efficiency: Optional[str] = None
    water_heater_efficiency: Optional[str] = None
    insulation_wall: Optional[str] = None
    infiltration: Optional[str] = None

    # Advanced inputs (optional — XGBoost handles NaN natively)
    thermostat_heating_setpoint: Optional[float] = Field(
        None, ge=50, le=85, description="Heating setpoint (°F)"
    )
    thermostat_cooling_setpoint: Optional[float] = Field(
        None, ge=65, le=90, description="Cooling setpoint (°F)"
    )
    thermostat_heating_setback: Optional[float] = Field(
        None, ge=0, le=20, description="Heating setback delta (°F)"
    )
    thermostat_cooling_setback: Optional[float] = Field(
        None, ge=0, le=20, description="Cooling setback delta (°F)"
    )
    weekend_operating_hours: Optional[float] = Field(
        None, ge=0, le=24, description="Weekend operating hours per day"
    )


class AssessmentRequest(BaseModel):
    buildings: list[BuildingInput]
