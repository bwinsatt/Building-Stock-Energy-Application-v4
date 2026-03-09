"""
Build upgrade cost lookup table from NREL Scout ECM definitions + REMDB + gap-filling.

Reads:
  - Resources/scout/ecm_definitions/*.json (185 Scout ECM files)
  - Resources/REMDB_2024.xlsx (142 residential measures)
  - Resources/scout/scout/supporting_data/convert_data/loc_cost_adj.csv
  - Resources/scout/scout/supporting_data/convert_data/cpi.csv
  - ComStock/raw_data/upgrades_lookup.json
  - ResStock/raw_data/upgrades_lookup.json

Writes:
  - Resources/upgrade_cost_lookup.json
"""

import json
import os
import re
import csv
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
SCOUT_ECM_DIR = BASE_DIR / "Resources" / "scout" / "ecm_definitions"
SCOUT_DATA_DIR = BASE_DIR / "Resources" / "scout" / "scout" / "supporting_data" / "convert_data"
COMSTOCK_LOOKUP = BASE_DIR / "ComStock" / "raw_data" / "upgrades_lookup.json"
RESSTOCK_LOOKUP = BASE_DIR / "ResStock" / "raw_data" / "upgrades_lookup.json"
OUTPUT_FILE = BASE_DIR / "Resources" / "upgrade_cost_lookup.json"

TARGET_DOLLAR_YEAR = 2023


# =============================================================================
# Step 1: Load CPI data for dollar-year normalization
# =============================================================================

def load_cpi_annual():
    """Load CPI data, compute annual averages, return {year: avg_cpi}."""
    monthly = {}
    with open(SCOUT_DATA_DIR / "cpi.csv") as f:
        reader = csv.DictReader(f)
        for row in reader:
            year = int(row["DATE"][:4])
            val = float(row["VALUE"])
            monthly.setdefault(year, []).append(val)
    return {yr: sum(vals) / len(vals) for yr, vals in monthly.items()}


def cpi_adjust(value, from_year, to_year, cpi):
    """Adjust a dollar value from one year to another using CPI."""
    if from_year == to_year or from_year not in cpi or to_year not in cpi:
        return value
    return value * (cpi[to_year] / cpi[from_year])


# =============================================================================
# Step 2: Load regional cost adjustment factors
# =============================================================================

def load_regional_adjustments():
    """Load state-level cost multipliers from Scout/RSMeans."""
    adj = {}
    with open(SCOUT_DATA_DIR / "loc_cost_adj.csv") as f:
        reader = csv.DictReader(f)
        for row in reader:
            state = row["state"].strip()
            adj[state] = {
                "city": row["city"].strip(),
                "residential": float(row["residential"]),
                "commercial": float(row["commercial"]),
            }
    return adj


# =============================================================================
# Step 3: Parse Scout ECM files
# =============================================================================

def parse_dollar_year(cost_units_str):
    """Extract dollar year from cost_units like '2023$/kBtu/h heating' -> 2023."""
    if not isinstance(cost_units_str, str):
        return None
    m = re.match(r"(\d{4})\$", cost_units_str)
    return int(m.group(1)) if m else None


def parse_cost_basis(cost_units_str):
    """Extract the cost basis from units like '2023$/kBtu/h heating' -> '$/kBtu/h heating'."""
    if not isinstance(cost_units_str, str):
        return cost_units_str
    return re.sub(r"^\d{4}", "", cost_units_str)


def extract_cost_value(installed_cost, prefer="existing"):
    """
    Extract a single cost value from Scout's various cost formats.
    Returns (cost_mid, cost_low, cost_high, notes).
    """
    if installed_cost is None:
        return None, None, None, "no cost data"

    # Simple number
    if isinstance(installed_cost, (int, float)):
        return float(installed_cost), None, None, ""

    # {new: X, existing: Y}
    if isinstance(installed_cost, dict):
        if "new" in installed_cost and "existing" in installed_cost:
            new_val = installed_cost["new"]
            exist_val = installed_cost["existing"]
            if isinstance(new_val, (int, float)) and isinstance(exist_val, (int, float)):
                mid = float(exist_val) if prefer == "existing" else float(new_val)
                low = min(float(new_val), float(exist_val))
                high = max(float(new_val), float(exist_val))
                return mid, low, high, f"new={new_val}, existing={exist_val}"

        # Per-building-type costs (e.g., lighting)
        # Filter out non-numeric and zero values
        numeric_vals = []
        for k, v in installed_cost.items():
            if isinstance(v, (int, float)) and v > 0:
                numeric_vals.append(float(v))
            elif isinstance(v, dict) and "existing" in v:
                ev = v["existing"]
                if isinstance(ev, (int, float)) and ev > 0:
                    numeric_vals.append(float(ev))

        if numeric_vals:
            mid = sum(numeric_vals) / len(numeric_vals)
            return mid, min(numeric_vals), max(numeric_vals), f"avg of {len(numeric_vals)} values"

    return None, None, None, f"unhandled format: {type(installed_cost)}"


def extract_lifetime(product_lifetime):
    """Extract a single lifetime value from Scout's formats."""
    if isinstance(product_lifetime, (int, float)):
        return float(product_lifetime)
    if isinstance(product_lifetime, dict):
        vals = [v for v in product_lifetime.values() if isinstance(v, (int, float))]
        if vals:
            return sum(vals) / len(vals)
    return None


