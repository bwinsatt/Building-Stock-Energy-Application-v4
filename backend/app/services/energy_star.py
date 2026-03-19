import os
import xml.etree.ElementTree as ET
from typing import Optional

from app.schemas.request import BuildingInput
from app.schemas.response import BaselineResult

BUILDING_TYPE_TO_ESPM = {
    "Office": "Office",
    "Warehouse and Storage": "Non-Refrigerated Warehouse",
    "Mercantile": "Retail Store",
    "Lodging": "Hotel",
    "Healthcare": "Hospital (General Medical & Surgical)",
    "Education": "K-12 School",
    "Food Sales": "Supermarket/Grocery Store",
    "Food Service": "Restaurant",
    "Multi-Family": "Multifamily Housing",
    "Public Assembly": "Convention Center",
    "Public Order and Safety": "Courthouse",
    "Religious Worship": "Worship Facility",
    "Service": "Other - Services",
    "Mixed Use": "Mixed Use Property",
}

ESPM_PROPERTY_USE_ELEMENT = {
    "Office": "office",
    "Non-Refrigerated Warehouse": "nonRefrigeratedWarehouse",
    "Retail Store": "retail",
    "Hotel": "hotel",
    "Hospital (General Medical & Surgical)": "hospital",
    "K-12 School": "k12School",
    "Supermarket/Grocery Store": "supermarket",
    "Restaurant": "restaurant",
    "Multifamily Housing": "multifamilyHousing",
    "Convention Center": "other",
    "Courthouse": "other",
    "Worship Facility": "worshipFacility",
    "Other - Services": "other",
    "Mixed Use Property": "other",
}

FUEL_MAPPING = {
    "electricity": {"energyType": "Electric", "energyUnit": "kBtu (thousand Btu)"},
    "natural_gas": {"energyType": "Natural Gas", "energyUnit": "kBtu (thousand Btu)"},
    "fuel_oil": {"energyType": "Fuel Oil No 2", "energyUnit": "kBtu (thousand Btu)"},
    "propane": {"energyType": "Propane", "energyUnit": "kBtu (thousand Btu)"},
    "district_heating": {"energyType": "District Steam", "energyUnit": "kBtu (thousand Btu)"},
}

ESPM_BASE_URL = os.environ.get("ESPM_BASE_URL", "https://portfoliomanager.energystar.gov/wstest")
ESPM_USERNAME = os.environ.get("ESPM_USERNAME", "")
ESPM_PASSWORD = os.environ.get("ESPM_PASSWORD", "")
ESPM_TIMEOUT = 15


def build_target_finder_xml(
    building: BuildingInput,
    baseline: BaselineResult,
    address: Optional[str],
    state: str,
) -> str:
    """Build an XML string for the ENERGY STAR Target Finder API."""
    if building.building_type not in BUILDING_TYPE_TO_ESPM:
        raise ValueError(f"Building type '{building.building_type}' is not mapped to an ESPM property type.")

    espm_type = BUILDING_TYPE_TO_ESPM[building.building_type]
    use_element = ESPM_PROPERTY_USE_ELEMENT.get(espm_type, "other")

    name_value = f"{building.building_type} - {address or building.zipcode}"
    sqft_int = int(building.sqft)

    root = ET.Element("targetFinder")

    # propertyInfo
    prop_info = ET.SubElement(root, "propertyInfo")
    ET.SubElement(prop_info, "name").text = name_value
    ET.SubElement(prop_info, "primaryFunction").text = espm_type

    gfa = ET.SubElement(prop_info, "grossFloorArea", units="Square Feet", temporary="false")
    ET.SubElement(gfa, "value").text = str(sqft_int)

    ET.SubElement(prop_info, "plannedConstructionCompletionYear").text = str(building.year_built)

    ET.SubElement(
        prop_info,
        "address",
        address1=address or "N/A",
        postalCode=building.zipcode,
        state=state,
        country="US",
    )
    ET.SubElement(prop_info, "numberOfBuildings").text = "1"

    # propertyUses
    prop_uses = ET.SubElement(root, "propertyUses")
    use_el = ET.SubElement(prop_uses, use_element)
    ET.SubElement(use_el, "name").text = building.building_type
    use_details = ET.SubElement(use_el, "useDetails")
    total_gfa = ET.SubElement(use_details, "totalGrossFloorArea", units="Square Feet")
    ET.SubElement(total_gfa, "value").text = str(sqft_int)

    # estimatedEnergyList
    energy_list = ET.SubElement(root, "estimatedEnergyList")
    entries = ET.SubElement(energy_list, "entries")

    fuel_values = {
        "electricity": baseline.eui_by_fuel.electricity,
        "natural_gas": baseline.eui_by_fuel.natural_gas,
        "fuel_oil": baseline.eui_by_fuel.fuel_oil,
        "propane": baseline.eui_by_fuel.propane,
        "district_heating": baseline.eui_by_fuel.district_heating,
    }

    for fuel_key, eui_kbtu_sf in fuel_values.items():
        if eui_kbtu_sf <= 0:
            continue
        mapping = FUEL_MAPPING[fuel_key]
        annual_kbtu = eui_kbtu_sf * building.sqft
        entry = ET.SubElement(entries, "designEntry")
        ET.SubElement(entry, "energyType").text = mapping["energyType"]
        ET.SubElement(entry, "energyUnit").text = "kBtu (thousand Btu)"
        ET.SubElement(entry, "estimatedAnnualEnergyUsage").text = str(annual_kbtu)

    # target
    target = ET.SubElement(root, "target")
    score_node = ET.SubElement(target, "targetTypeScore")
    ET.SubElement(score_node, "value").text = "75"

    return ET.tostring(root, encoding="unicode", xml_declaration=False)
