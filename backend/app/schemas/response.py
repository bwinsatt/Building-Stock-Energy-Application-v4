from pydantic import BaseModel
from typing import Optional


class FuelBreakdown(BaseModel):
    electricity: float
    natural_gas: float
    fuel_oil: float
    propane: float
    district_heating: float = 0.0


class BaselineResult(BaseModel):
    total_eui_kbtu_sf: float
    eui_by_fuel: FuelBreakdown
    emissions_kg_co2e_per_sf: Optional[float] = None


class CostEstimate(BaseModel):
    installed_cost_per_sf: float
    installed_cost_total: float
    cost_range: dict  # {"low": float, "high": float}
    useful_life_years: Optional[int] = None
    regional_factor: float
    confidence: str


class MeasureResult(BaseModel):
    upgrade_id: int
    name: str
    category: str
    applicable: bool
    post_upgrade_eui_kbtu_sf: Optional[float] = None
    savings_kbtu_sf: Optional[float] = None
    savings_pct: Optional[float] = None
    cost: Optional[CostEstimate] = None
    utility_bill_savings_per_sf: Optional[float] = None
    simple_payback_years: Optional[float] = None
    emissions_reduction_pct: Optional[float] = None
    electricity_savings_kwh: Optional[float] = None
    gas_savings_therms: Optional[float] = None
    other_fuel_savings_kbtu: Optional[float] = None
    description: Optional[str] = None


class ImputedField(BaseModel):
    value: str
    label: str
    source: str  # "model" or "default"
    confidence: Optional[float] = None  # 0.0-1.0, only when source="model"


class InputSummary(BaseModel):
    climate_zone: str
    cluster_name: str
    state: str
    vintage_bucket: str
    imputed_fields: list[str]  # keep for backward compat
    imputed_details: dict[str, ImputedField] = {}


class BuildingResult(BaseModel):
    building_index: int
    baseline: BaselineResult
    measures: list[MeasureResult]
    input_summary: InputSummary


class AssessmentResponse(BaseModel):
    results: list[BuildingResult]