def extract_sources(installed_cost_source):
    """Extract citation info from Scout's source data."""
    sources = []
    if not isinstance(installed_cost_source, dict):
        return sources
    notes = installed_cost_source.get("notes", "")
    source_data = installed_cost_source.get("source_data")
    if isinstance(source_data, list):
        for s in source_data:
            if isinstance(s, dict):
                sources.append({
                    "title": s.get("title", ""),
                    "author": s.get("author", ""),
                    "year": s.get("year"),
                    "url": s.get("url", ""),
                })
    elif isinstance(source_data, dict):
        sources.append({
            "title": source_data.get("title", ""),
            "author": source_data.get("author", ""),
            "year": source_data.get("year"),
            "url": source_data.get("url", ""),
        })
    elif isinstance(source_data, str) and source_data.strip():
        sources.append({"title": source_data.strip()})
    # Add notes as context if present and no structured sources found
    if notes and not sources:
        sources.append({"notes": notes})
    elif notes and sources:
        sources[0]["notes"] = notes
    return sources


def load_scout_ecms():
    """Parse all Scout ECM JSON files into a flat dict keyed by name."""
    ecms = {}
    for fp in sorted(SCOUT_ECM_DIR.glob("*.json")):
        if fp.name == "ecm_schema.json":
            continue
        with open(fp) as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                continue

        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict) or "name" not in item:
                continue
            name = item["name"]
            cost_units_raw = item.get("cost_units", "")
            # Handle dict cost_units (e.g., walls & air sealing)
            if isinstance(cost_units_raw, dict):
                # Use first non-None value
                for v in cost_units_raw.values():
                    if v:
                        cost_units_raw = v
                        break

            dollar_year = parse_dollar_year(cost_units_raw)
            cost_basis = parse_cost_basis(cost_units_raw)
            cost_mid, cost_low, cost_high, cost_notes = extract_cost_value(
                item.get("installed_cost")
            )
            lifetime = extract_lifetime(item.get("product_lifetime"))
            sources = extract_sources(item.get("installed_cost_source", {}))

            ecms[name] = {
                "cost_mid": cost_mid,
                "cost_low": cost_low,
                "cost_high": cost_high,
                "cost_units_raw": cost_units_raw if isinstance(cost_units_raw, str) else str(cost_units_raw),
                "cost_basis": cost_basis,
                "dollar_year": dollar_year,
                "useful_life_years": lifetime,
                "sources": sources,
                "end_use": item.get("end_use"),
                "technology": item.get("technology"),
                "bldg_type": item.get("bldg_type"),
                "cost_notes": cost_notes,
            }
    return ecms


# =============================================================================
# Step 4: Build the upgrade-to-ECM mapping
# =============================================================================

