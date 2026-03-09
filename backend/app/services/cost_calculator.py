"""Cost calculator service.

Converts unit costs from upgrade_cost_lookup.json into $/sf using
XGB-predicted capacity/area from the sizing models.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from app.schemas.response import CostEstimate

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_DEFAULT_LOOKUP_PATH = _DATA_DIR / "upgrade_cost_lookup.json"

# Conversion factor: square metres to square feet
M2_TO_FT2 = 10.764


def _get_sizing(sizing: dict, key: str) -> float:
    """Look up a sizing value, trying both bare and 'sizing_' prefixed keys."""
    if key in sizing:
        return sizing[key]
    prefixed = f"sizing_{key}"
    if prefixed in sizing:
        return sizing[prefixed]
    return 0


class CostCalculatorService:
    """Calculate installed upgrade costs from unit-cost data and sizing predictions."""

    def __init__(self, lookup_path: Optional[Path] = None) -> None:
        path = lookup_path or _DEFAULT_LOOKUP_PATH
        with open(path, "r") as f:
            data = json.load(f)

        self._comstock: dict = data.get("comstock", {})
        self._resstock: dict = data.get("resstock", {})
        self._regional: dict = data.get("regional_adjustments", {})

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate_cost(
        self,
        upgrade_id: int,
        dataset: str,
        sqft: float,
        sizing: dict,
        state: str,
    ) -> CostEstimate:
        """Calculate installed cost for an upgrade.

        Args:
            upgrade_id: upgrade number (key in the lookup JSON).
            dataset: ``'comstock'`` or ``'resstock'``.
            sqft: building gross floor area in ft².
            sizing: dict from ``predict_sizing()`` with keys
                ``heating_capacity``, ``cooling_capacity``, ``wall_area``,
                ``roof_area``, ``window_area``.
            state: 2-letter US state code for regional adjustment.

        Returns:
            A :class:`CostEstimate` pydantic model.
        """
        catalog = self._comstock if dataset == "comstock" else self._resstock
        entry = catalog.get(str(upgrade_id))
        if entry is None:
            raise ValueError(
                f"Upgrade {upgrade_id} not found in {dataset} cost lookup"
            )

        cost_basis: str = entry.get("cost_basis") or ""
        cost_mid: float = float(entry.get("cost_mid") or 0)
        cost_low: float = float(entry["cost_low"] if entry.get("cost_low") is not None else cost_mid)
        cost_high: float = float(entry["cost_high"] if entry.get("cost_high") is not None else cost_mid)
        useful_life: Optional[int] = (
            int(entry["useful_life_years"])
            if entry.get("useful_life_years") is not None
            else None
        )

        # --- Regional adjustment factor ---
        regional_factor = self._get_regional_factor(state, dataset)

        # --- Determine confidence ---
        confidence = self._determine_confidence(entry, cost_basis)

        # --- Handle mixed / package upgrades ---
        if cost_basis.startswith("mixed"):
            total_mid, total_low, total_high = self._resolve_mixed(
                entry, catalog, dataset, sqft, sizing
            )
        else:
            total_mid = self._unit_cost_to_total(
                cost_mid, cost_basis, dataset, sqft, sizing
            )
            total_low = self._unit_cost_to_total(
                cost_low, cost_basis, dataset, sqft, sizing
            )
            total_high = self._unit_cost_to_total(
                cost_high, cost_basis, dataset, sqft, sizing
            )

        # Apply regional adjustment
        total_mid *= regional_factor
        total_low *= regional_factor
        total_high *= regional_factor

        per_sf = total_mid / sqft if sqft > 0 else 0.0

        return CostEstimate(
            installed_cost_per_sf=round(per_sf, 2),
            installed_cost_total=round(total_mid, 2),
            cost_range={
                "low": round(total_low, 2),
                "high": round(total_high, 2),
            },
            useful_life_years=useful_life,
            regional_factor=round(regional_factor, 4),
            confidence=confidence,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_regional_factor(self, state: str, dataset: str) -> float:
        """Return the regional cost adjustment multiplier for *state*."""
        adj = self._regional.get(state.upper())
        if adj is None:
            return 1.0
        # The JSON stores {"city": ..., "residential": float, "commercial": float}
        if isinstance(adj, dict):
            if dataset == "resstock":
                return float(adj.get("residential", 1.0))
            return float(adj.get("commercial", 1.0))
        # Fallback: plain float
        return float(adj)

    @staticmethod
    def _determine_confidence(entry: dict, cost_basis: str) -> str:
        """Return confidence label for this upgrade cost estimate.

        If the JSON entry already carries a ``confidence`` field we prefer that.
        Otherwise we fall back to heuristic rules:
        - ``high`` for simple bases ($/ft^2 floor, $/unit)
        - ``low`` for mixed / package upgrades
        - ``medium`` for everything else
        """
        if "confidence" in entry and entry["confidence"]:
            raw = str(entry["confidence"]).lower().strip()
            # normalise "moderate" -> "medium"
            if raw in ("moderate",):
                return "medium"
            if raw in ("high", "medium", "low"):
                return raw
        # Heuristic fallback
        if cost_basis.startswith("mixed"):
            return "low"
        if cost_basis in ("$/ft^2 floor", "$/unit"):
            return "high"
        return "medium"

    @staticmethod
    def _unit_cost_to_total(
        unit_cost: float,
        cost_basis: str,
        dataset: str,
        sqft: float,
        sizing: dict,
    ) -> float:
        """Convert a per-unit cost into an absolute total cost."""
        basis = cost_basis.strip().lower()

        if basis in ("$/ft^2 floor", "$/ft² floor"):
            return unit_cost * sqft

        if basis in ("$/kbtu/h heating",):
            return unit_cost * _get_sizing(sizing, "heating_capacity")

        if basis in ("$/kbtu/h cooling",):
            capacity = _get_sizing(sizing, "cooling_capacity")
            if dataset == "comstock":
                # ComStock cooling capacity is in tons; convert to kBtu/h
                capacity = capacity * 12
            return unit_cost * capacity

        if basis in ("$/ft^2 wall", "$/ft² wall"):
            wall_area = _get_sizing(sizing, "wall_area")
            if dataset == "comstock":
                wall_area = wall_area * M2_TO_FT2
            return unit_cost * wall_area

        if basis in ("$/ft^2 roof", "$/ft² roof"):
            roof_area = _get_sizing(sizing, "roof_area")
            if dataset == "comstock":
                roof_area = roof_area * M2_TO_FT2
            return unit_cost * roof_area

        if basis in ("$/ft^2 glazing", "$/ft² glazing"):
            window_area = _get_sizing(sizing, "window_area")
            if dataset == "comstock":
                window_area = window_area * M2_TO_FT2
            return unit_cost * window_area

        if basis == "$/unit":
            return unit_cost

        if basis == "$/watt_dc":
            roof_area = _get_sizing(sizing, "roof_area")
            if dataset == "comstock":
                roof_area = roof_area * M2_TO_FT2
            # ~10 W/ft² panel density
            return unit_cost * roof_area * 10

        if basis in ("$/ft^2 duct", "$/ft² duct"):
            # Estimate duct area as 30% of floor area
            return unit_cost * sqft * 0.3

        if basis in ("$/kbtu/h cooking",):
            # Rough estimate: 50 kBtu/h for food-service cooking
            return unit_cost * 50

        logger.warning("Unknown cost_basis %r; returning unit_cost as total", cost_basis)
        return unit_cost

    def _resolve_mixed(
        self,
        entry: dict,
        catalog: dict,
        dataset: str,
        sqft: float,
        sizing: dict,
    ) -> tuple[float, float, float]:
        """Resolve a 'mixed (see components)' package upgrade.

        Sums the cost of each component upgrade referenced by
        ``component_upgrade_ids``.
        """
        component_ids = entry.get("component_upgrade_ids", [])
        if not component_ids:
            # Fall back to pre-computed cost_mid stored on the entry itself
            mid = float(entry.get("cost_mid") or 0)
            low = float(entry["cost_low"] if entry.get("cost_low") is not None else mid)
            high = float(entry["cost_high"] if entry.get("cost_high") is not None else mid)
            return mid, low, high

        total_mid = 0.0
        total_low = 0.0
        total_high = 0.0
        for comp_id in component_ids:
            comp = catalog.get(str(comp_id))
            if comp is None:
                logger.warning(
                    "Component upgrade %s not found in %s catalog; skipping",
                    comp_id,
                    dataset,
                )
                continue
            comp_basis = comp.get("cost_basis") or ""
            if comp_basis.startswith("mixed"):
                # Recursive packages -- resolve them too
                m, l, h = self._resolve_mixed(comp, catalog, dataset, sqft, sizing)
            else:
                comp_mid = float(comp.get("cost_mid") or 0)
                comp_low = float(comp["cost_low"] if comp.get("cost_low") is not None else comp_mid)
                comp_high = float(comp["cost_high"] if comp.get("cost_high") is not None else comp_mid)
                m = self._unit_cost_to_total(comp_mid, comp_basis, dataset, sqft, sizing)
                l = self._unit_cost_to_total(comp_low, comp_basis, dataset, sqft, sizing)
                h = self._unit_cost_to_total(comp_high, comp_basis, dataset, sqft, sizing)
            total_mid += m
            total_low += l
            total_high += h

        return total_mid, total_low, total_high
