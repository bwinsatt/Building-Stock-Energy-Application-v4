from pydantic import BaseModel
from typing import Optional


class FieldResult(BaseModel):
    value: Optional[object] = None
    source: Optional[str] = None  # "osm", "computed", "imputed", "nyc_opendata", "chicago_opendata", None
    confidence: Optional[float] = None


class LookupResponse(BaseModel):
    address: str
    lat: float
    lon: float
    zipcode: Optional[str] = None
    building_fields: dict[str, FieldResult]
    target_building_polygon: Optional[list[list[float]]] = None
    nearby_buildings: list[dict] = []
    bps_available: bool = False
    bps_ordinance_name: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    bbl: Optional[str] = None