def build_comstock_mapping():
    """
    Map each ComStock upgrade to Scout ECM(s) or gap-fill data.
    Returns dict: upgrade_id -> mapping info.
    """
    return {
        # --- HVAC: HP RTU variants (1-10) ---
        "1": {"scout_ecm": "(C) Best HP FS (RTU, NG Heat)", "category": "hvac_hp_rtu",
               "notes": "Variable speed HP RTU, electric backup"},
        "2": {"scout_ecm": "(C) Best HP FS (RTU, NG Heat)", "category": "hvac_hp_rtu",
               "notes": "Variable speed HP RTU, original fuel backup"},
        "3": {"scout_ecm": "(C) Best HP FS (RTU, NG Heat)", "category": "hvac_hp_rtu",
               "notes": "Variable speed HP RTU + energy recovery; cost does not include ERV adder"},
        "4": {"scout_ecm": "(C) ESTAR HP FS (RTU, NG Heat)", "category": "hvac_hp_rtu",
               "notes": "Standard performance HP RTU"},
        "5": {"scout_ecm": "(C) ESTAR HP FS (RTU, NG Heat)", "category": "hvac_hp_rtu",
               "notes": "Standard performance HP RTU using lab data"},
        "6": {"scout_ecm": "(C) ESTAR HP FS (RTU, NG Heat)", "category": "hvac_hp_rtu_plus_envelope",
               "notes": "HP RTU + roof insulation; cost is HP RTU portion only, add roof insulation cost (upgrade 49)"},
        "7": {"scout_ecm": "(C) ESTAR HP FS (RTU, NG Heat)", "category": "hvac_hp_rtu_plus_envelope",
               "notes": "HP RTU + new windows; cost is HP RTU portion only, add window cost (upgrade 52)"},
        "8": {"scout_ecm": "(C) ESTAR HP FS (RTU, NG Heat)", "category": "hvac_hp_rtu",
               "notes": "Standard HP RTU with 32F compressor lockout"},
        "9": {"scout_ecm": "(C) ESTAR HP FS (RTU, NG Heat)", "category": "hvac_hp_rtu",
               "notes": "Standard HP RTU with 2F unoccupied setback"},
        "10": {"scout_ecm": "(C) Best HP FS (RTU, NG Heat)", "category": "hvac_hp_rtu",
                "notes": "Commercial HVAC Challenge HP RTU, high performance"},

        # --- HVAC: Advanced RTU (11) ---
        "11": {"scout_ecm": "(C) Ref. Case RTU, NG Heat", "category": "hvac_rtu_controls",
                "notes": "Advanced RTU controls; cost is baseline RTU (controls upgrade is incremental)"},

        # --- HVAC: VRF (12-13) — GAP ---
        "12": {"gap_fill": True, "category": "hvac_vrf",
                "cost_mid": 350.0, "cost_low": 280.0, "cost_high": 450.0,
                "cost_basis": "$/kBtu/h cooling", "dollar_year": 2023,
                "useful_life_years": 20,
                "source_name": "EIA Updated Buildings Sector Equipment Costs 2023",
                "source_url": "https://www.eia.gov/analysis/studies/buildings/equipcosts/pdf/full.pdf",
                "notes": "VRF with DOAS. EIA commercial HVAC tables, VRF heat recovery systems."},
        "13": {"gap_fill": True, "category": "hvac_vrf",
                "cost_mid": 370.0, "cost_low": 300.0, "cost_high": 470.0,
                "cost_basis": "$/kBtu/h cooling", "dollar_year": 2023,
                "useful_life_years": 20,
                "source_name": "EIA Updated Buildings Sector Equipment Costs 2023",
                "source_url": "https://www.eia.gov/analysis/studies/buildings/equipcosts/pdf/full.pdf",
                "notes": "VRF with 25% upsizing allowance, higher cost for oversized equipment."},

        # --- HVAC: DOAS HP Minisplits (14) — GAP ---
        "14": {"gap_fill": True, "category": "hvac_minisplit",
                "cost_mid": 300.0, "cost_low": 220.0, "cost_high": 400.0,
                "cost_basis": "$/kBtu/h cooling", "dollar_year": 2023,
                "useful_life_years": 18,
                "source_name": "EIA Updated Buildings Sector Equipment Costs 2023",
                "source_url": "https://www.eia.gov/analysis/studies/buildings/equipcosts/pdf/full.pdf",
                "notes": "DOAS with HP minisplits. EIA ductless/mini-split HP tables."},

        # --- HVAC: Boilers (15-18) ---
        "15": {"scout_ecm": "(C) Best HP FS (NG Boiler)", "category": "hvac_hp_boiler",
                "notes": "HP boiler, electric backup"},
        "16": {"scout_ecm": "(C) Best HP FS (NG Boiler)", "category": "hvac_hp_boiler",
                "notes": "HP boiler, gas backup"},
        "17": {"scout_ecm": "(C) Best NG Boiler & Chiller", "category": "hvac_condensing_boiler",
                "notes": "Condensing gas boiler; using gas_boiler component cost"},
        "18": {"scout_ecm": "(C) Ref. Case Elec. Boiler FS (NG Boiler)", "category": "hvac_electric_boiler",
                "notes": "Electric resistance boiler"},

        # --- HVAC Controls (19-26) — GAPS, use PNNL/TRM estimates ---
        "19": {"gap_fill": True, "category": "hvac_controls_economizer",
                "cost_mid": 2.50, "cost_low": 1.50, "cost_high": 4.00,
                "cost_basis": "$/ft^2 floor", "dollar_year": 2020,
                "useful_life_years": 15,
                "source_name": "PNNL ASHRAE 90.1-2019 Cost-Effectiveness Analysis",
                "source_url": "",
                "notes": "Air side economizers for AHUs. PNNL commercial HVAC controls cost per sqft."},
        "20": {"gap_fill": True, "category": "hvac_controls_dcv",
                "cost_mid": 1.50, "cost_low": 0.75, "cost_high": 2.50,
                "cost_basis": "$/ft^2 floor", "dollar_year": 2020,
                "useful_life_years": 15,
                "source_name": "PNNL ASHRAE 90.1-2019 Cost-Effectiveness Analysis",
                "source_url": "",
                "notes": "Demand control ventilation. CO2 sensors + controls."},
        "21": {"gap_fill": True, "category": "hvac_controls_erv",
                "cost_mid": 3.00, "cost_low": 2.00, "cost_high": 5.00,
                "cost_basis": "$/ft^2 floor", "dollar_year": 2020,
                "useful_life_years": 20,
                "source_name": "PNNL ASHRAE 90.1-2019 Cost-Effectiveness Analysis",
                "source_url": "",
                "notes": "Energy recovery ventilator for AHUs. Includes enthalpy wheel or plate HX."},
        "22": {"gap_fill": True, "category": "hvac_controls_rtu",
                "cost_mid": 1.00, "cost_low": 0.50, "cost_high": 2.00,
                "cost_basis": "$/ft^2 floor", "dollar_year": 2020,
                "useful_life_years": 15,
                "source_name": "PNNL ASHRAE 90.1-2019 Cost-Effectiveness Analysis",
                "source_url": "",
                "notes": "Advanced RTU controls. Retrofit controller add-on."},
        "23": {"gap_fill": True, "category": "hvac_controls_unoccupied",
                "cost_mid": 0.75, "cost_low": 0.25, "cost_high": 1.50,
                "cost_basis": "$/ft^2 floor", "dollar_year": 2020,
                "useful_life_years": 15,
                "source_name": "PNNL ASHRAE 90.1-2019 Cost-Effectiveness Analysis",
                "source_url": "",
                "notes": "Unoccupied AHU control. Schedule programming + occupancy sensors."},
        "24": {"gap_fill": True, "category": "hvac_controls_fan",
                "cost_mid": 1.00, "cost_low": 0.50, "cost_high": 2.00,
                "cost_basis": "$/ft^2 floor", "dollar_year": 2020,
                "useful_life_years": 15,
                "source_name": "PNNL ASHRAE 90.1-2019 Cost-Effectiveness Analysis",
                "source_url": "",
                "notes": "Fan static pressure reset for multizone VAV. Controls upgrade."},
        "25": {"gap_fill": True, "category": "hvac_controls_setback",
                "cost_mid": 0.50, "cost_low": 0.10, "cost_high": 1.00,
                "cost_basis": "$/ft^2 floor", "dollar_year": 2020,
                "useful_life_years": 15,
                "source_name": "PNNL ASHRAE 90.1-2019 Cost-Effectiveness Analysis",
                "source_url": "",
                "notes": "Thermostat setbacks. Programmable thermostat or BMS schedule change."},
        "26": {"gap_fill": True, "category": "hvac_controls_vfd",
                "cost_mid": 2.00, "cost_low": 1.00, "cost_high": 3.50,
                "cost_basis": "$/ft^2 floor", "dollar_year": 2020,
                "useful_life_years": 15,
                "source_name": "PNNL ASHRAE 90.1-2019 Cost-Effectiveness Analysis",
                "source_url": "",
                "notes": "VFD pumps. Variable frequency drive retrofit on hydronic pumps."},

        # --- HVAC: Ideal Loads (27) — EXCLUDED ---
        "27": {"excluded": True, "category": "theoretical_benchmark",
                "notes": "Ideal thermal air loads — theoretical max savings, not a real measure."},

        # --- HVAC: Geothermal (28-30) ---
        "28": {"scout_ecm": "(C) Ref. Case GSHP", "category": "hvac_geothermal",
                "notes": "Hydronic water-to-water GHP. Includes bore field costs."},
        "29": {"scout_ecm": "(C) Ref. Case GSHP", "category": "hvac_geothermal",
                "notes": "Packaged water-to-air GHP."},
        "30": {"scout_ecm": "(C) Ref. Case GSHP", "category": "hvac_geothermal",
                "notes": "Console water-to-air GHP."},

        # --- HVAC: Chiller (31) ---
        "31": {"scout_ecm": "(C) Best NG Boiler & Chiller", "category": "hvac_chiller",
                "notes": "Chiller replacement; using chiller component costs from Scout ECM."},

        # --- Demand Flexibility (32-42) — low-cost controls ---
        **{str(i): {"gap_fill": True, "category": "demand_flexibility",
                     "cost_mid": 1.00, "cost_low": 0.25, "cost_high": 2.00,
                     "cost_basis": "$/ft^2 floor", "dollar_year": 2023,
                     "useful_life_years": 10,
                     "source_name": "Industry estimate — BMS controls programming",
                     "source_url": "",
                     "notes": "Controls-only measure. Cost = BMS programming + smart thermostat/lighting controls."}
           for i in range(32, 43)},

        # --- Lighting (43-44) ---
        "43": {"scout_ecm": "(C) 90.1 Lighting", "category": "lighting_led",
                "notes": "LED lighting retrofit"},
        "44": {"scout_ecm": "(C) 90.1 Lighting", "category": "lighting_controls",
                "notes": "Lighting controls; using lighting ECM as proxy (controls are a fraction of full retrofit cost)"},

        # --- Kitchen (45) ---
        "45": {"scout_ecm": "(C) Induction Range FS", "category": "kitchen_electric",
                "notes": "Electric/induction kitchen equipment replacing gas"},

        # --- Solar PV & Battery (46-47) — GAP, use NREL ATB ---
        "46": {"gap_fill": True, "category": "solar_pv",
                "cost_mid": 2.00, "cost_low": 1.50, "cost_high": 2.80,
                "cost_basis": "$/watt_dc", "dollar_year": 2023,
                "useful_life_years": 25,
                "source_name": "NREL Annual Technology Baseline 2024 — Commercial Rooftop PV",
                "source_url": "https://atb.nrel.gov/",
                "notes": "PV with 40% roof coverage. Cost is $/Wdc installed."},
        "47": {"gap_fill": True, "category": "solar_pv_battery",
                "cost_mid": 2.80, "cost_low": 2.10, "cost_high": 3.80,
                "cost_basis": "$/watt_dc", "dollar_year": 2023,
                "useful_life_years": 20,
                "source_name": "NREL Annual Technology Baseline 2024 — Commercial PV + Battery",
                "source_url": "https://atb.nrel.gov/",
                "notes": "PV + battery storage. Blended $/Wdc including battery."},

        # --- Envelope (48-53) ---
        "48": {"scout_ecm": "(C) BTO RDO Walls", "category": "envelope_wall",
                "notes": "Wall insulation retrofit"},
        "49": {"scout_ecm": "(C) BTO RDO Roofs", "category": "envelope_roof",
                "notes": "Roof insulation retrofit"},
        "50": {"scout_ecm": "(C) 90.1-2022 Windows", "category": "envelope_window_secondary",
                "notes": "Secondary windows (interior storm); using window ECM as upper bound proxy"},
        "51": {"gap_fill": True, "category": "envelope_window_film",
                "cost_mid": 10.00, "cost_low": 7.00, "cost_high": 15.00,
                "cost_basis": "$/ft^2 glazing", "dollar_year": 2023,
                "useful_life_years": 15,
                "source_name": "Industry estimate — commercial window film installation",
                "source_url": "",
                "notes": "Window film applied to interior glazing surface."},
        "52": {"scout_ecm": "(C) 90.1-2022 Windows", "category": "envelope_window_new",
                "notes": "New window replacement"},
        "53": {"scout_ecm": "(C) 90.1-2022 Walls & Air Sealing", "category": "envelope_code",
                "notes": "Code-level envelope upgrade (walls + air sealing)"},

        # --- Packages (54-65) — sum of components ---
        "54": {"package_of": ["48", "49", "52"], "category": "package",
                "notes": "Package 1: Wall + Roof Insulation + New Windows"},
        "55": {"package_of": ["43", "1", "15"], "category": "package",
                "notes": "Package 2: LED + Variable Speed HP RTU or HP Boilers"},
        "56": {"package_of": ["43", "4"], "category": "package",
                "notes": "Package 3: Package 2 with Standard Performance HP RTU"},
        "57": {"package_of": ["48", "49", "52", "43", "1", "15"], "category": "package",
                "notes": "Package 4: Package 1 + Package 2"},
        "58": {"package_of": ["1", "15", "19", "20", "21"], "category": "package",
                "notes": "Package 5: HP RTU or HP Boilers + Economizer + DCV + Energy Recovery"},
        "59": {"package_of": ["28", "29", "30"], "category": "package",
                "notes": "Package 6: Geothermal HP (any variant)"},
        "60": {"package_of": ["37", "36"], "category": "package",
                "notes": "Package 7: Demand Flex Lighting + Thermostat for Grid Peak"},
        "61": {"package_of": ["34", "32", "46"], "category": "package",
                "notes": "Package 8: Demand Flex Lighting + Thermostat for Daily Peak + PV"},
        "62": {"package_of": ["34", "32"], "category": "package",
                "notes": "Package 9: Demand Flex Lighting + Thermostat for Daily Peak"},
        "63": {"package_of": ["48", "49", "52", "28"], "category": "package",
                "notes": "Package 10: Package 1 + Package 6 (Envelope + GHP)"},
        "64": {"package_of": ["48", "49", "52", "28", "43"], "category": "package",
                "notes": "Package 11: Package 10 + LED Lighting"},
        "65": {"package_of": ["46", "49"], "category": "package",
                "notes": "Package 12: PV + Roof Insulation"},
    }


