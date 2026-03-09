#!/usr/bin/env python3
"""
CBECS 2018 Microdata -> XGBoost Model Feature Mapping Analysis
==============================================================
Analyzes the CBECS 2018 public use microdata and creates detailed mappings
to the XGBoost energy estimation model's input features.

ACTUAL model valid categories (from BuildingStock_Unique_Variables_v2.xlsx):
  in.building_type:           LargeOffice, MediumOffice, SmallOffice, Outpatient, Hospital,
                              RetailStripmall, RetailStandalone, SmallHotel, LargeHotel,
                              Warehouse, QuickServiceRestaurant, FullServiceRestaurant,
                              SecondarySchool, PrimarySchool, Multi-Family
  climate_zone_ashrae_2006:   1A,2A,2B,3A,3B,3C,4A,4B,4C,5A,5B,6A,6B,7,8
  in.heating_fuel:            Electricity, NaturalGas, Propane, FuelOil, DistrictHeating
  in.water_heater_fuel:       Electricity, NaturalGas, Propane, FuelOil, DistrictHeating
  num_of_stories:             1-3, 4-7, 8+
  floor_area:                 <25,000, 25,000-200,000, >200,000
  year_built:                 <1946, 1946-1959, 1960-1979, 1980-1999, 2000-2009, >2010
  in.hvac_category:           Unitary/Split/DX, Central Plant
  cluster_name:               97 regional cluster names
"""

import pandas as pd
import numpy as np
import os
import warnings
warnings.filterwarnings('ignore')

pd.set_option('display.max_rows', 200)
pd.set_option('display.max_columns', 50)
pd.set_option('display.width', 200)
pd.set_option('display.max_colwidth', 60)

# ==============================================================================
# LOAD DATA
# ==============================================================================
BASE = os.path.dirname(os.path.abspath(__file__))
CBECS_CSV = os.path.join(BASE, 'cbecs2018_final_public.csv')
CODEBOOK = os.path.join(BASE, '2018microdata_codebook.xlsx')

print("=" * 100)
print("CBECS 2018 MICRODATA -> XGBOOST MODEL FEATURE MAPPING ANALYSIS")
print("=" * 100)

# Load CBECS data
df = pd.read_csv(CBECS_CSV)
print(f"\nLoaded CBECS data: {len(df)} records, {len(df.columns)} columns")

# Load codebook
try:
    codebook = pd.read_excel(CODEBOOK, sheet_name=None)
    print(f"Codebook sheets: {list(codebook.keys())}")
    for sheet_name, sheet_df in codebook.items():
        print(f"\n--- Codebook Sheet: '{sheet_name}' ---")
        print(f"  Columns: {sheet_df.columns.tolist()}")
        print(sheet_df.head(20).to_string())
except Exception as e:
    print(f"Could not read codebook: {e}")

# Load actual model valid categories
unique_values_path = os.path.join(BASE, '..', '..', 'ComStock', 'BuildingStock_Unique_Variables_v2.xlsx')
model_valid = {}
if os.path.exists(unique_values_path):
    uv = pd.read_excel(unique_values_path, dtype=str)
    model_valid = {col: uv[col].dropna().tolist() for col in uv.columns}
    print(f"\nLoaded model valid categories from: {unique_values_path}")
    for col, vals in model_valid.items():
        print(f"  {col}: {vals}")

# ==============================================================================
# EXAMINE KEY CBECS VARIABLES
# ==============================================================================
print("\n\n" + "=" * 100)
print("SECTION 1: KEY CBECS VARIABLE VALUE DISTRIBUTIONS")
print("=" * 100)

key_vars = ['PBA', 'PBAPLUS', 'PUBCLIM', 'CENDIV', 'REGION', 'SQFT', 'NFLOOR',
            'YRCONC', 'MAINHT', 'MAINCL', 'PKGHT', 'FURNAC', 'BOILER', 'HTPMPH',
            'CHILLR', 'VAV', 'SLFCON', 'RCAC', 'PKGCL', 'HTPMPC', 'ACWNWL',
            'HT1', 'HT2', 'COOL',
            'ELHT1', 'NGHT1', 'FKHT1', 'PRHT1', 'STHT1', 'HWHT1',
            'ELWATR', 'NGWATR', 'FKWATR', 'PRWATR', 'STWATR', 'HWWATR',
            'HEATP', 'COOLP',
            'ELBTU', 'NGBTU', 'FKBTU', 'DHBTU', 'DHUSED',
            'HDD65', 'CDD65']

for var in key_vars:
    if var in df.columns:
        print(f"\n{var}:")
        print(f"  dtype: {df[var].dtype}, non-null: {df[var].notna().sum()}, unique: {df[var].nunique()}")
        if df[var].dtype in ['int64', 'float64'] and df[var].nunique() > 20:
            print(f"  min={df[var].min()}, max={df[var].max()}, mean={df[var].mean():.1f}, median={df[var].median():.1f}")
        else:
            vc = df[var].value_counts(dropna=False).sort_index()
            print(vc.to_string())
    else:
        print(f"\n{var}: NOT FOUND in CBECS data")


# ==============================================================================
# MAPPING 1: BUILDING TYPE (PBA/PBAPLUS -> in.building_type)
# ==============================================================================
print("\n\n" + "=" * 100)
print("MAPPING 1: BUILDING TYPE")
print("  CBECS variable: PBA (principal building activity) + PBAPLUS (detailed) + SQFT")
print("  Target: in.building_type")
print("  Model valid values: LargeOffice, MediumOffice, SmallOffice, Outpatient, Hospital,")
print("    RetailStripmall, RetailStandalone, SmallHotel, LargeHotel, Warehouse,")
print("    QuickServiceRestaurant, FullServiceRestaurant, SecondarySchool, PrimarySchool,")
print("    Multi-Family")
print("=" * 100)

