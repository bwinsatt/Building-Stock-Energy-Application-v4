# BPS Square Footage Conflict Resolution

**Date:** 2026-03-23
**Status:** Draft

## Problem

When a user looks up an address, the system computes building square footage from OSM polygon footprint × number of stories. This estimate can diverge significantly from reality — e.g., 210 N Wells St in Chicago: OSM computes 982,792 sqft vs the benchmarking-reported 597,377 sqft. The OSM calculation doesn't account for setbacks, parking podiums, non-conditioned space, or irregular building geometry.

Benchmarking data from ENERGY STAR Portfolio Manager is owner-reported and almost always more accurate for conditioned floor area. The system now pulls `reported_gross_floor_area` from 16 BPS jurisdictions, but the UI doesn't surface it or let users import it.

## Solution

Extend the existing BPS "found" banner to show a square footage comparison (benchmarking-reported vs OSM-estimated) and offer two import actions with a clear visual hierarchy favoring full import.

## Design

### Banner Layout (Option A: Inline Comparison)

The existing BPS "found" banner is extended with two additions:

1. **Square Footage Comparison Row** — A subtle inset box between the data grid and buttons showing:
   - "Reported (Benchmarking): **597,377 ft²**" — bold, primary text color
   - "vs"
   - "Estimated (OSM): 982,792 ft²" — regular weight, secondary text color

2. **Two-Button Import** — Replaces the single "Import to Utility Data" button:
   - **"Import All Data"** — Primary/prominent button (Partner `success` contained variant). Imports energy consumption data AND overwrites the sqft field with the benchmarking-reported value.
   - **"Import Energy Data Only"** — De-emphasized text link (Partner `neutral` link appearance). Imports only energy consumption data, leaves sqft unchanged.

### When to Show

- The square footage comparison row appears **whenever** `reported_gross_floor_area` is non-null in the BPS result, regardless of how close the values are to the OSM estimate.
- If `reported_gross_floor_area` is null (data not available from that jurisdiction), the banner falls back to the current single "Import to Utility Data" button behavior.
- If no OSM sqft was computed (e.g., no polygon found), the comparison row still shows the reported value but omits the "vs Estimated" portion.

### Design Tokens (Partner Components)

| Element | Token | Value |
|---|---|---|
| Banner background | Existing BPS "found" | `linear-gradient(135deg, #ecfdf5, #f0fdf4)` |
| Banner border | Existing BPS "found" | `1px solid #86efac` |
| Banner border-radius | Existing BPS spec | `6px` |
| Data labels | `.partner-subhead` | 10px, uppercase, 0.4px letter-spacing, `#6F7881` |
| Data values | `.partner-headline1` | 14px, semibold, `#333E47` |
| Comparison box bg | — | `rgba(255, 255, 255, 0.6)` |
| Comparison box border | `--partner-gray-3` | `1px solid #D9DDE1` |
| Comparison box radius | `--partner-radius-md` | `4px` |
| Reported sqft value | `.partner-body` bold | 14px, font-weight 700, `#333E47` |
| Estimated sqft value | `.partner-body` regular | 14px, font-weight 400, `#6F7881` |
| "Import All Data" button | `PButton variant="success"` | `#25852A` bg, white text, 2px radius, 32px height |
| "Import Energy Data Only" | `PButton appearance="link" variant="neutral"` | underlined, `#6F7881`, no border |

### Data Flow

#### "Import All Data" clicked:
1. Import energy data (same as current `importBpsData`): `electricity_kwh`, `natural_gas_therms`, `fuel_oil_gallons`, `district_heating_kbtu`
2. Import `site_eui_kbtu_sf` and `energy_star_score` (current behavior)
3. **Additionally**: Set `form.sqft` to `bpsResult.reported_gross_floor_area`
4. Set `fieldSources.value['sqft']` to `{ value: <reported_sqft>, source: 'benchmarking', confidence: bpsResult.match_confidence }`
5. The sqft field shows a "benchmarking" source badge (green, existing style)
6. Auto-expand utility data section, dismiss BPS banner

#### "Import Energy Data Only" clicked:
1. Import energy data only (same as current `importBpsData`)
2. Leave `form.sqft` unchanged (keeps OSM/computed/user-entered value)
3. Auto-expand utility data section, dismiss BPS banner

### Backend Changes

**Already complete.** The `reported_gross_floor_area` field has been added to:
- `_transform_result()` in `bps_query.py` — included in the standardized BPS result schema
- `_NUMERIC_FIELDS` set — ensures proper float conversion
- Field mappings in `bps_config.py` for 16 jurisdictions (Chicago, NYC, DC, Denver, Seattle, Cambridge, San Francisco, Berkeley, Philadelphia, Atlanta, Boston, San Jose, CA AB802, CO BPS, Miami, Montgomery County, Kansas City)

Three jurisdictions lack this field: LA EBEWE, Austin ECAD, Orlando BEWES.

### Frontend Changes

**`BuildingForm.vue`:**
- Modify the BPS "found" banner section to conditionally render the sqft comparison row when `bpsSearch.result.value.reported_gross_floor_area` is non-null
- Replace single import button with two-button layout when comparison is shown
- Update `importBpsData()` to accept a parameter indicating whether to import sqft
- Add new `importAllBpsData()` function (or parameterize existing) that also writes to `form.sqft` and `fieldSources`

### Edge Cases

- **No OSM sqft available**: Show reported sqft without the "vs Estimated" comparison. Both buttons still work — "Import All" sets sqft from benchmarking, "Import Energy Only" leaves sqft as-is (null/empty, user must enter manually).
- **No reported_gross_floor_area**: Fall back to current single-button behavior ("Import to Utility Data").
- **User manually edited sqft before BPS search**: "Import All" overwrites their manual entry. This is intentional — the user is explicitly choosing to import all data.
- **User edits sqft after import**: Source badge disappears (existing behavior for any manually-edited field).

## Out of Scope

- Automatic sqft conflict detection/resolution without user action
- Displaying reported sqft anywhere other than the BPS banner
- Using reported sqft to recalculate the Site EUI displayed in the banner (the banner shows the API-reported EUI as-is)
- Showing the sqft comparison for jurisdictions that don't provide gross floor area