def build_resstock_mapping():
    """Map each ResStock upgrade to Scout ECM(s) or gap-fill data."""
    return {
        # --- HVAC: Furnaces (1-3) ---
        "1": {"scout_ecm": "(R) Best NG Furnace & AC", "category": "hvac_furnace",
               "notes": "NG furnace 95% AFUE. Scout 'Best' tier cost."},
        "2": {"scout_ecm": "(R) Best NG Furnace & AC", "category": "hvac_furnace",
               "notes": "Propane/fuel oil furnace 95% AFUE. Same cost basis as NG furnace."},
        "3": {"scout_ecm": "(R) Min. Efficiency ASHP FS (NG Furnace)", "category": "hvac_min_efficiency",
               "notes": "Minimum efficiency boilers, furnaces, and ACs circa 2025."},

        # --- HVAC: Heat Pumps (4-5) ---
        "4": {"scout_ecm": "(R) ESTAR HP FS (NG Furnace)", "category": "hvac_ashp",
               "notes": "Cold climate ducted ASHP. ENERGY STAR tier."},
        "5": {"scout_ecm": "(R) ESTAR HP FS (NG Furnace)", "category": "hvac_dual_fuel",
               "notes": "Dual fuel heating system. ASHP + gas furnace backup."},

        # --- HVAC: Geothermal (6-8) ---
        "6": {"scout_ecm": "(R) ESTAR GSHP (NG Furnace)", "category": "hvac_gshp",
               "notes": "Single-speed GSHP with thermally enhanced grout and pipes."},
        "7": {"scout_ecm": "(R) ESTAR GSHP (NG Furnace)", "category": "hvac_gshp",
               "notes": "Dual-speed GSHP. Same installed cost as single-speed."},
        "8": {"scout_ecm": "(R) ESTAR GSHP (NG Furnace)", "category": "hvac_gshp",
               "notes": "Variable-speed GSHP. Premium unit, same installed cost basis."},

        # --- Water Heating (9-10) ---
        "9": {"scout_ecm": "(R) Best HPWH FS", "category": "water_heater_hp",
               "notes": "Heat pump water heater."},
        "10": {"scout_ecm": "(R) Best Gas WH", "category": "water_heater_gas",
                "notes": "High efficiency NG tankless water heater."},

        # --- Envelope: Air Sealing (11) ---
        "11": {"scout_ecm": "(R) BTO RDO Air Sealing", "category": "envelope_air_sealing",
                "notes": "Air sealing. Cost in $/ft^2 wall area."},

        # --- Envelope: Attic Insulation (12) ---
        "12": {"scout_ecm": "(R) IECC 2021 Roofs", "category": "envelope_attic_insulation",
                "notes": "Attic floor insulation for unfinished attics. Using roof insulation ECM."},

        # --- Envelope: Duct Sealing (13) ---
        "13": {"gap_fill": True, "category": "envelope_duct",
                "cost_mid": 1.50, "cost_low": 0.80, "cost_high": 2.50,
                "cost_basis": "$/ft^2 duct", "dollar_year": 2023,
                "useful_life_years": 20,
                "source_name": "NREL REMDB 2024 — Duct Sealing + Duct Insulation",
                "source_url": "https://remdb.nrel.gov/",
                "notes": "Duct sealing and insulation. Combined REMDB duct measures."},

        # --- Envelope: Drill-and-Fill Wall + Air Sealing (14) ---
        "14": {"scout_ecm": "(R) BTO RDO Walls", "category": "envelope_wall_insulation",
                "notes": "Drill and fill wall insulation with air sealing. Wall insulation ECM."},

        # --- Envelope Packages (15-16) ---
        "15": {"package_of": ["11", "12", "13"], "category": "package",
                "notes": "Air Sealing + Attic Insulation + Duct Sealing"},
        "16": {"package_of": ["11", "12", "13", "14"], "category": "package",
                "notes": "Air Sealing + Attic Insulation + Duct Sealing + Wall Insulation"},

        # --- Windows (17) ---
        "17": {"scout_ecm": "(R) ENERGY STAR Windows", "category": "envelope_windows",
                "notes": "ENERGY STAR windows."},

        # --- Full Package (18) ---
        "18": {"package_of": ["7", "11", "12", "13"], "category": "package",
                "notes": "Dual-speed GSHP + Air Sealing + Attic Insulation + Duct Sealing"},

        # --- EV Charging (19-23) ---
        "19": {"gap_fill": True, "category": "ev_charging",
                "cost_mid": 300.0, "cost_low": 200.0, "cost_high": 500.0,
                "cost_basis": "$/unit", "dollar_year": 2023,
                "useful_life_years": 15,
                "source_name": "NREL REMDB 2024 — EV Charger",
                "source_url": "https://remdb.nrel.gov/",
                "notes": "EV Level 1 charging. Charger hardware only, vehicle cost excluded."},
        "20": {"gap_fill": True, "category": "ev_charging",
                "cost_mid": 1500.0, "cost_low": 1000.0, "cost_high": 2500.0,
                "cost_basis": "$/unit", "dollar_year": 2023,
                "useful_life_years": 15,
                "source_name": "NREL REMDB 2024 — EV Charger",
                "source_url": "https://remdb.nrel.gov/",
                "notes": "EV Level 2 charging. Includes 240V wiring and charger."},
        "21": {"gap_fill": True, "category": "ev_charging",
                "cost_mid": 1500.0, "cost_low": 1000.0, "cost_high": 2500.0,
                "cost_basis": "$/unit", "dollar_year": 2023,
                "useful_life_years": 15,
                "source_name": "NREL REMDB 2024 — EV Charger",
                "source_url": "https://remdb.nrel.gov/",
                "notes": "Efficient EV with L2 charging. Same charger cost, vehicle cost excluded."},
        "22": {"gap_fill": True, "category": "ev_charging_demand_flex",
                "cost_mid": 1700.0, "cost_low": 1100.0, "cost_high": 2700.0,
                "cost_basis": "$/unit", "dollar_year": 2023,
                "useful_life_years": 15,
                "source_name": "NREL REMDB 2024 — EV Charger + Smart Thermostat",
                "source_url": "https://remdb.nrel.gov/",
                "notes": "EV L2 charging + demand flexibility. Charger + smart thermostat."},
        "23": {"gap_fill": True, "category": "ev_charging_demand_flex",
                "cost_mid": 1700.0, "cost_low": 1100.0, "cost_high": 2700.0,
                "cost_basis": "$/unit", "dollar_year": 2023,
                "useful_life_years": 15,
                "source_name": "NREL REMDB 2024 — EV Charger + Smart Thermostat",
                "source_url": "https://remdb.nrel.gov/",
                "notes": "Efficient EV L2 + demand flexibility. Same charger cost."},

        # --- Demand Flexibility (24-28) ---
        **{str(i): {"gap_fill": True, "category": "demand_flexibility",
                      "cost_mid": 250.0, "cost_low": 150.0, "cost_high": 350.0,
                      "cost_basis": "$/unit", "dollar_year": 2023,
                      "useful_life_years": 10,
                      "source_name": "NREL REMDB 2024 — Thermostat, Smart",
                      "source_url": "https://remdb.nrel.gov/",
                      "notes": "HVAC demand flexibility via smart thermostat. Controls-only measure."}
            for i in range(24, 29)},

        # --- General Air Sealing (29) ---
        "29": {"scout_ecm": "(R) BTO RDO Air Sealing", "category": "envelope_air_sealing",
                "notes": "General air sealing."},

        # --- Packages (30-32) ---
        "30": {"package_of": ["29", "12", "13"], "category": "package",
                "notes": "General Air Sealing + Attic Insulation + Duct Sealing"},
        "31": {"package_of": ["7", "29", "12", "13"], "category": "package",
                "notes": "Dual-speed GSHP + General Air Sealing + Attic Insulation + Duct Sealing"},
        "32": {"package_of": ["8", "29", "12", "13"], "category": "package",
                "notes": "Variable-speed GSHP + General Air Sealing + Attic Insulation + Duct Sealing"},
    }