# PBA codes from CBECS 2018 codebook:
# 1=Vacant, 2=Office, 4=Laboratory, 5=Nonrefrigerated warehouse,
# 6=Food sales, 7=Public order and safety, 8=Outpatient health care,
# 11=Refrigerated warehouse, 12=Religious worship, 13=Public assembly,
# 14=Education, 15=Food service, 16=Inpatient health care,
# 17=Nursing, 18=Lodging, 23=Strip shopping center,
# 24=Enclosed mall, 25=Retail other than mall, 26=Service, 91=Other

# PBAPLUS further distinguishes subtypes. Key PBAPLUS codes:
# 2=Administrative/professional office, 3=Bank/financial, 4=Government office,
# 5=Medical office (non-diagnostic), 6=Mixed-use office, 7=Other office
# 14=Elementary/middle school, 15=High school, 16=College/university
# 22=Fast food, 23=Restaurant/cafeteria
# 38=Motel or inn, 39=Hotel, 40=Dormitory
# etc.

print("\n--- PBAPLUS distribution (detailed building activity) ---")
print(df['PBAPLUS'].value_counts().sort_index().to_string())

def map_building_type(row):
    """Map CBECS PBA/PBAPLUS/SQFT to ComStock building types."""
    pba = row['PBA']
    pbaplus = row['PBAPLUS']
    sqft = row['SQFT']

    # Office: split by size
    if pba == 2:
        if sqft > 150000:
            return 'LargeOffice'
        elif sqft > 25000:
            return 'MediumOffice'
        else:
            return 'SmallOffice'

    # Education: split into primary and secondary school
    if pba == 14:
        if pbaplus == 14:  # Elementary/middle school
            return 'PrimarySchool'
        elif pbaplus == 15:  # High school
            return 'SecondarySchool'
        elif pbaplus == 16:  # College/university
            return 'SecondarySchool'  # best approximation
        else:
            # Use size as heuristic
            if sqft > 100000:
                return 'SecondarySchool'
            else:
                return 'PrimarySchool'

    # Food service: split into quick-service and full-service
    if pba == 15:
        if pbaplus == 22:  # Fast food
            return 'QuickServiceRestaurant'
        elif pbaplus == 23:  # Restaurant/cafeteria
            return 'FullServiceRestaurant'
        else:
            # Use size as heuristic: fast food tends to be smaller
            if sqft < 5000:
                return 'QuickServiceRestaurant'
            else:
                return 'FullServiceRestaurant'

    # Healthcare
    if pba == 8:   # Outpatient
        return 'Outpatient'
    if pba == 16:  # Inpatient
        return 'Hospital'
    if pba == 17:  # Nursing - best approximation is Outpatient or Hospital
        return 'Outpatient'  # Nursing homes are closer to outpatient in EUI profile

    # Lodging: split by size
    if pba == 18:
        if pbaplus == 38:  # Motel or inn
            return 'SmallHotel'
        elif pbaplus == 39:  # Hotel
            return 'LargeHotel'
        else:
            if sqft > 75000:
                return 'LargeHotel'
            else:
                return 'SmallHotel'

    # Mercantile/Retail
    if pba == 23:  # Strip shopping center
        return 'RetailStripmall'
    if pba == 24:  # Enclosed mall
        return 'RetailStandalone'  # closest match
    if pba == 25:  # Retail other than mall
        return 'RetailStandalone'
    if pba == 6:   # Food sales (grocery)
        return 'RetailStandalone'  # grocery stores are standalone retail

    # Warehouse
    if pba == 5:   # Nonrefrigerated warehouse
        return 'Warehouse'
    if pba == 11:  # Refrigerated warehouse
        return 'Warehouse'

    # Unmappable types
    return np.nan

df['in.building_type'] = df.apply(map_building_type, axis=1)

# Show the mapping results
print("\n--- PBA x PBAPLUS -> Building Type Mapping Detail ---")
bt_detail = df.groupby(['PBA', 'PBAPLUS', 'in.building_type']).size().reset_index(name='count')
print(bt_detail.to_string(index=False))

print(f"\n--- Records by Mapped Building Type ---")
bt_counts = df['in.building_type'].value_counts(dropna=False)
print(bt_counts.to_string())
print(f"\nTotal mapped:   {df['in.building_type'].notna().sum()}")
print(f"Total unmapped: {df['in.building_type'].isna().sum()}")

# Show unmapped PBA codes
unmapped_mask = df['in.building_type'].isna()
print(f"\n--- PBA codes of UNMAPPED buildings ---")
unmapped_pba = df.loc[unmapped_mask, 'PBA'].value_counts().sort_index()
pba_names = {1: 'Vacant', 4: 'Laboratory', 7: 'Public order and safety',
             12: 'Religious worship', 13: 'Public assembly', 26: 'Service', 91: 'Other'}
for pba_code, count in unmapped_pba.items():
    print(f"  PBA={pba_code} ({pba_names.get(pba_code, '?')}): {count}")

print("\n*** NOTE: CBECS is a COMMERCIAL building survey. 'Multi-Family' buildings are NOT")
print("    represented. Multi-Family validation requires RECS.")


# ==============================================================================
# MAPPING 2: FLOOR AREA (SQFT -> floor_area bins)
# ==============================================================================
print("\n\n" + "=" * 100)
print("MAPPING 2: FLOOR AREA")
print("  CBECS variable: SQFT (square footage)")
print("  Target: floor_area (binned)")
print("  Model bins: <25,000 | 25,000-200,000 | >200,000")
print("=" * 100)

