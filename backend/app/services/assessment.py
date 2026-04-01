"""
Assessment orchestrator — wires preprocessor, model inference, cost
calculation, and response formatting into a single assessment pipeline.
"""

from __future__ import annotations

import json as _json
import logging
import math
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path as _Path
from typing import Optional

logger = logging.getLogger(__name__)

# Load end-use grouping config once at module level
_ENDUSE_CFG_PATH = _Path(__file__).resolve().parent.parent / "data" / "enduse_grouping.json"
_ENDUSE_CFG: dict = {}
if _ENDUSE_CFG_PATH.exists():
    with open(_ENDUSE_CFG_PATH) as _f:
        _ENDUSE_CFG = _json.load(_f)
else:
    logger.warning(
        "enduse_grouping.json not found at %s; enduse_breakdown will be null", _ENDUSE_CFG_PATH
    )

from app.schemas.request import BuildingInput
from app.schemas.response import (
    AssessmentResponse,
    BaselineResult,
    BuildingResult,
    CostEstimate,
    FuelBreakdown,
    ImputedField,
    InputSummary,
    MeasureResult,
)
from app.constants import (
    KWH_TO_KBTU,
    KWH_TO_THERMS,
    KWH_PER_GALLON_FUEL_OIL,
    KWH_PER_GALLON_PROPANE,
    KWH_PER_THERM,
    STORY_HEIGHT_COMMERCIAL,
    STORY_HEIGHT_RESIDENTIAL,
    ASPECT_RATIO,
)
from app.services.emissions import calculate_emissions_reduction_pct
from app.inference.applicability import PACKAGE_CONSTITUENTS, RESSTOCK_PACKAGE_CONSTITUENTS
from app.services.preprocessor import preprocess, year_to_vintage, get_electricity_emission_factor
from app.inference.model_manager import ModelManager
from app.services.cost_calculator import CostCalculatorService


# ---------------------------------------------------------------------------
# Applicability helper (graceful fallback if Task 12 not yet implemented)
# ---------------------------------------------------------------------------

def _check_applicability(
    upgrade_id: int, dataset: str, features: dict
) -> bool:
    """Check whether an upgrade is applicable to a building.

    Delegates to ``app.inference.applicability.check_applicability`` when
    available; falls back to *always applicable* otherwise.
    """
    try:
        from app.inference.applicability import check_applicability
        # check_applicability expects available_upgrades set; when called
        # from the orchestrator the model already exists, so pass {upgrade_id}
        return check_applicability(upgrade_id, dataset, features, {upgrade_id})
    except (ImportError, AttributeError):
        # Module not ready yet — assume all upgrades are applicable.
        return True


# ---------------------------------------------------------------------------
# Upgrade name / category helpers
# ---------------------------------------------------------------------------

def _get_upgrade_name(
    upgrade_id: int,
    dataset: str,
    cost_calculator: CostCalculatorService,
) -> str:
    """Return the human-readable upgrade name from the cost lookup."""
    catalog = (
        cost_calculator._comstock
        if dataset == "comstock"
        else cost_calculator._resstock
    )
    entry = catalog.get(str(upgrade_id), {})
    return entry.get("upgrade_name", f"Upgrade {upgrade_id}")


def _get_upgrade_category(
    upgrade_id: int,
    dataset: str,
    cost_calculator: CostCalculatorService,
) -> str:
    """Return the measure category from the cost lookup."""
    catalog = (
        cost_calculator._comstock
        if dataset == "comstock"
        else cost_calculator._resstock
    )
    entry = catalog.get(str(upgrade_id), {})
    return entry.get("measure_category", "other")


def _get_upgrade_description(
    upgrade_id: int,
    dataset: str,
    cost_calculator: CostCalculatorService,
) -> str | None:
    """Return the measure description from the cost lookup."""
    catalog = (
        cost_calculator._comstock
        if dataset == "comstock"
        else cost_calculator._resstock
    )
    entry = catalog.get(str(upgrade_id), {})
    return entry.get("description")


# ---------------------------------------------------------------------------
# Geometric sizing (wall / roof / window area)
# ---------------------------------------------------------------------------

# Regex to parse "10-20%" style WWR strings
_RE_WWR = re.compile(r"(\d+)-(\d+)%")

# Default WWR when not available
_DEFAULT_WWR = 0.15