# =============================================================================
# Step 5: Build the final lookup table
# =============================================================================

def build_upgrade_entry(upgrade_id, upgrade_name, mapping, scout_ecms, cpi, dataset):
    """Build a single upgrade cost entry."""
    # Excluded measures
    if mapping.get("excluded"):
        return {
            "upgrade_id": int(upgrade_id),
            "dataset": dataset,
            "upgrade_name": upgrade_name,
            "measure_category": mapping["category"],
            "excluded": True,
            "notes": mapping["notes"],
        }

    # Package measures — sum of components
    if "package_of" in mapping:
        return {
            "upgrade_id": int(upgrade_id),
            "dataset": dataset,
            "upgrade_name": upgrade_name,
            "measure_category": "package",
            "is_package": True,
            "component_upgrade_ids": [int(x) for x in mapping["package_of"]],
            "cost_method": "sum_of_components",
            "notes": mapping["notes"],
        }

    # Gap-fill measures
    if mapping.get("gap_fill"):
        cost_mid_2023 = cpi_adjust(
            mapping["cost_mid"], mapping["dollar_year"], TARGET_DOLLAR_YEAR, cpi
        )
        cost_low_2023 = cpi_adjust(
            mapping["cost_low"], mapping["dollar_year"], TARGET_DOLLAR_YEAR, cpi
        ) if mapping.get("cost_low") else None
        cost_high_2023 = cpi_adjust(
            mapping["cost_high"], mapping["dollar_year"], TARGET_DOLLAR_YEAR, cpi
        ) if mapping.get("cost_high") else None

        return {
            "upgrade_id": int(upgrade_id),
            "dataset": dataset,
            "upgrade_name": upgrade_name,
            "measure_category": mapping["category"],
            "cost_mid": round(cost_mid_2023, 2),
            "cost_low": round(cost_low_2023, 2) if cost_low_2023 else None,
            "cost_high": round(cost_high_2023, 2) if cost_high_2023 else None,
            "cost_basis": mapping["cost_basis"],
            "cost_year_dollars": TARGET_DOLLAR_YEAR,
            "useful_life_years": mapping.get("useful_life_years"),
            "cost_type": "full_replacement",
            "scout_ecm_name": None,
            "confidence": "low",
            "sources": [{
                "name": mapping["source_name"],
                "url": mapping.get("source_url", ""),
            }],
            "notes": mapping["notes"],
        }

    # Scout ECM-based measures
    ecm_name = mapping["scout_ecm"]
    ecm = scout_ecms.get(ecm_name)
    if not ecm:
        return {
            "upgrade_id": int(upgrade_id),
            "dataset": dataset,
            "upgrade_name": upgrade_name,
            "measure_category": mapping["category"],
            "error": f"Scout ECM not found: {ecm_name}",
            "notes": mapping["notes"],
        }

    # CPI-adjust cost to target year
    source_year = ecm["dollar_year"] or TARGET_DOLLAR_YEAR
    cost_mid = cpi_adjust(ecm["cost_mid"], source_year, TARGET_DOLLAR_YEAR, cpi) if ecm["cost_mid"] else None
    cost_low = cpi_adjust(ecm["cost_low"], source_year, TARGET_DOLLAR_YEAR, cpi) if ecm["cost_low"] else None
    cost_high = cpi_adjust(ecm["cost_high"], source_year, TARGET_DOLLAR_YEAR, cpi) if ecm["cost_high"] else None

    # Build source citations
    sources = []
    for s in ecm.get("sources", []):
        sources.append({
            "title": s.get("title", ""),
            "author": s.get("author", ""),
            "year": s.get("year"),
            "url": s.get("url", ""),
        })
    if not sources:
        sources = [{"name": f"NREL Scout ECM: {ecm_name}"}]

    return {
        "upgrade_id": int(upgrade_id),
        "dataset": dataset,
        "upgrade_name": upgrade_name,
        "measure_category": mapping["category"],
        "cost_mid": round(cost_mid, 2) if cost_mid is not None else None,
        "cost_low": round(cost_low, 2) if cost_low is not None else None,
        "cost_high": round(cost_high, 2) if cost_high is not None else None,
        "cost_basis": ecm["cost_basis"],
        "cost_year_dollars": TARGET_DOLLAR_YEAR,
        "useful_life_years": ecm["useful_life_years"],
        "cost_type": "full_replacement",
        "scout_ecm_name": ecm_name,
        "confidence": "high" if len(sources) > 0 and sources[0].get("title") else "moderate",
        "sources": sources,
        "notes": mapping["notes"],
    }


