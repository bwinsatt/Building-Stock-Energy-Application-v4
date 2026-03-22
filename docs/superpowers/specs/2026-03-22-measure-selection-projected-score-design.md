# Measure Selection & Projected ENERGY STAR Score

**Date**: 2026-03-22
**Status**: Approved

## Overview

Allow users to select upgrade measures from the assessment results table, persist those selections to a project (SQLite), compute a projected post-upgrade EUI from the selected measures, and run an ENERGY STAR Portfolio Manager score calculation to show the projected score alongside the baseline.

Target users are sustainability managers at commercial real estate companies (not energy audit professionals), so UX and language must be accessible to non-experts.

## Interaction Model

### Selection Rules

- Users select measures via checkboxes in the measures table (Individual Measures and Measure Packages sections only; non-applicable measures have no checkboxes).
- **Package → Individual lockout**: Selecting a package disables and grays out its constituent individual measures. A tooltip on each disabled checkbox explains: "Included in [Package Name]."
- **Individual → Package conflict (auto-replace)**: If a user has already selected individual measures and then selects a package that contains one or more of them, show a brief inline message listing all overlapping measures: "This package includes [Measure A, Measure B, ...], which you already selected. Selecting this package will replace those individual picks." On confirm, deselect all overlapping individual measures and select the package. If only one measure overlaps, the message uses singular form.
- Only applicable measures are selectable.

### Projected EUI Calculation

- **Simple sum of per-fuel deltas**: For each selected measure, subtract its per-fuel savings (kBtu/sf) from the baseline. All computed client-side from data in the assessment response.
- **Required backend change**: The current `MeasureResult` response does not include per-fuel savings in kBtu/sf. A new field `savings_by_fuel: FuelBreakdown | None` must be added to `MeasureResult`, providing per-fuel savings in kBtu/sf (matching the baseline `eui_by_fuel` units). This is populated from the delta model outputs (already computed in `assessment.py` but not currently exposed in the response). Without this field, client-side projected EUI computation is not possible.
- No backend re-prediction is needed or possible — the XGBoost delta models predict savings independently against the baseline, and there is no model for combined measure interactions (packages are the only way combined effects are captured in the training data).
- Include a small disclaimer below the projected EUI chip in the score card's right half (state 3/4): "Estimates assume independent measure savings."

### Projected ENERGY STAR Score

- **On-demand button**: "Calculate Projected Score" appears in the right half of the score card once at least one measure is selected.
- Sends the projected per-fuel EUI to the ESPM Target Finder API (same mechanism as baseline score, but with projected consumption values).
- After calculation, a "Recalculate" button is shown in case selections changed.
- **Error handling**: If the ESPM API call fails (network error, rate limit, timeout), show an error message inline in the right half of the score card with a "Retry" button. The card remains in state 3 (does not advance to state 4). Same error UX pattern as the existing baseline score error state.
- **Deselect all after calculating**: If the user deselects all measures after a projected score has been calculated, the card reverts to state 2 (instructional text). The projected ESPM result is cleared from both the UI and the database.

## UI Layout

### ENERGY STAR Score Card — Four-State Progression

The card uses progressive disclosure. The split layout only appears once baseline data exists.

**State 1 — No score yet**:
Full-width trigger button: "Calculate ENERGY STAR Score / Compare against similar buildings nationwide." Takes the entire card width (current design).

**State 2 — Baseline calculated, no measures selected**:
Card transitions to a 50/50 split layout:
- **Left half**: Baseline gauge (donut chart with score), percentile headline, metric chips (Target EUI, Median EUI, Your EUI), ESPM property type. Label: "ENERGY STAR Score."
- **Center**: Vertical divider line.
- **Right half**: Instructional text — "Select upgrades below to calculate your post-retrofit ENERGY STAR score."

**State 3 — Measures selected, score not yet calculated**:
- **Left half**: Baseline gauge + metrics (label changes to "Baseline Score").
- **Right half**: Selection summary — upgrade count, projected EUI with reduction %, and "Calculate Projected Score" button (Partner blue-7).

**State 4 — Projected score calculated**:
- **Left half**: Baseline gauge + metrics (label: "Baseline Score").
- **Center divider**: Arrow circle with "+N pts" delta badge.
- **Right half**: Green-tinted background (gradient from green-1 to white). Projected gauge, percentile text ("Would be better than N% of similar buildings"), projected EUI chip, EUI reduction chip, upgrade count, "Recalculate" outline button.

