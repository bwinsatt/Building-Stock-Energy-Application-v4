# Carbon Performance Export — Design Spec

**Date:** 2026-06-29
**App:** Building Stock Energy Estimator v4 (Rapid Energy Audit / REAC)
**Status:** Approved design, pending implementation plan

## Goal

Add an **Export** button to the energy efficiency measures results that generates a
filled copy of the SiteLynx **Carbon Performance import workbook**
(`sitelynx_carbon_performance_import.xlsx`, sheet `Export BlueLynx`) and downloads it.
The filled workbook is later pasted into the real Carbon Performance calculator in
SL Heaven / SiteLynx, where its formulas resolve.

## Constraints

- **The template format must not change.** Its named ranges all reference an external
  workbook (`[1]`); they resolve only after the filled sheet is pasted into the real
  calculator. We write **scalar values into specific cells only** — no formulas, no
  structural edits, no touching helper columns (AM/AN) or reference tables.
- One building per file (the active building). Multi-building is out of scope.
- Up to 30 measure rows (template rows 6-35, pre-labeled `Project 1`..`Project 30`).
- Keep backend logic FastAPI-decoupled and stateless (SiteLynx/KIP port readiness, per CLAUDE.md).

## Approach (chosen)

**Backend openpyxl endpoint.** A new endpoint fills the template server-side with
openpyxl and streams the file back. openpyxl round-trips the existing `.xlsx`,
preserving defined names, styles, and helper columns; we only set cell values. No
public API schema changes.

Approaches considered and rejected:
- *Client-side JS fill (SheetJS/exceljs):* risks dropping/corrupting the external-workbook
  named ranges and styling on read-modify-write of an existing template; requires response
  schema changes. Rejected for template-fidelity risk.
- *Hybrid (extend response + thin file-gen endpoint):* still needs schema changes and adds
  moving parts. Rejected as more complex than necessary.

## Components

### Backend
- **Template asset:** `backend/app/data/templates/sitelynx_carbon_performance_import.xlsx`
  (copied from the app root, shipped with the backend).
- **`services/export_service.py`** (new): self-contained function
  `build_carbon_performance_workbook(building, selected_upgrade_ids, espm_property_type=None) -> bytes`.
  Internally calls `assess_building_for_export(building)` to get baseline/measures/rates,
  filters measures, loads the template, writes cells, returns `.xlsx` bytes. No FastAPI types.
- **`services/assessment.py`** (small internal refactor): expose
  `assess_building_for_export(building) -> (BuildingResult, rates)` so the export path gets
  the per-fuel utility `rates` dict already computed at `assessment.py:325`. The public
  `/assess` response (`AssessmentResponse`) is unchanged; rates are surfaced only to the
  internal export call.
- **`api/routes.py`:** `POST /export/carbon-performance`
  - Request: `{ building: BuildingInput, selected_upgrade_ids: list[int], espm_property_type: str | None }`
  - Response: `StreamingResponse`,
    `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`,
    `Content-Disposition: attachment; filename="CarbonPerformance_<zip>.xlsx"`.

ESPM property type (AJ9) is **sent from the frontend** in the request (it is already
computed/displayed by the energy-star panel). The export endpoint does not call the
energy-star service. If absent, AJ9 is left blank.

### Frontend
- **Export button** in the `MeasuresTable.vue` card header (top-right, next to the title
  and summary stats). The component **emits an `export` event**; it does not call the API
  itself.
- **Partner-components compliance:** the button uses `PButton` with `icon="download"`
  (Carbon icon set, already bundled in `PIcon` — no new asset needed; `document-export` is
  the alternative glyph). Label e.g. "Export to Carbon Performance". Match the existing
  `PButton` usage in this file for size/variant. No raw HTML buttons or non-library icons.
- **Loading/disabled state:** disable the button and show a spinner/`loading` state while
  the export request is in flight; surface failures via the existing error pattern.
- **Parent results view** (holds building input, `selectedUpgradeIds`, and ESPM type)
  handles the event: POSTs the request via the `useAssessment` composable, receives the
  blob, and triggers a browser download.

## Cell Mapping

### Measure rows
One selected measure per row, starting **row 6**, in the table's current display order,
capped at 30 rows. `elec_savings_kwh = measure.electricity_savings_kwh * sqft`;
`gas_savings_therms_total = measure.gas_savings_therms * sqft`.

