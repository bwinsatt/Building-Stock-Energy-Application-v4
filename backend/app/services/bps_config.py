"""BPS ordinance configuration — endpoints, field mappings, and zipcode overrides."""
import os

# Socrata app token from environment (public app token, not a secret key)
BPS_SOCRATA_TOKEN = os.environ.get("BPS_SOCRATA_TOKEN", "")

BPS_CONFIGS: dict = {
    "state": {
        "california": {
            "ordinance_name": "CA AB802",
            "endpoints": {
                "2018": {"Benchmarking": "CA_AB802_database, 2025.04.28.csv"},
            },
            "address_field": "Address",
            "api_type": "csv",
        },
        "colorado": {
            "ordinance_name": "CO BPS",
            "endpoints": {
                "2022": {"Benchmarking": "CO_BPS_2022-2025, 2025.05.07.csv"},
            },
            "address_field": "address_line_1_107",
            "api_type": "csv",
        },
    },
    "county": {
        "montgomery county, maryland": {
            "ordinance_name": "Montgomery County Benchmarking",
            "endpoints": {
                "2023": {"Benchmarking": "https://data.montgomerycountymd.gov/resource/ensr-8pr2.json"},
            },
            "address_field": "address",
            "api_type": "socrata",
        },
    },
    "city": {
        "new york, new york": {
            "ordinance_name": "NYC LL84",
            "endpoints": {
                "2024": {"Benchmarking": "https://data.cityofnewyork.us/resource/5zyy-y8am.json"},
                "2022": {"Benchmarking": "https://data.cityofnewyork.us/resource/7x5e-2fxh.json"},
            },
            "address_field": "address_1",
            "api_type": "socrata",
        },
        "denver, colorado": {
            "ordinance_name": "Energize Denver",
            "endpoints": {
                "2023": {"Benchmarking": "https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/ArcGIS/rest/services/_2023_Final_Master_Dataset/FeatureServer/0/query"},
                "2022": {"Benchmarking": "https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/arcgis/rest/services/ODC__2022_Final_Master_Dataset/FeatureServer/28/query"},
            },
            "address_field": "Street",
            "api_type": "arcgis",
        },
        "washington, district of columbia": {
            "ordinance_name": "DC BEPS",
            "endpoints": {
                "2023": {"Benchmarking": "https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/Environment_Energy_WebMercator/MapServer/45/query"},
            },
            "address_field": "ADDRESSOFRECORD",
            "alt_address_field": "REPORTEDADDRESS",
            "api_type": "arcgis",
        },
        "atlanta, georgia": {
            "ordinance_name": "Atlanta CBEEO",
            "endpoints": {
                "2019": {"Benchmarking": "https://services5.arcgis.com/5RxyIIJ9boPdptdo/ArcGIS/rest/services/Energy_Ratings/FeatureServer/14/query"},
            },
            "address_field": "Match_addr",
            "api_type": "arcgis",
        },
        "austin, texas": {
            "ordinance_name": "Austin ECAD",
            "endpoints": {
                "2019": {"Benchmarking": "https://data.austintexas.gov/resource/rs4a-x7f5.json"},
            },
            "address_field": "commercial_property_property_street_address",
            "api_type": "socrata",
        },
        "chicago, illinois": {
            "ordinance_name": "Chicago Benchmarking",
            "endpoints": {
                "2023": {"Benchmarking": "https://data.cityofchicago.org/resource/xq83-jr8c.json"},
            },
            "address_field": "address",
            "api_type": "socrata",
        },
        "los angeles, california": {
            "ordinance_name": "LA EBEWE",
            "endpoints": {
                "2023": {"Benchmarking": "https://data.lacity.org/resource/9yda-i4ya.json"},
            },
            "address_field": "building_address",
            "api_type": "socrata",
        },
        "san francisco, california": {
            "ordinance_name": "San Francisco Benchmarking",
            "endpoints": {
                "2011": {
                    "Benchmarking": "https://data.sfgov.org/resource/96ck-qcfe.json",
                    "Audit Compliance": "SF_Audit_Compliance.csv",
                },
            },
            "address_field": "building_address",
            "api_type": "socrata",
        },
        "berkeley, california": {
            "ordinance_name": "Berkeley BESO",
            "endpoints": {
                "2020": {"Benchmarking": "https://data.cityofberkeley.info/resource/5vy5-rwja.json"},
            },
            "address_field": "building_address",
            "api_type": "socrata",
        },
        "boston, massachusetts": {
            "ordinance_name": "Boston BERDO",
            "endpoints": {
                "2024": {"Benchmarking": "87521565-7f15-4b8d-a225-ac4df9e3f309"},
                "2023": {"Benchmarking": "cb9ad2aa-eec6-4726-a308-945a215056d5"},
                "2022": {"Benchmarking": "cd2c6809-ee14-4321-9d88-e9b45a840a02"},
                "2021": {"Benchmarking": "a7b155de-10ee-48fc-bd89-fc8e31134913"},
            },
            "base_url": "https://data.boston.gov/api/3/action/datastore_search",
            "address_field": "Building Address",
            "api_type": "ckan",
        },
        "cambridge, massachusetts": {
            "ordinance_name": "Cambridge BEUDO",
            "endpoints": {
                "2023": {"Benchmarking": "https://data.cambridgema.gov/resource/72g6-j7aq.json"},
            },
            "address_field": "address",
            "api_type": "socrata",
        },
        "seattle, washington": {
            "ordinance_name": "Seattle Benchmarking",
            "endpoints": {
                "2015": {"Benchmarking": "https://data.seattle.gov/resource/teqw-tu6e.json"},
            },
            "address_field": "address",
            "api_type": "socrata",
        },
        "orlando, florida": {
            "ordinance_name": "Orlando BEWES",
            "endpoints": {
                "2023": {"Benchmarking": "https://data.cityoforlando.net/resource/f63n-kp6t.json"},
            },
            "address_field": "building_address",
            "api_type": "socrata",
        },
        "miami, florida": {
            "ordinance_name": "Miami Benchmarking",
            "endpoints": {
                "2023": {"Benchmarking": "Miami Benchmarking, 2023 Data.csv"},
            },
            "address_field": "Property Address Street*",
            "api_type": "csv",
        },
        "philadelphia, pennsylvania": {
            "ordinance_name": "Philadelphia Benchmarking",
            "endpoints": {
                "2023": {"Benchmarking": "https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/properties_reported_2023/FeatureServer/0/query"},
                "2022": {"Benchmarking": "https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/Properties_Reported_2022/FeatureServer/0/query"},
                "2021": {"Benchmarking": "https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/Properties_Reported_2021/FeatureServer/0/query"},
            },
            "address_field": "street_address",
            "api_type": "arcgis",
        },
    },
}