### Score Gauge Color Thresholds

| Score Range | Color | Token |
|-------------|-------|-------|
| >= 75 | Green | `--partner-green-7` (#25852A) |
| 50-74 | Yellow | `--partner-yellow-7` (#F18D00) |
| < 50 | Orange | `--partner-orange-7` (#F04C25) |

### Gauge Centering

The score number is positioned slightly above vertical center within the donut so that "out of 100" fits cleanly below it, with both lines together vertically centered as a unit inside the circle.

### Design System Compliance

All border radii must use the Partner design system radius tokens from `partner-radius.css` (base: `--radius: 0.625rem` / 10px). Do not hardcode radius values. All colors must reference Partner color tokens — no Tailwind defaults or arbitrary hex values outside the Partner palette.

**Migration note**: The existing `EnergyStarScore.vue` gauge uses hardcoded Tailwind colors (`#22c55e`, `#eab308`, `#ef4444`). As part of this feature, migrate the existing baseline gauge colors to the Partner tokens listed above so both gauges are visually consistent.

### Measures Table Changes

- New sticky checkbox column as the first column (before Measure name). Sticky left: 0, z-index consistent with existing sticky columns.
- Existing sticky column left offsets shift right to accommodate the checkbox column width.
- Checkboxes appear only in the Individual Measures and Measure Packages sections.
- Non-applicable measures section: no checkboxes.
- When a package is selected, its constituent individual measures show disabled/grayed checkboxes with a tooltip.

## Data Flow

### Persistence — SQLite Schema

New table `measure_selections`:

```sql
CREATE TABLE IF NOT EXISTS measure_selections (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  building_id INTEGER NOT NULL UNIQUE,
  selected_upgrade_ids TEXT NOT NULL DEFAULT '[]',
  projected_espm TEXT,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (building_id) REFERENCES buildings(id) ON DELETE CASCADE
);
```

- `selected_upgrade_ids`: JSON array of integer upgrade IDs (e.g., `[3, 5, 8]`).
- `projected_espm`: JSON blob of `EnergyStarResponse` (null until calculated).
- `UNIQUE(building_id)`: One selection set per building.
- `updated_at`: Must be explicitly set to `CURRENT_TIMESTAMP` in UPDATE queries (SQLite `DEFAULT` only applies on INSERT).

### Save Triggers

| Event | Action |
|-------|--------|
| Checkbox toggle | Auto-save `selected_upgrade_ids` via PUT endpoint (optimistic update — UI updates immediately, revert on failure with toast error) |
| "Calculate Projected Score" click | Save `projected_espm` via PUT endpoint |
| Re-assessment (new assessment saved) | Clear `projected_espm` (baseline changed). Keep `selected_upgrade_ids` — auto-reconcile on frontend |

### Auto-Reconciliation on Re-Assessment

When a new assessment is loaded and saved selections exist:
1. Frontend loads `selected_upgrade_ids` from the database.
2. Filters out any IDs not present in the new assessment's `measures[].upgrade_id` list.
3. If any IDs were removed, saves the reconciled list back to the database.
4. Projected ESPM result is already cleared by the backend on re-assessment.

## Backend Changes

### Schema Changes

**`MeasureResult` Pydantic model** — new fields:
```python
constituent_upgrade_ids: list[int] | None = None
savings_by_fuel: FuelBreakdown | None = None  # per-fuel savings in kBtu/sf
```
- `constituent_upgrade_ids`: Populated for package measures with the upgrade IDs of their constituent individual measures. `None` for individual measures. The mapping is defined in `applicability.py` where package rules reference their component upgrades — this must be extracted into a structured constant (e.g., `PACKAGE_CONSTITUENTS: dict[int, list[int]]`) that both the applicability checker and the response builder can reference.
- `savings_by_fuel`: Per-fuel savings in kBtu/sf (same units/structure as `BaselineResult.eui_by_fuel`). Already computed internally in `assessment.py` during the upgrade loop (the per-fuel deltas in kWh/sf, converted to kBtu/sf) but not currently exposed in the response. Must be added to enable client-side projected EUI computation.

**`assessment.py`** — When building `MeasureResult` objects:
- Populate `savings_by_fuel` from the delta model outputs (already computed, just not serialized).
- For packages, populate `constituent_upgrade_ids` from the `PACKAGE_CONSTITUENTS` mapping.

### ResStock Packages

ResStock does not currently define package upgrades. The package/individual conflict logic (lockout, auto-replace) only applies to ComStock buildings. ResStock buildings will only see individual measure checkboxes with no package interaction rules.

### New Database Functions (`database.py`)

```python
def save_selections(building_id: int, upgrade_ids: list[int]) -> None
def save_projected_espm(building_id: int, espm_result: dict) -> None
def get_selections(building_id: int) -> dict | None
def clear_projected_espm(building_id: int) -> None
```

### Assessment Save Hook

When `save_assessment()` is called (re-assessment), also call `clear_projected_espm(building_id)` to invalidate stale projected scores.

### New API Endpoints (`routes.py`)

**`PUT /projects/{project_id}/buildings/{building_id}/selections`**
- Body: `{ "selected_upgrade_ids": [int] }`
- Upserts the selection row for the building.
- Returns 200 with the saved selection.

**`GET /projects/{project_id}/buildings/{building_id}/selections`**
- Returns `{ "selected_upgrade_ids": [int], "projected_espm": EnergyStarResponse | null, "updated_at": str | null }`.
- If no row exists, returns 200 with empty defaults: `{ "selected_upgrade_ids": [], "projected_espm": null, "updated_at": null }`. Does not return 404.

**`POST /energy-star/projected-score`**
- Body: `{ "building": BuildingInput, "projected_eui_by_fuel": FuelBreakdown, "address": str | null }`
- Accepts projected per-fuel EUI in kBtu/sf (computed client-side from baseline minus selected deltas).
- Internally constructs a synthetic `BaselineResult` from the projected `FuelBreakdown` so the existing `EnergyStarService.get_score()` and `build_target_finder_xml()` can be reused without modification.
- Calls ESPM Target Finder API with the projected consumption values.
- Returns `EnergyStarResponse`.

## Frontend Changes

### Modified Components

**`EnergyStarScore.vue`**
- Expanded to handle four-state progression (trigger → split with baseline + instructional text → measures selected → projected score).
- New props: `selectedMeasures: MeasureResult[]`, `projectedEui: ProjectedEui | null`, `projectedEspm: EnergyStarResponse | null`.
- Emits `calculate-projected` event when the Calculate button is clicked.
- Baseline label changes from "ENERGY STAR Score" to "Baseline Score" when projected side is populated (state 3+).

**`MeasuresTable.vue`**
- New props: `selectedUpgradeIds: Set<number>`, `packageConstituentMap: Map<number, number[]>`.
- New emit: `toggle-measure(upgradeId: number)`.
- Sticky checkbox column as first column in Individual and Package sections.
- Disabled/grayed checkboxes for individual measures that are constituents of a selected package, with tooltip.
- Auto-replace confirmation dialog when selecting a package that overlaps with individual selections.

### New Composable

**`useMeasureSelections.ts`**
- `selectedUpgradeIds: Ref<Set<number>>` — reactive set of selected upgrade IDs.
- `projectedEui: ComputedRef<ProjectedEui | null>` — computed from selected measures' per-fuel deltas subtracted from baseline.
- `projectedEspm: Ref<EnergyStarResponse | null>` — result from ESPM API.
- `toggleMeasure(upgradeId: number)` — handles package ↔ individual conflict logic, auto-saves to backend.
- `calculateProjectedScore()` — calls `/energy-star/projected-score`, saves result to backend.
- `loadSelections(buildingId: number)` — loads saved selections from backend.
- `reconcileSelections(measures: MeasureResult[])` — filters stale IDs, saves reconciled list.

### New Type

**`ProjectedEui`** in `types/assessment.ts`:
```typescript
interface ProjectedEui {
  total_eui_kbtu_sf: number
  eui_by_fuel: FuelBreakdown
  reduction_pct: number
}
```

**`MeasureResult`** — add to existing interface:
```typescript
constituent_upgrade_ids?: number[] | null
savings_by_fuel?: FuelBreakdown | null  // per-fuel savings in kBtu/sf
```

### Parent Orchestration

The page/view component that hosts both `EnergyStarScore` and `MeasuresTable`:
- Instantiates `useMeasureSelections` with the assessment result and baseline.
- Passes selection state down to both components as props.
- `MeasuresTable` emits `toggle-measure` → composable handles logic + persistence.
- `EnergyStarScore` reads selection state reactively to determine which of the four states to render.

## Visual Reference

Mockups for the four-state ENERGY STAR card progression are saved in:
`.superpowers/brainstorm/47046-1774214815/score-progression.html`