def bin_floor_area(area):
    if pd.isna(area):
        return np.nan
    if area < 25000:
        return '<25,000'
    elif area <= 200000:
        return '25,000-200,000'
    else:
        return '>200,000'

df['floor_area'] = df['SQFT'].apply(bin_floor_area)

print(f"\nSQFT statistics:")
print(f"  min={df['SQFT'].min():,.0f}, max={df['SQFT'].max():,.0f}")
print(f"  mean={df['SQFT'].mean():,.0f}, median={df['SQFT'].median():,.0f}")
print(f"\n--- Floor Area Bin Distribution ---")
fa_counts = df['floor_area'].value_counts(dropna=False)
print(fa_counts.to_string())
print(f"\nTotal mapped: {df['floor_area'].notna().sum()}")
print(f"Total unmapped: {df['floor_area'].isna().sum()}")


# ==============================================================================
# MAPPING 3: CLIMATE ZONE (PUBCLIM + CENDIV + HDD/CDD -> ASHRAE climate zone)
# ==============================================================================
print("\n\n" + "=" * 100)
print("MAPPING 3: CLIMATE ZONE")
print("  CBECS variables: PUBCLIM + CENDIV + HDD65/CDD65")
print("  Target: climate_zone_ashrae_2006")
print("  Model valid: 1A,2A,2B,3A,3B,3C,4A,4B,4C,5A,5B,6A,6B,7,8")
print("=" * 100)

# PUBCLIM (from codebook: "Third-party data: ASHRAE climate zone"):
# 1 = Cold or very cold  (ASHRAE 5-8)
# 2 = Cool               (ASHRAE ~4-5)
# 3 = Mixed mild         (ASHRAE ~3-4)
# 4 = Warm               (ASHRAE ~2-3)
# 5 = Hot or very hot    (ASHRAE ~1-2)
# 7 = Withheld for confidentiality

print("\n--- Cross-tabulation: PUBCLIM x CENDIV ---")
cross_tab = pd.crosstab(df['PUBCLIM'], df['CENDIV'], margins=True)
print(cross_tab.to_string())

print("\n\nPUBCLIM definitions (CBECS 2018 codebook):")
print("  1 = Cold or very cold  (ASHRAE 5-8)")
print("  2 = Cool               (ASHRAE ~4-5)")
print("  3 = Mixed mild         (ASHRAE ~3-4)")
print("  4 = Warm               (ASHRAE ~2-3)")
print("  5 = Hot or very hot    (ASHRAE ~1-2)")
print("  7 = Withheld for confidentiality (852 records)")

print("\nCENDIV definitions:")
print("  1 = New England       (CT,ME,MA,NH,RI,VT)")
print("  2 = Middle Atlantic   (NJ,NY,PA)")
print("  3 = East N. Central   (IL,IN,MI,OH,WI)")
print("  4 = West N. Central   (IA,KS,MN,MO,NE,ND,SD)")
print("  5 = South Atlantic    (DE,DC,FL,GA,MD,NC,SC,VA,WV)")
print("  6 = East S. Central   (AL,KY,MS,TN)")
print("  7 = West S. Central   (AR,LA,OK,TX)")
print("  8 = Mountain          (AZ,CO,ID,MT,NM,NV,UT,WY)")
print("  9 = Pacific           (AK,CA,HI,OR,WA)")

# HDD/CDD by PUBCLIM x CENDIV
print("\n\n--- HDD65 and CDD65 by PUBCLIM x CENDIV ---")
hdd_cdd = df.groupby(['PUBCLIM', 'CENDIV']).agg(
    count=('SQFT', 'size'),
    HDD65_mean=('HDD65', 'mean'),
    HDD65_min=('HDD65', 'min'),
    HDD65_max=('HDD65', 'max'),
    CDD65_mean=('CDD65', 'mean'),
    CDD65_min=('CDD65', 'min'),
    CDD65_max=('CDD65', 'max'),
).reset_index()
print(hdd_cdd.to_string(index=False))

