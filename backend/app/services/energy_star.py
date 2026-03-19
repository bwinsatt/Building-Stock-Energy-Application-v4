import os

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