def main():
    print("Loading CPI data...")
    cpi = load_cpi_annual()
    print(f"  CPI 2020={cpi.get(2020, 'N/A'):.1f}, 2022={cpi.get(2022, 'N/A'):.1f}, 2023={cpi.get(2023, 'N/A'):.1f}")

    print("Loading regional adjustments...")
    regional = load_regional_adjustments()
    print(f"  {len(regional)} states loaded")

    print("Parsing Scout ECMs...")
    scout_ecms = load_scout_ecms()
    print(f"  {len(scout_ecms)} ECMs parsed")

    print("Loading upgrade lookups...")
    with open(COMSTOCK_LOOKUP) as f:
        comstock_names = json.load(f)
    with open(RESSTOCK_LOOKUP) as f:
        resstock_names = json.load(f)

    print("Building ComStock mapping...")
    comstock_mapping = build_comstock_mapping()

    print("Building ResStock mapping...")
    resstock_mapping = build_resstock_mapping()

    # Build ComStock entries
    comstock_entries = {}
    for uid, name in comstock_names.items():
        if uid == "0":  # Skip baseline
            continue
        mapping = comstock_mapping.get(uid)
        if not mapping:
            comstock_entries[uid] = {
                "upgrade_id": int(uid),
                "dataset": "comstock",
                "upgrade_name": name,
                "error": "No mapping defined",
            }
            continue
        comstock_entries[uid] = build_upgrade_entry(
            uid, name, mapping, scout_ecms, cpi, "comstock"
        )

    # Build ResStock entries
    resstock_entries = {}
    for uid, name in resstock_names.items():
        if uid == "0":  # Skip baseline
            continue
        mapping = resstock_mapping.get(uid)
        if not mapping:
            resstock_entries[uid] = {
                "upgrade_id": int(uid),
                "dataset": "resstock",
                "upgrade_name": name,
                "error": "No mapping defined",
            }
            continue
        resstock_entries[uid] = build_upgrade_entry(
            uid, name, mapping, scout_ecms, cpi, "resstock"
        )

    # Resolve package costs
    def resolve_package(entries, entry):
        if not entry.get("is_package"):
            return
        component_ids = entry["component_upgrade_ids"]
        total_mid = 0
        total_low = 0
        total_high = 0
        has_all = True
        component_names = []
        for cid in component_ids:
            comp = entries.get(str(cid))
            if not comp or comp.get("is_package") or comp.get("excluded"):
                has_all = False
                continue
            if comp.get("cost_mid") is not None:
                total_mid += comp["cost_mid"]
                total_low += comp.get("cost_low") or comp["cost_mid"]
                total_high += comp.get("cost_high") or comp["cost_mid"]
                component_names.append(f"[{cid}] {comp.get('upgrade_name', '')}")
            else:
                has_all = False

        if has_all and total_mid > 0:
            entry["cost_mid"] = round(total_mid, 2)
            entry["cost_low"] = round(total_low, 2)
            entry["cost_high"] = round(total_high, 2)
            # Use the cost basis of the first component with one
            first_comp = entries.get(str(component_ids[0]), {})
            entry["cost_basis"] = "mixed (see components)"
            entry["cost_year_dollars"] = TARGET_DOLLAR_YEAR
            entry["useful_life_years"] = None  # varies by component
            entry["confidence"] = "moderate"
            entry["sources"] = [{"name": "Sum of component upgrade costs"}]
            entry["component_details"] = component_names

    for entry in comstock_entries.values():
        resolve_package(comstock_entries, entry)
    for entry in resstock_entries.values():
        resolve_package(resstock_entries, entry)

    # Assemble final output
    output = {
        "metadata": {
            "version": "1.0",
            "cost_year_dollars": TARGET_DOLLAR_YEAR,
            "generated": datetime.now().strftime("%Y-%m-%d"),
            "notes": (
                "National average installed costs. Apply regional_adjustments multipliers "
                "by state for location-adjusted costs. Costs are full replacement unless noted. "
                "Package costs are sums of component upgrade costs."
            ),
            "sources_summary": {
                "primary": "NREL Scout ECM Definitions (github.com/trynthink/scout)",
                "secondary": "NREL REMDB 2024 (remdb.nrel.gov)",
                "regional": "RSMeans city cost indices via Scout loc_cost_adj.csv",
                "cpi": "BLS CPI-U via Scout cpi.csv",
                "gap_fill": [
                    "EIA Updated Buildings Sector Equipment Costs 2023",
                    "PNNL ASHRAE 90.1-2019 Cost-Effectiveness Analysis",
                    "NREL Annual Technology Baseline 2024",
                    "Industry estimates for demand flexibility and window film",
                ],
            },
        },
        "comstock": comstock_entries,
        "resstock": resstock_entries,
        "regional_adjustments": regional,
    }

    # Write output
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    # Summary stats
    print(f"\nOutput written to: {OUTPUT_FILE}")
    print(f"\nComStock upgrades: {len(comstock_entries)}")
    cs_with_cost = sum(1 for e in comstock_entries.values()
                       if e.get("cost_mid") is not None)
    cs_packages = sum(1 for e in comstock_entries.values()
                      if e.get("is_package"))
    cs_excluded = sum(1 for e in comstock_entries.values()
                      if e.get("excluded"))
    cs_gaps = sum(1 for e in comstock_entries.values()
                  if e.get("confidence") == "low")
    print(f"  With cost data: {cs_with_cost}")
    print(f"  Packages (resolved): {cs_packages}")
    print(f"  Excluded: {cs_excluded}")
    print(f"  Low confidence (gap-filled): {cs_gaps}")

    print(f"\nResStock upgrades: {len(resstock_entries)}")
    rs_with_cost = sum(1 for e in resstock_entries.values()
                       if e.get("cost_mid") is not None)
    rs_packages = sum(1 for e in resstock_entries.values()
                      if e.get("is_package"))
    rs_gaps = sum(1 for e in resstock_entries.values()
                  if e.get("confidence") == "low")
    print(f"  With cost data: {rs_with_cost}")
    print(f"  Packages (resolved): {rs_packages}")
    print(f"  Low confidence (gap-filled): {rs_gaps}")

    print(f"\nRegional adjustments: {len(regional)} states")
    print(f"  Range: {min(r['commercial'] for r in regional.values()):.2f} - "
          f"{max(r['commercial'] for r in regional.values()):.2f} (commercial)")


if __name__ == "__main__":
    main()