# Mapping logic using PUBCLIM + CENDIV
pubclim_cendiv_to_ashrae = {
    # PUBCLIM 1 = Cold or very cold (HDD typically >5400)
    (1, 1): '6A',   # New England cold: VT,NH,ME = 6A (HDD~7678)
    (1, 2): '6A',   # Mid-Atlantic cold: upstate NY = 6A (HDD~7532)
    (1, 3): '6A',   # East N Central: northern WI, MI = 6A (HDD~7773)
    (1, 4): '6A',   # West N Central: MN, Dakotas = 6A (HDD~8534)
    (1, 8): '6B',   # Mountain cold: MT, WY = 6B (HDD~7208, dry)
    (1, 9): '6B',   # Pacific cold: AK = 6B/7 (HDD~7607, dry)

    # PUBCLIM 2 = Cool (HDD ~4500-7000)
    (2, 1): '5A',   # New England: Boston area = 5A (HDD~6014)
    (2, 2): '5A',   # Mid-Atlantic: upstate NY, PA = 5A (HDD~6558)
    (2, 3): '5A',   # East N Central: Chicago, Detroit = 5A (HDD~6435)
    (2, 4): '5A',   # West N Central: IA, NE = 5A (HDD~7194)
    (2, 8): '5B',   # Mountain: Denver, SLC = 5B (HDD~5707, dry)
    (2, 9): '4C',   # Pacific: Portland, Seattle = 4C marine (HDD~6056)

    # PUBCLIM 3 = Mixed mild (HDD ~3500-5500)
    (3, 1): '5A',   # New England: southern CT = 5A (HDD~5613)
    (3, 2): '4A',   # Mid-Atlantic: NYC, Philly = 4A (HDD~5081)
    (3, 3): '4A',   # East N Central: southern OH, IN = 4A (HDD~5217)
    (3, 4): '4A',   # West N Central: MO, KS = 4A (HDD~5190)
    (3, 5): '4A',   # South Atlantic: DC, MD, VA = 4A (HDD~4367)
    (3, 6): '4A',   # East S Central: TN, KY = 4A (HDD~4311)
    (3, 7): '3A',   # West S Central: AR, N TX = 3A (HDD~4173)
    (3, 8): '4B',   # Mountain: NM highlands = 4B (HDD~4489, dry)
    (3, 9): '3C',   # Pacific: SF, coastal CA = 3C marine (HDD~3978)

    # PUBCLIM 4 = Warm (HDD ~1500-3500)
    (4, 5): '3A',   # South Atlantic: NC, SC, GA = 3A (HDD~2959)
    (4, 6): '3A',   # East S Central: AL, MS = 3A (HDD~3289)
    (4, 7): '3A',   # West S Central: central TX = 3A (HDD~3453)
    (4, 8): '3B',   # Mountain: Phoenix, Tucson = 3B (HDD~3418, dry)
    (4, 9): '3B',   # Pacific: inland CA, LA, San Diego = 3B (HDD~1427, dry)

    # PUBCLIM 5 = Hot or very hot (HDD <2000)
    (5, 5): '2A',   # South Atlantic: FL = 2A (HDD~1563)
    (5, 6): '2A',   # East S Central: S AL = 2A (HDD~2286)
    (5, 7): '2A',   # West S Central: Houston, S TX, LA = 2A (HDD~1588)
    (5, 8): '2B',   # Mountain: Phoenix metro = 2B (HDD~1606, dry)
    (5, 9): '1A',   # Pacific: Hawaii = 1A (HDD~786)
}

# For PUBCLIM=7 (withheld) and any unmatched combos, infer from HDD/CDD
def infer_ashrae_from_hdd_cdd(row):
    """Infer ASHRAE zone from HDD65/CDD65 and census division."""
    hdd = row.get('HDD65', np.nan)
    cendiv = row.get('CENDIV', -1)

    if pd.isna(hdd):
        return np.nan

    # Determine moisture regime
    is_dry = cendiv == 8
    is_marine = cendiv == 9

    if hdd >= 9000:
        return '7'
    elif hdd >= 7200:
        return '6B' if is_dry else '6A'
    elif hdd >= 5400:
        if is_dry:
            return '5B'
        elif is_marine:
            return '4C'
        else:
            return '5A'
    elif hdd >= 3600:
        if is_dry:
            return '4B'
        elif is_marine:
            return '3C'
        else:
            return '4A'
    elif hdd >= 1800:
        if is_dry:
            return '3B'
        else:
            return '3A'
    elif hdd >= 900:
        return '2B' if is_dry else '2A'
    else:
        return '1A'

def assign_ashrae_zone(row):
    result = pubclim_cendiv_to_ashrae.get((row['PUBCLIM'], row['CENDIV']), None)
    if result is not None:
        return result
    return infer_ashrae_from_hdd_cdd(row)

df['climate_zone_ashrae_2006'] = df.apply(assign_ashrae_zone, axis=1)

print("\n\n--- Proposed ASHRAE Zone Mapping ---")
print(f"{'PUBCLIM':<10} {'CENDIV':<10} {'ASHRAE Zone':<15} {'Count':<10} {'Avg HDD65':<12} {'Avg CDD65':<12}")
print("-" * 70)
for (pc, cd), ashrae in sorted(pubclim_cendiv_to_ashrae.items()):
    mask = (df['PUBCLIM'] == pc) & (df['CENDIV'] == cd)
    count = mask.sum()
    if count > 0:
        avg_hdd = df.loc[mask, 'HDD65'].mean()
        avg_cdd = df.loc[mask, 'CDD65'].mean()
        print(f"{pc:<10} {cd:<10} {ashrae:<15} {count:<10} {avg_hdd:<12.0f} {avg_cdd:<12.0f}")

# Show PUBCLIM=7 inferred zones
print(f"\n--- PUBCLIM=7 (withheld) -> ASHRAE Zone (inferred from HDD/CDD) ---")
p7_mask = df['PUBCLIM'] == 7
p7_zones = df.loc[p7_mask, 'climate_zone_ashrae_2006'].value_counts().sort_index()
print(p7_zones.to_string())

print(f"\n--- Overall Climate Zone Distribution ---")
cz_counts = df['climate_zone_ashrae_2006'].value_counts(dropna=False).sort_index()
print(cz_counts.to_string())
print(f"\nTotal mapped: {df['climate_zone_ashrae_2006'].notna().sum()}")
print(f"Total unmapped: {df['climate_zone_ashrae_2006'].isna().sum()}")

# Validation: HDD/CDD by assigned zone
print("\n--- Validation: HDD65/CDD65 by assigned ASHRAE zone ---")
zone_climate = df.groupby('climate_zone_ashrae_2006').agg(
    count=('SQFT', 'size'),
    HDD65_mean=('HDD65', 'mean'),
    HDD65_std=('HDD65', 'std'),
    CDD65_mean=('CDD65', 'mean'),
    CDD65_std=('CDD65', 'std'),
).reset_index()
print(zone_climate.to_string(index=False))