| Col | Field | Source |
|-----|-------|--------|
| C | Description and Performance Specification | `measure.name` |
| D | Premium Cost | `measure.cost.installed_cost_total` |
| H | Total Cost Savings — Electricity ($) | `elec_savings_kwh * rate_elec` |
| I | Total Cost Savings — Gas ($) | `gas_savings_therms_total * rate_gas` |
| J | Total Cost Savings — Water ($) | blank (water not modeled) |
| L | Total Consumption Savings — Electricity (kWh) | `elec_savings_kwh` |
| M | Total Consumption Savings — Gas (Therm) | `gas_savings_therms_total` |

All other measure columns (E, F, G, K, N, O, P-AB) are left untouched.

### Baseline Metrics (values in column AJ)

| Cell | Field | Source / Value |
|------|-------|----------------|
| AJ8 | Property Zip Code | `building.zipcode` |
| AJ9 | Property Type | `espm_property_type` from request (blank if absent) |
| AJ10 | Baseline Year | leave existing `2024` |
| AJ11 | State | `input_summary.state` |
| AJ14 | eGRID Region | `egrid_subregion` from zipcode lookup |
| AJ15 | Climate Zone | `input_summary.climate_zone` |
| AJ16 | Baseline Electric Usage (kWh) | `baseline.eui_by_fuel.electricity * sqft / KWH_TO_KBTU` |
| AJ17 | Total Electric Cost ($) | `AJ16 * rate_elec` |
| AJ20 | Natural Gas (Therms) | `baseline.eui_by_fuel.natural_gas * sqft / KBTU_PER_THERM` (100) |
| AJ21 | Total Natural Gas Cost ($) | `AJ20 * rate_gas` |
| AJ24 | Building Size (SF) | `building.sqft` |
| AJ32 | Grid Decarbonization Model | `"NREL Cambium, 2022"` |

Left blank / default (not written): AJ6, AJ7 (pre-filled U.S. / Imperial), AJ12 (Utility),
AJ13 (Utility Decarb Goal Year), AJ18 ($/kWh), AJ19, AJ22 ($/Therms), AJ23, AJ25 (Grid
Emission Factor), AJ26-AJ31, AJ33-AJ35.

## Data Flow

```
Export click (MeasuresTable emits 'export')
  -> parent POSTs { building, selected_upgrade_ids, espm_property_type }
  -> export_service
       -> assess_building_for_export(building)  => baseline, measures, rates
       -> filter measures to selected_upgrade_ids
            (fallback: all applicable individual measures if none selected; cap 30)
       -> openpyxl load template
       -> write measure rows (C/D/H/I/L/M from row 6)
       -> write baseline metrics (AJ cells)
       -> save to BytesIO
  -> StreamingResponse (.xlsx)
  -> browser download
```

## Edge Cases / Error Handling

- **No measures checked** -> fall back to all applicable individual measures.
- **>30 measures** -> write the first 30; log/flag that the list was truncated.
- **Missing rate or fuel** (rate `None`/0, no gas) -> leave that cost/consumption cell
  blank rather than writing 0.
- **Zip lookup miss** -> state / climate zone / eGRID cells left blank; export still succeeds.
- **ESPM type absent** -> AJ9 left blank.
- **Template missing/corrupt** -> 500 with a clear message.

## Testing

- **Unit:** `export_service` produces a workbook; assert specific cells (C6, D6, H6, L6,
  AJ8, AJ9, AJ16, AJ17, AJ32) for the `office_input` fixture.
- **Unit:** fallback-to-applicable when no IDs; 30-row cap behavior.
- **Integrity:** reload the generated file with openpyxl and assert defined names and the
  `Export BlueLynx` sheet survive (guards against openpyxl dropping reference-table named
  ranges).
- **API:** endpoint returns 200 with correct content-type and filename.

## Implementation Notes

- The azure App Service migration is complete and will be merged to `main`. Branch
  **`feat/carbon-performance-export`** off **`main`** (which will then contain the same code
  as the current `feature/azure-app-service-migration` branch).
- AJ32's exact value (`"NREL Cambium, 2022"`) must match the calculator's dropdown label;
  verify on first real paste into the Carbon Performance workbook.
- `KWH_TO_KBTU` lives in `app/constants.py`; add `KBTU_PER_THERM` (100) there if not present.