# Zipcode overrides for cities whose boroughs/neighborhoods have different
# city names but should resolve to the parent city's BPS ordinance.
ZIPCODE_CITY_OVERRIDES: dict[str, str] = {}

_NYC_ZIPCODES = [
    '10001', '10002', '10003', '10004', '10005', '10006', '10007', '10009',
    '10010', '10011', '10012', '10013', '10014', '10016', '10017', '10018',
    '10019', '10020', '10021', '10022', '10023', '10024', '10025', '10026',
    '10027', '10028', '10029', '10030', '10031', '10032', '10033', '10034',
    '10035', '10036', '10037', '10038', '10039', '10040', '10044', '10065',
    '10075', '10128', '10280', '10301', '10302', '10303', '10304', '10305',
    '10306', '10307', '10308', '10309', '10310', '10312', '10314', '10451',
    '10452', '10453', '10454', '10455', '10456', '10457', '10458', '10459',
    '10460', '10461', '10462', '10463', '10464', '10465', '10466', '10467',
    '10468', '10469', '10470', '10471', '10472', '10473', '10474', '10475',
    '11004', '11005', '11101', '11102', '11103', '11104', '11105', '11106',
    '11201', '11203', '11204', '11205', '11206', '11207', '11208', '11209',
    '11210', '11211', '11212', '11213', '11214', '11215', '11216', '11217',
    '11218', '11219', '11220', '11221', '11222', '11223', '11224', '11225',
    '11226', '11228', '11229', '11230', '11231', '11232', '11233', '11234',
    '11235', '11236', '11237', '11238', '11239', '11354', '11355', '11356',
    '11357', '11358', '11359', '11360', '11361', '11362', '11363', '11364',
    '11365', '11366', '11367', '11368', '11369', '11370', '11372', '11373',
    '11374', '11375', '11377', '11378', '11379', '11385', '11411', '11412',
    '11413', '11414', '11415', '11416', '11417', '11418', '11419', '11420',
    '11421', '11422', '11423', '11426', '11427', '11428', '11429', '11432',
    '11433', '11434', '11435', '11436', '11691', '11692', '11693', '11694',
    '11695', '11697',
]