# ==============================================================================
# MAPPING 4: HEATING FUEL (-> in.heating_fuel)
# ==============================================================================
print("\n\n" + "=" * 100)
print("MAPPING 4: HEATING FUEL")
print("  CBECS variables: ELHT1, NGHT1, FKHT1, PRHT1, STHT1, HWHT1")
print("  Target: in.heating_fuel")
print("  Model valid: Electricity, NaturalGas, Propane, FuelOil, DistrictHeating")
print("=" * 100)

print("\n--- Primary heating fuel flags ---")
for fuel_var in ['ELHT1', 'NGHT1', 'FKHT1', 'PRHT1', 'STHT1', 'HWHT1']:
    if fuel_var in df.columns:
        yes_count = (df[fuel_var] == 1).sum()
        print(f"  {fuel_var}: {yes_count} buildings use this fuel for primary heating")

print(f"\n  HT1 (space heating used): {(df['HT1'] == 1).sum()} yes, {(df['HT1'] == 2).sum()} no")

print("\n--- MAINHT distribution ---")
print(df['MAINHT'].value_counts(dropna=False).sort_index().to_string())

def derive_heating_fuel(row):
    if row.get('HT1', 2) != 1:
        return np.nan

    # District steam/hot water
    if row.get('STHT1', 2) == 1 or row.get('HWHT1', 2) == 1:
        return 'DistrictHeating'
    if row.get('NGHT1', 2) == 1:
        return 'NaturalGas'
    if row.get('ELHT1', 2) == 1:
        return 'Electricity'
    if row.get('FKHT1', 2) == 1:
        return 'FuelOil'
    if row.get('PRHT1', 2) == 1:
        return 'Propane'

    return 'Unknown'

df['in.heating_fuel'] = df.apply(derive_heating_fuel, axis=1)

print("\n--- Heating Fuel Distribution ---")
hf_counts = df['in.heating_fuel'].value_counts(dropna=False)
print(hf_counts.to_string())
print(f"\nTotal mapped (heated): {df['in.heating_fuel'].notna().sum()}")
print(f"Not heated (no HT1): {df['in.heating_fuel'].isna().sum()}")
print(f"Unknown fuel: {(df['in.heating_fuel'] == 'Unknown').sum()}")

# Cross-check
print("\n--- Heating Fuel x MAINHT ---")
ct_fuel_mainht = pd.crosstab(df['in.heating_fuel'], df['MAINHT'], margins=True, dropna=False)
print(ct_fuel_mainht.to_string())


# ==============================================================================
# MAPPING 5: WATER HEATER FUEL (-> in.water_heater_fuel)
# ==============================================================================
print("\n\n" + "=" * 100)
print("MAPPING 5: WATER HEATER FUEL")
print("  CBECS variables: ELWATR, NGWATR, FKWATR, PRWATR, STWATR, HWWATR")
print("  Target: in.water_heater_fuel")
print("  Model valid: Electricity, NaturalGas, Propane, FuelOil, DistrictHeating")
print("=" * 100)

print("\n--- Water heating fuel flags ---")
for fuel_var in ['ELWATR', 'NGWATR', 'FKWATR', 'PRWATR', 'STWATR', 'HWWATR']:
    if fuel_var in df.columns:
        yes_count = (df[fuel_var] == 1).sum()
        print(f"  {fuel_var}: {yes_count} buildings use this fuel for water heating")

print(f"\n  WATR (water heating used): {(df['WATR'] == 1).sum()} yes, {(df['WATR'] == 2).sum()} no")

def derive_water_heater_fuel(row):
    if row.get('WATR', 2) != 1:
        return np.nan

    if row.get('STWATR', 2) == 1 or row.get('HWWATR', 2) == 1:
        return 'DistrictHeating'
    if row.get('NGWATR', 2) == 1:
        return 'NaturalGas'
    if row.get('ELWATR', 2) == 1:
        return 'Electricity'
    if row.get('FKWATR', 2) == 1:
        return 'FuelOil'
    if row.get('PRWATR', 2) == 1:
        return 'Propane'

    return 'Unknown'

df['in.water_heater_fuel'] = df.apply(derive_water_heater_fuel, axis=1)

print("\n--- Water Heater Fuel Distribution ---")
whf_counts = df['in.water_heater_fuel'].value_counts(dropna=False)
print(whf_counts.to_string())
print(f"\nTotal mapped: {df['in.water_heater_fuel'].notna().sum()}")
print(f"No water heating: {df['in.water_heater_fuel'].isna().sum()}")


# ==============================================================================
# MAPPING 6: NUMBER OF STORIES (NFLOOR -> num_of_stories bins)
# ==============================================================================
print("\n\n" + "=" * 100)
print("MAPPING 6: NUMBER OF STORIES")
print("  CBECS variable: NFLOOR")
print("  Target: num_of_stories")
print("  Model bins: 1-3, 4-7, 8+")
print("  NOTE: CBECS uses 994=10-14, 995=15+")
print("=" * 100)

print("\n--- NFLOOR distribution ---")
print(df['NFLOOR'].value_counts(dropna=False).sort_index().to_string())

def bin_stories(n):
    if pd.isna(n):
        return np.nan
    if n <= 3:
        return '1-3'
    elif n <= 7:
        return '4-7'
    else:
        return '8+'  # Model only has 8+ (not 8-14 and 15+ separately)

df['num_of_stories'] = df['NFLOOR'].apply(bin_stories)

print(f"\n--- Story Bin Distribution ---")
st_counts = df['num_of_stories'].value_counts(dropna=False)
print(st_counts.to_string())
print(f"\nTotal mapped: {df['num_of_stories'].notna().sum()}")