def _parse_wwr(features: dict, dataset: str) -> float:
    """Extract window-to-wall ratio from features as a decimal (0-1)."""
    if dataset == "comstock":
        wwr_str = features.get("in.window_to_wall_ratio_category", "")
        m = _RE_WWR.search(str(wwr_str))
        if m:
            return (int(m.group(1)) + int(m.group(2))) / 200.0
    elif dataset == "resstock":
        # in.window_areas is like "F15 B15 L15 R15" — avg of face percentages
        wa = features.get("in.window_areas", "")
        nums = re.findall(r"(\d+)", str(wa))
        if nums:
            return sum(int(n) for n in nums) / len(nums) / 100.0
    return _DEFAULT_WWR


def _geometric_sizing(
    sqft: float, num_stories: int, features: dict, dataset: str,
) -> dict:
    """Compute wall, roof, and window area from building geometry.

    Returns areas in ft².
    """
    story_height = (
        STORY_HEIGHT_RESIDENTIAL if dataset == "resstock"
        else STORY_HEIGHT_COMMERCIAL
    )
    floor_area = sqft / max(num_stories, 1)
    width = math.sqrt(floor_area / ASPECT_RATIO)
    length = width * ASPECT_RATIO
    perimeter = 2 * (length + width)

    wall_area = perimeter * story_height * num_stories
    roof_area = floor_area
    wwr = _parse_wwr(features, dataset)
    window_area = wall_area * wwr

    return {
        "wall_area": wall_area,
        "roof_area": roof_area,
        "window_area": window_area,
    }


# ---------------------------------------------------------------------------
# Utility data conversion helper
# ---------------------------------------------------------------------------

def convert_utility_to_eui(
    sqft: float,
    annual_electricity_kwh: float | None = None,
    annual_natural_gas_therms: float | None = None,
    annual_fuel_oil_gallons: float | None = None,
    annual_propane_gallons: float | None = None,
    annual_district_heating_kbtu: float | None = None,
) -> dict[str, float] | None:
    """Convert user-provided annual utility data to kWh/sqft per fuel.

    Returns None if no utility data is provided.
    """
    has_data = any(v is not None for v in [
        annual_electricity_kwh, annual_natural_gas_therms,
        annual_fuel_oil_gallons, annual_propane_gallons,
        annual_district_heating_kbtu,
    ])
    if not has_data:
        return None

    return {
        "electricity": (annual_electricity_kwh or 0) / sqft,
        "natural_gas": (annual_natural_gas_therms or 0) * KWH_PER_THERM / sqft,
        "fuel_oil": (annual_fuel_oil_gallons or 0) * KWH_PER_GALLON_FUEL_OIL / sqft,
        "propane": (annual_propane_gallons or 0) * KWH_PER_GALLON_PROPANE / sqft,
        "district_heating": (annual_district_heating_kbtu or 0) / KWH_TO_KBTU / sqft,
    }


# ---------------------------------------------------------------------------
# End-use breakdown
# ---------------------------------------------------------------------------

def _compute_enduse_breakdown(
    raw_enduse_eui: dict[str, float],
    total_baseline_kbtu: float,
    dataset: str,
) -> dict[str, float] | None:
    """Convert raw per-end-use EUI predictions into grouped kBtu/sf breakdown.

    1. Sum raw predictions → predicted total
    2. Compute each end use's share of that total
    3. Group by display category
    4. Scale grouped shares to the trusted baseline total (kBtu/sf)

    Returns dict of display_category -> kBtu/sf, or None if no data.
    """
    if not raw_enduse_eui or total_baseline_kbtu <= 0:
        return None

    predicted_total = sum(max(0.0, v) for v in raw_enduse_eui.values())
    if predicted_total <= 0:
        return None

    grouping = _ENDUSE_CFG.get(dataset, {}).get("grouping", {})
    if not grouping:
        return None

    result = {}
    for category, enduses in grouping.items():
        cat_eui = sum(max(0.0, raw_enduse_eui.get(eu, 0.0)) for eu in enduses)
        share = cat_eui / predicted_total
        result[category] = share * total_baseline_kbtu

    # Catch any trained end uses not in the grouping → add to "Other"
    grouped_enduses = set()
    for enduses in grouping.values():
        grouped_enduses.update(enduses)
    ungrouped_eui = sum(
        v for k, v in raw_enduse_eui.items() if k not in grouped_enduses
    )
    if ungrouped_eui > 0:
        other_share = ungrouped_eui / predicted_total
        result["Other"] = result.get("Other", 0.0) + other_share * total_baseline_kbtu

    return {k: round(v, 2) for k, v in result.items()}