_BOSTON_ZIPCODES = [
    '02021', '02026', '02108', '02109', '02110', '02111', '02113', '02114',
    '02115', '02116', '02118', '02119', '02120', '02121', '02122', '02124',
    '02125', '02126', '02127', '02128', '02129', '02130', '02131', '02132',
    '02134', '02135', '02136', '02151', '02152', '02163', '02186', '02199',
    '02203', '02210', '02215', '02459', '02467',
]

for _zc in _NYC_ZIPCODES:
    ZIPCODE_CITY_OVERRIDES[_zc] = "new york"

for _zc in _BOSTON_ZIPCODES:
    ZIPCODE_CITY_OVERRIDES[_zc] = "boston"

# Field mappings: maps each ordinance's raw API field names to standard names.
FIELD_MAPPINGS: dict[str, dict[str, str]] = {
    "NYC LL84": {
        "site_eui_kbtu_ft": "site_eui_kbtu_sf",
        "electricity_use_grid_purchase_1": "electricity_kwh",
        "natural_gas_use_kbtu": "natural_gas_kbtu",
        "district_steam_use_kbtu": "district_steam_kbtu",
        "district_hot_water_use_kbtu": "district_hot_water_kbtu",
        "fuel_oil_2_use_kbtu": "fuel_oil_kbtu",
        "energy_star_score": "energy_star_score",
        "property_name": "property_name",
        "address_1": "matched_address",
    },
    "Energize Denver": {
        "Site_EUI__kBtu_Sq_Ft_": "site_eui_kbtu_sf",
        "Electricity_Use_Grid_Purchase_a": "electricity_kbtu",
        "Natural_Gas_Use__kBtu_": "natural_gas_kbtu",
        "Energy_Star_Score": "energy_star_score",
        "Property_Name": "property_name",
        "Street": "matched_address",
    },
    "Boston BERDO": {
        "Site EUI (Energy Use Intensity kBtu/ft2)": "site_eui_kbtu_sf",
        "Electricity Usage (kWh)": "electricity_kwh",
        "Natural Gas Usage (kBtu)": "natural_gas_kbtu",
        "District Steam Usage (kBtu)": "district_steam_kbtu",
        "District Hot Water Usage (kBtu)": "district_hot_water_kbtu",
        "Fuel Oil 2 Usage (kBtu)": "fuel_oil_kbtu",
        "Energy Star Score": "energy_star_score",
        "Property Owner Name": "property_name",
        "Building Address": "matched_address",
    },
    "LA EBEWE": {
        "site_eui": "site_eui_kbtu_sf",
        "energy_star_score": "energy_star_score",
        "building_address": "matched_address",
    },
    "Chicago Benchmarking": {
        "site_eui_kbtu_sq_ft": "site_eui_kbtu_sf",
        "electricity_use_kbtu": "electricity_kbtu",
        "energy_star_score": "energy_star_score",
        "property_name": "property_name",
        "address": "matched_address",
    },
    "DC BEPS": {
        "SITEEUI_KBTU_FT": "site_eui_kbtu_sf",
        "ELECTRICITYUSE_GRID_KWH": "electricity_kwh",
        "NATURALGASUSE_THERMS": "natural_gas_therms",
        "DISTRSTEAM_KBTU": "district_steam_kbtu",
        "FUELOILANDDIESELFUELUSEKBTU": "fuel_oil_kbtu",
        "ENERGYSTARSCORE": "energy_star_score",
        "PROPERTYNAME": "property_name",
        "ADDRESSOFRECORD": "matched_address",
        "REPORTEDADDRESS": "matched_address",
    },
    "Seattle Benchmarking": {
        "siteeui_kbtu_sf": "site_eui_kbtu_sf",
        "electricity_kwh": "electricity_kwh",
        "naturalgas_therms": "natural_gas_therms",
        "energystarscore": "energy_star_score",
        "buildingname": "property_name",
        "address": "matched_address",
    },
    "Cambridge BEUDO": {
        "site_eui_kbtu_ft2": "site_eui_kbtu_sf",
        "electricity_use_grid_purchase_kwh": "electricity_kwh",
        "natural_gas_use_therms": "natural_gas_therms",
        "energy_star_score": "energy_star_score",
        "address": "matched_address",
    },
    "San Francisco Benchmarking": {
        "site_eui": "site_eui_kbtu_sf",
        "electricity_use_grid_purchase": "electricity_kbtu",
        "natural_gas_use": "natural_gas_kbtu",
        "energy_star_score": "energy_star_score",
        "building_name": "property_name",
        "building_address": "matched_address",
    },
    "Berkeley BESO": {
        "_2023_site_eui_kbtu_ft2_": "site_eui_kbtu_sf",
        "_2023_electricity_use_grid_purchase_kwh_": "electricity_kwh",
        "_2023_natural_gas_use_kbtu_": "natural_gas_kbtu",
        "_2023_energy_star_score": "energy_star_score",
        "property_building_name": "property_name",
        "building_address": "matched_address",
    },
    "Orlando BEWES": {
        "site_energ": "site_eui_kbtu_sf",
        "energy_sta": "energy_star_score",
        "property_a": "matched_address",
    },
    "Philadelphia Benchmarking": {
        "site_eui_kbtuft2": "site_eui_kbtu_sf",
        "electric_use_kbtu": "electricity_kbtu",
        "natural_gas_use_kbtu": "natural_gas_kbtu",
        "steam_use_kbtu": "district_steam_kbtu",
        "fuel_oil_02_use_kbtu": "fuel_oil_kbtu",
        "energy_star_score": "energy_star_score",
        "property_name": "property_name",
        "street_address": "matched_address",
    },
    "Atlanta CBEEO": {
        "USER_SiteEUI": "site_eui_kbtu_sf",
        "USER_ENERGYSTAR": "energy_star_score",
        "USER_Name_1": "property_name",
        "Match_addr": "matched_address",
    },
    "Austin ECAD": {
        "kwh_sqft": "site_eui_kwh_sf",  # kWh/sqft — needs conversion to kBtu/sqft
        "building_name": "property_name",
        "commercial_property_property_street_address": "matched_address",
    },
    "CA AB802": {
        "EUI String": "site_eui_kbtu_sf",
        "Electricity Use - Grid Purchase (kBtu)": "electricity_kbtu",
        "Natural Gas Use (kBtu)": "natural_gas_kbtu",
        "ENERGY STAR Score Range": "energy_star_score",
        "Building Name": "property_name",
        "Address": "matched_address",
    },
    "CO BPS": {
        "address_line_1_107": "matched_address",
    },
    "Miami Benchmarking": {
        "Site EUI**": "site_eui_kbtu_sf",
        " Electricity Use Grid Purchase and Onsite (KWh)** ": "electricity_kwh",
        " Natural Gas Use (therms)** ": "natural_gas_therms",
        "Energy Star Score**": "energy_star_score",
        "Property Address Street*": "matched_address",
    },
    "Montgomery County Benchmarking": {
        "address": "matched_address",
    },
}