# ==============================================================================
# MAPPING 7: YEAR BUILT (YRCONC -> year_built bins)
# ==============================================================================
print("\n\n" + "=" * 100)
print("MAPPING 7: YEAR BUILT")
print("  CBECS variable: YRCONC")
print("  Target: year_built")
print("  Model bins: <1946, 1946-1959, 1960-1979, 1980-1999, 2000-2009, >2010")
print("=" * 100)

print("\n--- YRCONC distribution ---")
print(df['YRCONC'].value_counts(dropna=False).sort_index().to_string())

# YRCONC in this dataset only has values 2-9:
# 2=1920-1945, 3=1946-1959, 4=1960-1969, 5=1970-1979,
# 6=1980-1989, 7=1990-1999, 8=2000-2012, 9=2013-2018
# (Note: 8 appears to combine 2000-2012 in this dataset based on counts)

yrconc_to_yearbin = {
    1: '<1946',       # Before 1920
    2: '<1946',       # 1920-1945
    3: '1946-1959',   # 1946-1959
    4: '1960-1979',   # 1960-1969
    5: '1960-1979',   # 1970-1979
    6: '1980-1999',   # 1980-1989
    7: '1980-1999',   # 1990-1999
    8: '2000-2009',   # 2000-2012 (straddling boundary)
    9: '>2010',       # 2013-2018
    10: '>2010',      # if present
    11: '>2010',      # if present
}

df['year_built'] = df['YRCONC'].map(yrconc_to_yearbin)

print("\n--- YRCONC -> Year Bin Mapping ---")
yrconc_desc = {
    1: 'Before 1920', 2: '1920-1945', 3: '1946-1959',
    4: '1960-1969', 5: '1970-1979', 6: '1980-1989',
    7: '1990-1999', 8: '2000-2012', 9: '2013-2018',
    10: '2008-2012', 11: '2013-2018'
}
print(f"{'YRCONC':<10} {'Description':<20} {'Model Year Bin':<15} {'Count':<10}")
print("-" * 55)
for code in sorted(df['YRCONC'].unique()):
    count = (df['YRCONC'] == code).sum()
    desc = yrconc_desc.get(code, '?')
    ybin = yrconc_to_yearbin.get(code, '?')
    print(f"{code:<10} {desc:<20} {ybin:<15} {count}")

print(f"\n--- Year Built Bin Distribution ---")
yb_counts = df['year_built'].value_counts(dropna=False)
print(yb_counts.to_string())


# ==============================================================================
# MAPPING 8: HVAC CATEGORY (-> in.hvac_category)
# ==============================================================================
print("\n\n" + "=" * 100)
print("MAPPING 8: HVAC CATEGORY")
print("  CBECS variables: BOILER, CHILLR, VAV, PKGHT, PKGCL, FURNAC, RCAC, HTPMPH, etc.")
print("  Target: in.hvac_category")
print("  Model valid values: 'Unitary/Split/DX' and 'Central Plant'")
print("  (Only 2 categories, not 4 as initially assumed!)")
print("=" * 100)

# With only 2 categories, the logic is much simpler:
# Central Plant = has boiler and/or chiller (centralized equipment)
# Unitary/Split/DX = everything else (packaged, split systems, PTACs, window units)

print("\n--- Key Equipment Variables ---")
for var in ['BOILER', 'CHILLR', 'VAV', 'PKGHT', 'PKGCL', 'FURNAC', 'RCAC', 'HTPMPH', 'SLFCON', 'ACWNWL', 'REHEAT']:
    if var in df.columns:
        yes = (df[var] == 1).sum()
        no = (df[var] == 2).sum()
        na = df[var].isna().sum()
        print(f"  {var:<10} Yes={yes:>5}  No={no:>5}  NA={na:>5}")

def classify_hvac(row):
    """
    Central Plant: building has a boiler AND/OR chiller (central water-based systems)
    Also includes buildings with VAV (which implies central AHU/plant),
    or district heating/cooling.
    Unitary/Split/DX: packaged rooftop units, split systems, PTACs, window units, etc.
    """
    boiler = row.get('BOILER', 2) == 1
    chiller = row.get('CHILLR', 2) == 1
    vav = row.get('VAV', 2) == 1

    # District heating implies central plant
    stht1 = row.get('STHT1', 2) == 1
    hwht1 = row.get('HWHT1', 2) == 1
    district = stht1 or hwht1

    if boiler or chiller or vav or district:
        return 'Central Plant'
    else:
        return 'Unitary/Split/DX'

df['in.hvac_category'] = df.apply(classify_hvac, axis=1)

print("\n--- HVAC Category Distribution ---")
hvac_counts = df['in.hvac_category'].value_counts(dropna=False)
print(hvac_counts.to_string())

# Cross-tab with building type
print("\n--- HVAC Category x Building Type ---")
ct_hvac_bt = pd.crosstab(df['in.hvac_category'], df['in.building_type'], margins=True, dropna=False)
print(ct_hvac_bt.to_string())

# Equipment prevalence within each category
print("\n--- Equipment prevalence within each HVAC category ---")
for cat in ['Central Plant', 'Unitary/Split/DX']:
    mask = df['in.hvac_category'] == cat
    n = mask.sum()
    print(f"\n  {cat} (n={n}):")
    for var in ['VAV', 'BOILER', 'CHILLR', 'PKGHT', 'PKGCL', 'FURNAC', 'RCAC', 'HTPMPH', 'HTPMPC', 'SLFCON', 'ACWNWL', 'REHEAT']:
        if var in df.columns:
            yes_pct = (df.loc[mask, var] == 1).mean() * 100
            print(f"    {var}=1: {yes_pct:.1f}%")


