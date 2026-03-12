"""
One-time script to merge eGRID electricity emission factors into zipcode_lookup.json.

Reads the Excel file at Resources/Zipcode to Emission Factor, kgCO2e.xlsx,
maps each zipcode to its 3-digit prefix, and adds:
  - egrid_subregion
  - electricity_emission_factor_kg_co2e_per_kwh

to each prefix entry in backend/app/data/zipcode_lookup.json.
"""

import json
import os

import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXCEL_PATH = os.path.join(
    REPO_ROOT, "Resources", "Zipcode to Emission Factor, kgCO2e.xlsx"
)
LOOKUP_PATH = os.path.join(REPO_ROOT, "backend", "app", "data", "zipcode_lookup.json")

ZIP_COL = "Zip Code"
EF_COL = "Emission Factor (kgCO2e/kWh)"
SUBREGION_COL = "eGRID Subregion #1"


def main():
    # Load Excel
    df = pd.read_excel(EXCEL_PATH)
    print(f"Excel columns: {list(df.columns)}")
    print(f"Excel shape: {df.shape}")
    print(f"Sample rows:\n{df.head()}")

    # Drop rows with missing zipcodes or emission factors
    df = df.dropna(subset=[ZIP_COL, EF_COL])

    # Convert zipcodes to 3-digit prefixes, aggregate by prefix (mean EF)
    df["prefix"] = (
        df[ZIP_COL].astype(int).astype(str).str.zfill(5).str[:3]
    )

    prefix_groups = df.groupby("prefix").agg(
        ef=(EF_COL, "mean"),
        subregion=(SUBREGION_COL, lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else ""),
    ).reset_index()

    # Load existing zipcode lookup
    with open(LOOKUP_PATH) as fh:
        lookup = json.load(fh)

    # Merge
    updated = 0
    missing = 0
    for _, row in prefix_groups.iterrows():
        prefix = row["prefix"]
        if prefix in lookup["prefixes"]:
            lookup["prefixes"][prefix][
                "electricity_emission_factor_kg_co2e_per_kwh"
            ] = round(float(row["ef"]), 6)
            lookup["prefixes"][prefix]["egrid_subregion"] = str(row["subregion"])
            updated += 1
        else:
            missing += 1

    print(f"\nUpdated {updated} prefixes, {missing} prefixes not in lookup")

    # Write back
    with open(LOOKUP_PATH, "w") as fh:
        json.dump(lookup, fh, indent=2)

    print(f"Wrote updated lookup to {LOOKUP_PATH}")


if __name__ == "__main__":
    main()
