from fastapi import APIRouter, Request, HTTPException

from app.schemas.request import AssessmentRequest
from app.schemas.response import AssessmentResponse
from app.schemas.lookup_response import LookupResponse
from app.services.assessment import assess_buildings
from app.services.address_lookup import lookup_address
from app.services.autocomplete import PhotonProvider

router = APIRouter()

# Module-level provider instance — swap this to change providers
autocomplete_provider = PhotonProvider()


@router.post("/assess", response_model=AssessmentResponse)
async def assess(request: AssessmentRequest, req: Request):
    try:
        model_manager = req.app.state.model_manager
        cost_calculator = req.app.state.cost_calculator
        imputation_service = getattr(req.app.state, "imputation_service", None)
        results = assess_buildings(
            request.buildings, model_manager, cost_calculator, imputation_service
        )
        return AssessmentResponse(results=results)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/metadata")
async def metadata():
    return {
        "building_types": [
            "Education",
            "Food Sales",
            "Food Service",
            "Healthcare",
            "Lodging",
            "Mercantile",
            "Mixed Use",
            "Multi-Family",
            "Office",
            "Public Assembly",
            "Public Order and Safety",
            "Religious Worship",
            "Service",
            "Warehouse and Storage",
        ],
        "heating_fuels": [
            "NaturalGas",
            "Electricity",
            "FuelOil",
            "Propane",
            "DistrictHeating",
        ],
        "dhw_fuels": [
            "NaturalGas",
            "Electricity",
            "FuelOil",
            "Propane",
        ],
        "hvac_system_types": [
            "PSZ-AC",
            "PSZ-HP",
            "PTAC",
            "PTHP",
            "VAV_chiller_boiler",
            "VAV_air_cooled_chiller_boiler",
            "PVAV_gas_boiler",
            "PVAV_gas_heat",
            "Residential_AC_gas_furnace",
            "Residential_forced_air_furnace",
        ],
        "wall_constructions": ["Mass", "Metal", "SteelFrame", "WoodFrame"],
        "window_types": [
            "Single, Clear, Metal",
            "Single, Clear, Non-metal",
            "Double, Clear, Metal",
            "Double, Clear, Non-metal",
            "Double, Low-E, Metal",
            "Double, Low-E, Non-metal",
            "Triple, Low-E, Metal",
            "Triple, Low-E, Non-metal",
        ],
        "window_to_wall_ratios": [
            "0-10%",
            "10-20%",
            "20-30%",
            "30-40%",
            "40-50%",
            "50%+",
        ],
        "lighting_types": ["T12", "T8", "T5", "CFL", "LED"],
    }


@router.get("/lookup", response_model=LookupResponse)
async def lookup(address: str, req: Request):
    imputation_service = getattr(req.app.state, "imputation_service", None)
    result = lookup_address(address, imputation_service=imputation_service)
    if result is None:
        raise HTTPException(status_code=404, detail="Address not found")
    return result


@router.get("/autocomplete")
async def autocomplete(q: str = "") -> list[dict]:
    if len(q) < 3:
        return []
    suggestions = await autocomplete_provider.suggest(q, limit=5)
    return [
        {
            "display": s.display,
            "lat": s.lat,
            "lon": s.lon,
            "zipcode": s.zipcode,
        }
        for s in suggestions
    ]


@router.get("/health")
async def health():
    return {"status": "ok"}