# ==============================================================================
# CALCULATE TARGET EUI VALUES
# ==============================================================================
print("\n\n" + "=" * 100)
print("TARGET EUI CALCULATIONS")
print("  electricity_eui = ELBTU / SQFT (kBtu/sqft)")
print("  natural_gas_eui = NGBTU / SQFT")
print("  district_heating_eui = DHBTU / SQFT")
print("  other_fuel_eui = FKBTU / SQFT")
print("  total_site_eui = sum of all")
print("=" * 100)

df['electricity_eui'] = np.where(df['SQFT'] > 0, df['ELBTU'].fillna(0) / df['SQFT'], np.nan)
df['natural_gas_eui'] = np.where(df['SQFT'] > 0, df['NGBTU'].fillna(0) / df['SQFT'], np.nan)

if 'DHBTU' in df.columns:
    df['district_heating_eui'] = np.where(df['SQFT'] > 0, df['DHBTU'].fillna(0) / df['SQFT'], 0)
else:
    df['district_heating_eui'] = 0

if 'FKBTU' in df.columns:
    df['other_fuel_eui'] = np.where(df['SQFT'] > 0, df['FKBTU'].fillna(0) / df['SQFT'], 0)
else:
    df['other_fuel_eui'] = 0

df['total_site_eui'] = (df['electricity_eui'].fillna(0) +
                         df['natural_gas_eui'].fillna(0) +
                         df['district_heating_eui'].fillna(0) +
                         df['other_fuel_eui'].fillna(0))

print("\n--- EUI Statistics (all buildings) ---")
eui_cols = ['electricity_eui', 'natural_gas_eui', 'district_heating_eui', 'other_fuel_eui', 'total_site_eui']
eui_stats = df[eui_cols].describe(percentiles=[.25, .5, .75, .90, .95])
print(eui_stats.to_string())

# EUI by building type
print("\n\n--- EUI Distribution by Building Type (kBtu/sqft) ---")
for bt in sorted(df['in.building_type'].dropna().unique()):
    mask = df['in.building_type'] == bt
    n = mask.sum()
    print(f"\n  {bt} (n={n}):")
    for eui_col in eui_cols:
        med = df.loc[mask, eui_col].median()
        mean = df.loc[mask, eui_col].mean()
        q25 = df.loc[mask, eui_col].quantile(0.25)
        q75 = df.loc[mask, eui_col].quantile(0.75)
        print(f"    {eui_col:<30} median={med:8.1f}  mean={mean:8.1f}  Q25={q25:8.1f}  Q75={q75:8.1f}")


# ==============================================================================
# CLUSTER NAME
# ==============================================================================
print("\n\n" + "=" * 100)
print("CLUSTER NAME")
print("=" * 100)
print("\nThe XGBoost model requires 'cluster_name' (97 unique regional clusters).")
print("CBECS does not provide zipcode/FIPS for anonymity. CENDIV is the finest geography.")
print("\nFor validation, options:")
print("  1. Test predictions with each of the most common clusters per CENDIV")
print("  2. Average predictions across all plausible clusters")
print("  3. Use a 'representative' cluster for each census division")


# ==============================================================================
# FINAL SUMMARY: COMPLETE CASES ANALYSIS
# ==============================================================================
print("\n\n" + "=" * 100)
print("FINAL SUMMARY: COMPLETE CASES ANALYSIS")
print("=" * 100)

required_features = ['in.building_type', 'floor_area', 'climate_zone_ashrae_2006',
                     'in.heating_fuel', 'in.water_heater_fuel', 'num_of_stories',
                     'year_built', 'in.hvac_category']

print("\n--- Feature completeness ---")
for feat in required_features:
    if feat in ['in.heating_fuel', 'in.water_heater_fuel']:
        valid = ((df[feat].notna()) & (df[feat] != 'Unknown')).sum()
    else:
        valid = df[feat].notna().sum()
    total = len(df)
    pct = valid / total * 100
    print(f"  {feat:<30} {valid:>5} / {total} ({pct:.1f}%)")

# Check against model valid values
print("\n--- Validation against model valid categories ---")
for feat in required_features:
    if feat in model_valid:
        valid_vals = model_valid[feat]
        in_model = df[feat].isin(valid_vals).sum()
        not_in = df[feat].notna() & ~df[feat].isin(valid_vals)
        print(f"  {feat:<30} in model={in_model:>5}  NOT in model={not_in.sum():>5}")
        if not_in.sum() > 0:
            bad_vals = df.loc[not_in, feat].value_counts()
            for v, c in bad_vals.items():
                print(f"    '{v}': {c} records (not a valid model category)")

# Complete cases
complete_mask = (
    df['in.building_type'].notna() &
    df['in.building_type'].isin(model_valid.get('in.building_type', [])) &
    df['floor_area'].notna() &
    df['climate_zone_ashrae_2006'].notna() &
    df['climate_zone_ashrae_2006'].isin(model_valid.get('climate_zone_ashrae_2006', [])) &
    df['in.heating_fuel'].notna() &
    df['in.heating_fuel'].isin(model_valid.get('in.heating_fuel', [])) &
    df['in.water_heater_fuel'].notna() &
    df['in.water_heater_fuel'].isin(model_valid.get('in.water_heater_fuel', [])) &
    df['num_of_stories'].notna() &
    df['num_of_stories'].isin(model_valid.get('num_of_stories', [])) &
    df['year_built'].notna() &
    df['year_built'].isin(model_valid.get('year_built', [])) &
    df['in.hvac_category'].notna() &
    df['in.hvac_category'].isin(model_valid.get('in.hvac_category', []))
)