# ---------------------------------------------------------------------------
# Single-building assessment
# ---------------------------------------------------------------------------

def _assess_single(
    building: BuildingInput,
    index: int,
    model_manager: ModelManager,
    cost_calculator: CostCalculatorService,
    imputation_service=None,
) -> BuildingResult:
    """Run the full assessment pipeline for one building."""

    # 1. Preprocess
    features, imputed_details, dataset, climate_zone, state = preprocess(
        building, imputation_service=imputation_service
    )

    # Shared encoding cache — avoids re-encoding the same features across models
    enc_cache: dict = {}

    # 2. Predict baseline EUI (kWh/ft2 per fuel)
    baseline_eui = model_manager.predict_baseline(features, dataset, enc_cache)

    # Convert utility data to kWh/sqft if provided
    actual_baseline_eui = convert_utility_to_eui(
        sqft=building.sqft,
        annual_electricity_kwh=building.annual_electricity_kwh,
        annual_natural_gas_therms=building.annual_natural_gas_therms,
        annual_fuel_oil_gallons=building.annual_fuel_oil_gallons,
        annual_propane_gallons=building.annual_propane_gallons,
        annual_district_heating_kbtu=building.annual_district_heating_kbtu,
    )
    calibrated = actual_baseline_eui is not None
    effective_baseline = actual_baseline_eui if calibrated else baseline_eui

    # 3. Predict sizing (capacity for cost calculation) + geometric areas
    sizing = model_manager.predict_sizing(features, dataset, enc_cache)
    # Clamp sizing predictions to zero — negative capacity is physically impossible
    sizing = {k: max(0.0, v) for k, v in sizing.items()}
    # Override ML-predicted areas with geometric calculation (more accurate)
    geo = _geometric_sizing(building.sqft, building.num_stories or 1, features, dataset)
    sizing.update(geo)

    # ResStock sizing predictions are per-unit; keep them per-unit and let the
    # cost calculator produce per-unit costs, then convert to $/sf below.
    resstock_per_unit_sqft: Optional[float] = None
    resstock_per_unit_sizing: Optional[dict] = None
    if dataset == "resstock":
        resstock_per_unit_sqft = features.get("in.sqft..ft2", 900.0)
        # Geometric areas are whole-building; scale to per-unit for cost calc
        n_units = building.sqft / resstock_per_unit_sqft if resstock_per_unit_sqft > 0 else 1
        resstock_per_unit_sizing = {**sizing}
        for area_key in ("wall_area", "roof_area", "window_area"):
            if area_key in resstock_per_unit_sizing:
                resstock_per_unit_sizing[area_key] = sizing[area_key] / n_units

    # 4. Predict utility rates ($/kWh per fuel)
    rates = model_manager.predict_rates(features, dataset, enc_cache)

    # 5. Convert effective baseline to kBtu/sf (clamp negatives to zero)
    baseline_kbtu = {fuel: max(0.0, eui * KWH_TO_KBTU) for fuel, eui in effective_baseline.items()}
    total_baseline_kbtu = sum(baseline_kbtu.values())

    # 5b. Predict end-use breakdown (graceful: returns {} if models not trained)
    raw_enduse_eui = model_manager.predict_enduse(features, dataset, enc_cache)
    enduse_breakdown = _compute_enduse_breakdown(
        raw_enduse_eui, total_baseline_kbtu, dataset
    )

    # 6. Check applicability and predict upgrades
    upgrade_ids = model_manager.get_available_upgrades(dataset)

    # Pre-warm: load all upgrade models from disk in parallel (I/O-bound)
    applicable_ids = [
        uid for uid in upgrade_ids
        if _check_applicability(uid, dataset, features)
    ]
    model_manager.warm_upgrades(dataset, applicable_ids)

    # Pre-compute all deltas in parallel (XGBoost releases the GIL)
    delta_results: dict[int, dict] = {}

    def _predict_upgrade(uid: int) -> tuple[int, dict]:
        return uid, model_manager.predict_delta(
            features, uid, dataset,
            baseline_eui=actual_baseline_eui if calibrated else baseline_eui,
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        for uid, delta in pool.map(_predict_upgrade, applicable_ids):
            delta_results[uid] = delta

    measures: list[MeasureResult] = []

    # Electricity emission factor (same for all upgrades — same building/zipcode)
    electricity_ef = get_electricity_emission_factor(building.zipcode)

    for uid in upgrade_ids:
        # Check applicability
        if uid not in delta_results:
            measures.append(
                MeasureResult(
                    upgrade_id=uid,
                    name=_get_upgrade_name(uid, dataset, cost_calculator),
                    category=_get_upgrade_category(uid, dataset, cost_calculator),
                    applicable=False,
                )
            )
            continue

        delta = delta_results[uid]
        savings_kwh = {}
        for fuel, d in delta.items():
            bl = effective_baseline.get(fuel, 0)
            if bl <= 0.001:
                # No meaningful baseline consumption — zero out savings
                savings_kwh[fuel] = 0.0
            elif d > 0:
                # Positive savings capped at baseline (can't save more than you use)
                savings_kwh[fuel] = min(d, bl)
            else:
                # Negative savings (fuel-switching increase) — pass through
                savings_kwh[fuel] = d

        # Derive post-upgrade EUI from baseline - savings (floor at zero)
        post_eui = {
            fuel: max(0.0, effective_baseline.get(fuel, 0) - savings_kwh.get(fuel, 0))
            for fuel in effective_baseline
        }

        category = _get_upgrade_category(uid, dataset, cost_calculator)

        post_kbtu = {fuel: eui * KWH_TO_KBTU for fuel, eui in post_eui.items()}
        total_post_kbtu = sum(post_kbtu.values())

        # Savings
        savings_kbtu = total_baseline_kbtu - total_post_kbtu
        savings_pct = (
            (savings_kbtu / total_baseline_kbtu * 100)
            if total_baseline_kbtu > 0
            else 0.0
        )

        # Cost
        cost: Optional[CostEstimate] = None
        try:
            if resstock_per_unit_sqft is not None:
                # ResStock: calculate per-unit cost, then convert to $/sf
                per_unit_cost = cost_calculator.calculate_cost(
                    uid, dataset, resstock_per_unit_sqft,
                    resstock_per_unit_sizing, state
                )
                # Convert per-unit total to $/sf, then scale to whole building
                cost_per_sf = (
                    per_unit_cost.installed_cost_total / resstock_per_unit_sqft
                    if resstock_per_unit_sqft > 0
                    else 0.0
                )
                total_cost = cost_per_sf * building.sqft
                cost = CostEstimate(
                    installed_cost_per_sf=round(cost_per_sf, 2),
                    installed_cost_total=round(total_cost, 2),
                    cost_range={
                        "low": round(
                            per_unit_cost.cost_range["low"]
                            / resstock_per_unit_sqft
                            * building.sqft,
                            2,
                        ),
                        "high": round(
                            per_unit_cost.cost_range["high"]
                            / resstock_per_unit_sqft
                            * building.sqft,
                            2,
                        ),
                    },
                    useful_life_years=per_unit_cost.useful_life_years,
                    regional_factor=per_unit_cost.regional_factor,
                    confidence=per_unit_cost.confidence,
                )
            else:
                cost = cost_calculator.calculate_cost(
                    uid, dataset, building.sqft, sizing, state
                )
        except (ValueError, KeyError):
            logger.debug(
                "Could not calculate cost for upgrade %d (%s)", uid, dataset
            )

        # Bill savings: sum of (rate * savings) per fuel
        bill_savings_per_sf = sum(
            savings_kwh.get(fuel, 0) * rates.get(fuel, 0)
            for fuel in effective_baseline
        )

        # Simple payback
        payback: Optional[float] = None
        if cost and bill_savings_per_sf > 0:
            payback = cost.installed_cost_per_sf / bill_savings_per_sf

        # Per-fuel savings in display units
        elec_savings_kwh = round(savings_kwh.get("electricity", 0.0), 2)
        gas_savings_therms = round(
            savings_kwh.get("natural_gas", 0.0) * KWH_TO_THERMS, 4
        )
        other_fuels = ["fuel_oil", "propane", "district_heating"]
        other_savings_kbtu = round(
            sum(savings_kwh.get(f, 0.0) for f in other_fuels) * KWH_TO_KBTU, 2
        )

        # Per-fuel savings in kBtu/sf for client-side projected EUI computation
        savings_fuel_breakdown = FuelBreakdown(
            electricity=round(savings_kwh.get("electricity", 0.0) * KWH_TO_KBTU, 4),
            natural_gas=round(savings_kwh.get("natural_gas", 0.0) * KWH_TO_KBTU, 4),
            fuel_oil=round(savings_kwh.get("fuel_oil", 0.0) * KWH_TO_KBTU, 4),
            propane=round(savings_kwh.get("propane", 0.0) * KWH_TO_KBTU, 4),
            district_heating=round(savings_kwh.get("district_heating", 0.0) * KWH_TO_KBTU, 4),
        )

        # Package constituent IDs
        pkg_map = RESSTOCK_PACKAGE_CONSTITUENTS if dataset == "resstock" else PACKAGE_CONSTITUENTS
        pkg_constituents = pkg_map.get(uid)

        # Emissions reduction
        emissions_pct = calculate_emissions_reduction_pct(
            effective_baseline, post_eui, electricity_ef
        )

        measures.append(
            MeasureResult(
                upgrade_id=uid,
                name=_get_upgrade_name(uid, dataset, cost_calculator),
                category=category,
                applicable=True,
                post_upgrade_eui_kbtu_sf=round(total_post_kbtu, 2),
                savings_kbtu_sf=round(savings_kbtu, 2),
                savings_pct=round(savings_pct, 1),
                cost=cost,
                utility_bill_savings_per_sf=round(bill_savings_per_sf, 4),
                simple_payback_years=round(payback, 1) if payback else None,
                electricity_savings_kwh=elec_savings_kwh,
                gas_savings_therms=gas_savings_therms,
                other_fuel_savings_kbtu=other_savings_kbtu,
                emissions_reduction_pct=round(emissions_pct, 1),
                description=_get_upgrade_description(uid, dataset, cost_calculator),
                savings_by_fuel=savings_fuel_breakdown,
                constituent_upgrade_ids=pkg_constituents,
            )
        )

    # Sort: applicable first (desc by savings_pct), then non-applicable
    measures.sort(key=lambda m: (not m.applicable, -(m.savings_pct or 0)))

    # Build fuel breakdown for baseline
    fuel_breakdown = FuelBreakdown(
        electricity=round(baseline_kbtu.get("electricity", 0), 2),
        natural_gas=round(baseline_kbtu.get("natural_gas", 0), 2),
        fuel_oil=round(baseline_kbtu.get("fuel_oil", 0), 2),
        propane=round(baseline_kbtu.get("propane", 0), 2),
        district_heating=round(baseline_kbtu.get("district_heating", 0), 2),
    )

    return BuildingResult(
        building_index=index,
        baseline=BaselineResult(
            total_eui_kbtu_sf=round(total_baseline_kbtu, 2),
            eui_by_fuel=fuel_breakdown,
            actual_eui_by_fuel=FuelBreakdown(**{
                fuel: val * KWH_TO_KBTU for fuel, val in actual_baseline_eui.items()
            }) if calibrated else None,
            actual_total_eui_kbtu_sf=sum(
                val * KWH_TO_KBTU for val in actual_baseline_eui.values()
            ) if calibrated else None,
            enduse_breakdown=enduse_breakdown,
        ),
        measures=measures,
        input_summary=InputSummary(
            climate_zone=climate_zone,
            cluster_name=features.get("cluster_name", "Unknown"),
            state=state,
            vintage_bucket=features.get(
                "in.vintage",
                year_to_vintage(building.year_built, dataset),
            ),
            imputed_fields=list(imputed_details.keys()),
            imputed_details={
                k: ImputedField(**v) for k, v in imputed_details.items()
            },
        ),
        calibrated=calibrated,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def assess_buildings(
    buildings: list[BuildingInput],
    model_manager: ModelManager,
    cost_calculator: CostCalculatorService,
    imputation_service=None,
) -> list[BuildingResult]:
    """Process a list of building inputs and return assessment results."""
    results: list[BuildingResult] = []
    for i, building in enumerate(buildings):
        result = _assess_single(
            building, i, model_manager, cost_calculator, imputation_service
        )
        results.append(result)
    return results
