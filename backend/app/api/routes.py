import asyncio
import logging

from fastapi import APIRouter, Request, HTTPException

from app.schemas.request import AssessmentRequest
from app.schemas.response import AssessmentResponse
from app.schemas.lookup_response import LookupResponse
from app.schemas.energy_star import EnergyStarRequest, EnergyStarResponse
from app.services.assessment import assess_buildings
from app.services.address_lookup import lookup_address
from app.services.autocomplete import PhotonProvider
from app.services.energy_star import EnergyStarService
from app.services.bps_query import query_bps

logger = logging.getLogger(__name__)
router = APIRouter()

# Auto-offload: clear upgrade cache after 20 minutes of inactivity
_OFFLOAD_DELAY_SECONDS = 20 * 60
_offload_task: asyncio.Task | None = None


async def _schedule_offload(app):
    """Wait then offload upgrade models if no new assessment arrives."""
    try:
        await asyncio.sleep(_OFFLOAD_DELAY_SECONDS)
        evicted = app.state.model_manager.offload_upgrades()
        logger.info("Auto-offloaded %d upgrade bundles after inactivity", evicted)
    except asyncio.CancelledError:
        pass


def _reset_offload_timer(app):
    """Cancel any pending offload and start a new timer."""
    global _offload_task
    if _offload_task and not _offload_task.done():
        _offload_task.cancel()
    _offload_task = asyncio.create_task(_schedule_offload(app))

# Module-level provider instance — swap this to change providers
autocomplete_provider = PhotonProvider()


@router.post("/assess", response_model=AssessmentResponse)
async def assess(request: AssessmentRequest, req: Request):
    try:
        _reset_offload_timer(req.app)
        model_manager = req.app.state.model_manager
        cost_calculator = req.app.state.cost_calculator
        imputation_service = getattr(req.app.state, "imputation_service", None)
        results = assess_buildings(
            request.buildings, model_manager, cost_calculator, imputation_service
        )
        return AssessmentResponse(results=results)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/offload")
async def offload(req: Request):
    """Manually free cached upgrade models from memory."""
    evicted = req.app.state.model_manager.offload_upgrades()
    return {"status": "ok", "evicted": evicted}


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


@router.get("/bps/search")
async def bps_search(
    address: str,
    city: str | None = None,
    state: str | None = None,
    zipcode: str | None = None,
    county: str | None = None,
):
    """Search BPS benchmarking databases for a building's energy data."""
    if not city or not state:
        from app.services.address_lookup import geocode_address
        geo = geocode_address(address)
        if geo is None:
            raise HTTPException(status_code=404, detail="Could not geocode address")
        city = city or geo.get("city")
        state = state or geo.get("state")
        zipcode = zipcode or geo.get("zipcode")

    if not city or not state:
        raise HTTPException(status_code=400, detail="Could not determine city/state")

    # Resolve county if not provided
    if not county and zipcode:
        try:
            import pgeocode
            nomi = pgeocode.Nominatim("US")
            result = nomi.query_postal_code(zipcode)
            if hasattr(result, "county_name"):
                county_val = result.county_name
                if county_val == county_val:  # NaN check
                    county = county_val
        except Exception:
            pass

    result = await query_bps(address, city, state, county, zipcode)
    if result is None:
        raise HTTPException(status_code=404, detail="No benchmarking data found for this address")

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


@router.post("/energy-star/score", response_model=EnergyStarResponse)
async def energy_star_score(request: EnergyStarRequest):
    service = EnergyStarService()
    try:
        return service.get_score(
            building=request.building,
            baseline=request.baseline,
            address=request.address,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/health")
async def health():
    return {"status": "ok"}
