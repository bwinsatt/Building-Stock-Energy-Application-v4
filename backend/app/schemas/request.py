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

    # Utility bill data (optional, for calibration)
    annual_electricity_kwh: Optional[float] = None
    annual_natural_gas_therms: Optional[float] = None
    annual_fuel_oil_gallons: Optional[float] = None
    annual_propane_gallons: Optional[float] = None
    annual_district_heating_kbtu: Optional[float] = None


class AssessmentRequest(BaseModel):
    buildings: list[BuildingInput]
