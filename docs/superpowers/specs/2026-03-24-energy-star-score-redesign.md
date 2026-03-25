# Energy Star Score UI Redesign

**Date:** 2026-03-24
**Status:** Approved for implementation
**Mockup:** `.superpowers/brainstorm/35258-1774406385/linear-gauge-v6.html`
**Affects:** `frontend/src/components/EnergyStarScore.vue`, `frontend/src/composables/useMeasureSelections.js`

---

## Overview

Three coordinated changes to the Energy Star Score component:

1. **Linear gauge** — replace three KPI chips with a horizontal zone gauge
2. **Button radius fix** — the Calculate Projected Score button uses the wrong border-radius token
3. **Projected EUI bug fix** — saved assessments show 0% savings due to null `savings_by_fuel`

---

## 1. Linear Gauge Redesign

### Layout

The `EnergyStarScore` card uses a permanent **3/4 + 1/4** layout:

- **Left 3/4** (`es-main`): donut gauges + linear gauge in a single horizontal row
- **Right 1/4** (`es-side`): action panel (calculate button or savings stats)

### Left Panel — Donut Pair

Two donut gauges side by side, connected by an SVG arrow:

| Element | State 1 (baseline only) | State 2 (post-retrofit) |
|---|---|---|
| Left donut | Baseline score (colored by zone) | Baseline score (same) |
| Arrow | Faint/gray, no badge | Colored SVG arrow + delta badge (e.g. "▲ +16 pts") |
| Right donut | Dashed placeholder "—" | Projected score (colored by zone) |

A muted headline sits above the donut pair: *"Better than 62% of similar buildings"* (0.6875rem, `--gray-5`).

**Donut zone colors** (determined by score):

| Score range | Arc color | Token |
|---|---|---|
| 0–29 | Orange | `--partner-orange-7` / `#F04C25` |
| 30–64 | Amber | `--partner-yellow-7` / `#F18D00` |
| 65–100 | Green | `--partner-green-7` / `#25852A` |

**SVG arrow color** matches the projected donut's zone color.

**Green gradient** on `es-main` background: applied only when projected score ≥ 65.

```css
background: linear-gradient(130deg, white 30%, #E9F7EA 100%);
```

### Left Panel — Linear Gauge

Sits to the right of the donut pair via `flex: 1`.

**Zone track** (height: 20px, `border-radius: 2px`):

| Zone | Score range | Width | Color |
|---|---|---|---|
| Low | 0–30 | 30% | `--partner-orange-3` |
| Moderate | 30–65 | 35% | `--partner-yellow-2` |
| High | 65–100 | 35% | `--partner-green-2` |
| ENERGY STAR band | 75–100 | 71.4% of High | `--partner-green-3` + dashed left border |

No text labels inside the zones — color provides the semantics.

**Scale ticks** below track at positions: 0, 30, 65, 75★, 100.

**EUI annotations** below scale:
- *Median EUI* (gray) at score 50 (left: 50%)
- *Target EUI ★* (green) at score 75 (left: 75%)

**Pointer (State 1 — baseline only):**
- Downward triangle above track at `score%` from left
- Color: `--partner-blue-7` (#005199)
- Callout above: score number (1rem bold) + EUI value (0.5625rem) below it, blue border/bg

**Pointer (State 2 — post-retrofit):**
- Blue solid dot (14×14px, no border/ring) centered vertically **inside** the track at baseline score position
- "62 baseline" label above the track in `--gray-6`, 0.625rem semibold
- Projected pointer triangle + callout above at projected score position, colored by zone
- **No ghost triangle** — the blue dot alone marks the baseline

**Close-score handling** (projected within ~5 pts of baseline):
- Projected callout stays above track as normal
- "← 62 baseline" label moves **below** the track instead of above
- Scale row gets extra top margin to clear the below-label

**Callout structure (score is dominant):**
```
[Score number — 1rem bold, zone color]
[EUI value · label — 0.5625rem, subordinate]
```
Border-radius: `--partner-radius-md` (4px). Border + text: zone color.

### Right Panel

**State 1 — no projected score:**
- Star icon (faint)
- Hint text: "Select upgrades below, then calculate your projected score"
- `PButton` (primary): "⭐ Calculate"

**State 2 — projected score available:**
- EUI reduction % — 1.25rem bold, colored by direction (green = reduction, orange = increase)
- "EUI reduction" label — 0.5625rem, gray-5, uppercase
- Divider
- Projected EUI value — 1rem, gray-7
- "projected EUI" label — 0.5625rem, gray-5, uppercase
- Recalculate button — outline variant, 26px height, 0.6875rem font (smaller than Calculate)

---

## 2. Button Border-Radius Fix

**File:** `EnergyStarScore.vue`

The existing `.es-btn` uses `border-radius: var(--partner-radius-lg)` (8px). Per Partner design system, buttons use `--partner-radius-sm` (2px).

**Fix:** Replace custom `.es-btn` with the `PButton` component, or change the border-radius token to `var(--partner-radius-sm)`.

---

## 3. Projected EUI Bug Fix (Saved Assessments)

**File:** `useMeasureSelections.js`

**Root cause:** Older saved assessments have `savings_by_fuel: null` on measures (field was added to the schema after those assessments were saved). The `projectedEui` computed silently skips any measure where `!m?.savings_by_fuel`, producing 0% savings even when `savings_kbtu_sf` is present and correct.

**Fix:** When `savings_by_fuel` is null, fall back to proportional distribution across fuels using `savings_kbtu_sf` and the baseline fuel ratios:

```js
for (const uid of selectedUpgradeIds.value) {
  const m = measures.value.find(m => m.upgrade_id === uid)
  if (!m) continue

  if (m.savings_by_fuel) {
    elec     -= m.savings_by_fuel.electricity
    gas      -= m.savings_by_fuel.natural_gas
    oil      -= m.savings_by_fuel.fuel_oil
    propane  -= m.savings_by_fuel.propane
    district -= m.savings_by_fuel.district_heating
  } else if (m.savings_kbtu_sf != null && baseline.value.total_eui_kbtu_sf > 0) {
    // Proportional fallback for older saved assessments missing savings_by_fuel
    const ratio = m.savings_kbtu_sf / baseline.value.total_eui_kbtu_sf
    elec     -= baseByFuel.electricity      * ratio
    gas      -= baseByFuel.natural_gas      * ratio
    oil      -= baseByFuel.fuel_oil         * ratio
    propane  -= baseByFuel.propane          * ratio
    district -= baseByFuel.district_heating * ratio
  }
}
```

**Note:** The proportional fallback is an approximation — it assumes savings are distributed across fuels proportionally to baseline consumption. This is acceptable because `savings_by_fuel` will always be present on assessments run after the schema change; the fallback only applies to historical data.

---

## Label Changes

- "Your EUI" → **"Calculated EUI"** in all callout labels and display text

---

## Files to Modify

| File | Change |
|---|---|
| `frontend/src/components/EnergyStarScore.vue` | Replace KPI chips with linear gauge component; fix button border-radius; rename "Your EUI" |
| `frontend/src/composables/useMeasureSelections.js` | Fix `projectedEui` computed with `savings_by_fuel` fallback |