n_complete = complete_mask.sum()
print(f"\n\n{'='*60}")
print(f"COMPLETE CASES (all features valid for model): {n_complete} / {len(df)} ({n_complete/len(df)*100:.1f}%)")
print(f"{'='*60}")

df_complete = df[complete_mask].copy()

print(f"\n--- Building Type distribution (complete cases) ---")
print(df_complete['in.building_type'].value_counts().to_string())

print(f"\n--- Climate Zone distribution (complete cases) ---")
print(df_complete['climate_zone_ashrae_2006'].value_counts().sort_index().to_string())

print(f"\n--- Floor Area Bin distribution (complete cases) ---")
print(df_complete['floor_area'].value_counts().to_string())

print(f"\n--- Year Built Bin distribution (complete cases) ---")
print(df_complete['year_built'].value_counts().to_string())

print(f"\n--- Heating Fuel distribution (complete cases) ---")
print(df_complete['in.heating_fuel'].value_counts().to_string())

print(f"\n--- Water Heater Fuel distribution (complete cases) ---")
print(df_complete['in.water_heater_fuel'].value_counts().to_string())

print(f"\n--- HVAC Category distribution (complete cases) ---")
print(df_complete['in.hvac_category'].value_counts().to_string())

print(f"\n--- Story Bin distribution (complete cases) ---")
print(df_complete['num_of_stories'].value_counts().to_string())

# Building type x climate zone coverage
print(f"\n--- Building Type x Climate Zone (complete cases) ---")
bt_cz = pd.crosstab(df_complete['in.building_type'], df_complete['climate_zone_ashrae_2006'], margins=True)
print(bt_cz.to_string())

# EUI summary for complete cases
print(f"\n--- EUI Summary for Complete Cases ---")
for bt in sorted(df_complete['in.building_type'].unique()):
    mask = df_complete['in.building_type'] == bt
    n = mask.sum()
    med_eui = df_complete.loc[mask, 'total_site_eui'].median()
    mean_eui = df_complete.loc[mask, 'total_site_eui'].mean()
    print(f"  {bt:<30} n={n:<5}  median_total_EUI={med_eui:7.1f}  mean_total_EUI={mean_eui:7.1f} kBtu/sqft")

# Records excluded and why
print(f"\n\n--- Records EXCLUDED ---")
excluded_mask = ~complete_mask
n_excluded = excluded_mask.sum()
print(f"Total excluded: {n_excluded}")

reason_bt = df['in.building_type'].isna() | ~df['in.building_type'].isin(model_valid.get('in.building_type', []))
reason_fuel = df['in.heating_fuel'].isna() | ~df['in.heating_fuel'].isin(model_valid.get('in.heating_fuel', []))
reason_dhw = df['in.water_heater_fuel'].isna() | ~df['in.water_heater_fuel'].isin(model_valid.get('in.water_heater_fuel', []))
reason_cz = df['climate_zone_ashrae_2006'].isna() | ~df['climate_zone_ashrae_2006'].isin(model_valid.get('climate_zone_ashrae_2006', []))
reason_yr = df['year_built'].isna() | ~df['year_built'].isin(model_valid.get('year_built', []))

print(f"  Building type not valid:    {(reason_bt & excluded_mask).sum()}")
print(f"  Heating fuel not valid:     {(reason_fuel & excluded_mask & ~reason_bt).sum()}")
print(f"  DHW fuel not valid:         {(reason_dhw & excluded_mask & ~reason_bt & ~reason_fuel).sum()}")
print(f"  Climate zone not valid:     {(reason_cz & excluded_mask & ~reason_bt & ~reason_fuel & ~reason_dhw).sum()}")
print(f"  Year built not valid:       {(reason_yr & excluded_mask & ~reason_bt & ~reason_fuel & ~reason_dhw & ~reason_cz).sum()}")

# PBA codes of excluded
print(f"\n  PBA codes of excluded (unmapped building types):")
pba_names = {1: 'Vacant', 4: 'Laboratory', 7: 'Public order and safety',
             12: 'Religious worship', 13: 'Public assembly', 26: 'Service', 91: 'Other'}
excluded_pba = df.loc[reason_bt, 'PBA'].value_counts().sort_index()
for pba_code, count in excluded_pba.items():
    desc = pba_names.get(pba_code, f'PBA={pba_code}')
    print(f"    PBA={pba_code} ({desc}): {count}")

print("\n\n" + "=" * 100)
print("ANALYSIS COMPLETE")
print("=" * 100)

# Save mapped dataset
output_path = os.path.join(BASE, 'cbecs2018_mapped_for_xgb.csv')
cols_to_save = ['PUBID', 'PBA', 'PBAPLUS', 'PUBCLIM', 'CENDIV', 'SQFT', 'NFLOOR', 'YRCONC',
                'in.building_type', 'floor_area', 'climate_zone_ashrae_2006',
                'in.heating_fuel', 'in.water_heater_fuel', 'num_of_stories',
                'year_built', 'in.hvac_category',
                'electricity_eui', 'natural_gas_eui', 'district_heating_eui',
                'other_fuel_eui', 'total_site_eui',
                'ELBTU', 'NGBTU', 'FKBTU', 'DHBTU', 'FINALWT',
                'HDD65', 'CDD65']
cols_to_save = [c for c in cols_to_save if c in df.columns]
df[cols_to_save].to_csv(output_path, index=False)
print(f"\nMapped dataset saved to: {output_path}")
