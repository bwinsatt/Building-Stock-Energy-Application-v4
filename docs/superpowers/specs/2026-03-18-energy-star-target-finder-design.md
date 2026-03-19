# ENERGY STAR Target Finder Integration — Design Spec

## Overview

Add ENERGY STAR scoring to the building stock energy estimation tool by integrating with the ESPM Target Finder API. Users can request an ENERGY STAR score for their building after running an assessment, displayed as a dedicated section in the results view.

## Approach

**Target Finder Only** — a single stateless API call to ESPM's `POST /targetFinder` endpoint. No ESPM property creation, no meter management, no persistent ESPM state. The service maps existing assessment output to the Target Finder schema and returns the score + comparison metrics.

This approach was chosen over full property creation because:
- All required inputs are already available from the assessment output
- No ESPM property lifecycle management needed
- Single HTTP call vs. 5-6 chained calls
- Persistence/CRUD is out of scope (SQLite being added in a parallel effort)

## Backend

### New Service: `backend/app/services/energy_star.py`

`EnergyStarService` class with a single public method:

```python
def get_score(self, building: BuildingInput, baseline: BaselineResult, address: str | None = None) -> EnergyStarResponse
```

**Responsibilities:**
1. Map `building.building_type` to ESPM `primaryFunction` via static lookup
2. Build Target Finder XML request
3. Call ESPM API with Basic Auth
4. Parse XML response into `EnergyStarResponse`

No dependencies on FastAPI request/response objects — pure service layer callable from any entry point.

### New Endpoint: `POST /energy-star/score`

Added to `backend/app/api/routes.py`.

**Does not re-run the assessment.** The frontend sends the already-computed baseline data. If inputs have changed since the last assessment, the frontend handles the stale state warning (see Frontend section).

### Request Schema: `EnergyStarRequest`

```python
class EnergyStarRequest(BaseModel):
    building: BuildingInput          # reuse existing schema
    baseline: BaselineResult         # reuse existing schema
    address: str | None = None       # full street address if available from /lookup
```

### Response Schema: `EnergyStarResponse`

```python
class EnergyStarResponse(BaseModel):
    score: int | None                    # 1-100, None if ineligible
    eligible: bool                       # whether building type received a score
    median_eui_kbtu_sf: float | None     # median site EUI for this building type
    target_eui_kbtu_sf: float | None     # EUI needed for ENERGY STAR score of 75
    design_eui_kbtu_sf: float | None     # building's site EUI as calculated by ESPM
    percentile_text: str | None          # e.g. "Better than 72% of similar buildings"
    espm_property_type: str              # the mapped ESPM primaryFunction used
    reasons_for_no_score: list[str] | None  # if no score, why
```

### Building Type Mapping

Static dict mapping frontend building types to ESPM `primaryFunction` values:

| Building Type | ESPM primaryFunction |
|---|---|
| Office | Office |
| Warehouse and Storage | Non-Refrigerated Warehouse |
| Mercantile | Retail Store |
| Lodging | Hotel |
| Healthcare | Hospital (General Medical & Surgical) |
| Education | K-12 School |
| Food Sales | Supermarket/Grocery Store |
| Food Service | Restaurant |
| Multi-Family | Multifamily Housing |
| Public Assembly | Convention Center |
| Public Order and Safety | Courthouse |
| Religious Worship | Worship Facility |
| Service | Other - Services |
| Mixed Use | Mixed Use Property |

A corresponding property use XML element mapping (e.g., `"Office"` → `"office"`, `"Retail Store"` → `"retail"`). Types without a specific property use element fall back to a generic type.

### Energy Mapping

Baseline per-fuel EUI (kBtu/sf) is converted to total annual energy (kBtu) by multiplying by sqft. All fuels use kBtu as the unit sent to ESPM — no unit conversion beyond `eui × sqft`.

| Baseline Fuel | ESPM energyType | Unit |
|---|---|---|
| electricity | Electric | kBtu |
| natural_gas | Natural Gas | kBtu |
| fuel_oil | Fuel Oil No 2 | kBtu |
| propane | Propane | kBtu |
| district_heating | District Steam | kBtu |

Only fuels with nonzero consumption are included in the `estimatedEnergyList`.

### Target Finder XML Request Structure

```xml
<targetFinder>
    <propertyInfo>
        <name>{auto-generated from building type + address}</name>
        <primaryFunction>{mapped ESPM type}</primaryFunction>
        <grossFloorArea units="Square Feet" temporary="false">
            <value>{sqft}</value>
        </grossFloorArea>
        <plannedConstructionCompletionYear>{year_built}</plannedConstructionCompletionYear>
        <address address1="{address or 'N/A'}"
                 postalCode="{zipcode}"
                 state="{state from zipcode lookup}"
                 country="US"/>
        <numberOfBuildings>1</numberOfBuildings>
    </propertyInfo>
    <propertyUses>
        <{useElement}>
            <name>{building type}</name>
            <useDetails>
                <totalGrossFloorArea units="Square Feet">
                    <value>{sqft}</value>
                </totalGrossFloorArea>
                <!-- all other use details omitted — ESPM auto-defaults -->
            </useDetails>
        </{useElement}>
    </propertyUses>
    <estimatedEnergyList>
        <entries>
            <!-- one designEntry per nonzero fuel -->
            <designEntry>
                <energyType>{mapped type}</energyType>
                <energyUnit>kBtu (thousand Btu)</energyUnit>
                <estimatedAnnualEnergyUsage>{eui * sqft}</estimatedAnnualEnergyUsage>
            </designEntry>
        </entries>
    </estimatedEnergyList>
    <target>
        <targetTypeScore>
            <value>75</value>
        </targetTypeScore>
    </target>
</targetFinder>
```

**Address handling:** Use the full street address if available from the `/lookup` flow. If not available, fabricate a minimal address with `address1="N/A"` and the zipcode.

### ESPM API Client

- **XML construction:** `xml.etree.ElementTree` (stdlib)
- **HTTP client:** `httpx` for outgoing requests
- **XML parsing:** `ElementTree` — extract metrics by `name` attribute
- **Auth:** Basic HTTP Auth
- **Config (env vars):**
  - `ESPM_USERNAME` — Basic Auth username
  - `ESPM_PASSWORD` — Basic Auth password
  - `ESPM_BASE_URL` — defaults to `https://portfoliomanager.energystar.gov/wstest` (test env)

### Error Handling

| Scenario | Behavior |
|---|---|
| Network/timeout (15s) | HTTPException 502: "ENERGY STAR service unavailable" |
| Auth failure (401) | HTTPException 502: "ENERGY STAR authentication failed" |
| No score returned but metrics available | `eligible=False`, still parse median/target EUI |
| Malformed XML response | HTTPException 502 |
| Unmapped building type (e.g. future ResStock single-family types) | Return `eligible=False` with reason, do not call ESPM |

HTTP timeout: 15 seconds for the outgoing `httpx` call.

No retry logic — if the call fails, the user clicks the button again.

### Environment Notes

- `ESPM_BASE_URL` defaults to the **test** environment. Switch to `https://portfoliomanager.energystar.gov/ws` for production deployment.
- Currently only ComStock building types + Multi-Family (ResStock) are supported. Other ResStock types (Single-Family, Mobile Home) are not mapped and will return `eligible=False`.

## Frontend

### New Component: `EnergyStarScore.vue`

Located in `frontend/src/components/`. Sits between `BaselineSummary` and `MeasuresTable` in `AssessmentView.vue`.

### Component States

1. **Ready** — "Calculate ENERGY STAR Score" button appears after assessment completes
2. **Loading** — Spinner while calling `/energy-star/score`
3. **Result with score** — Compact card: circular gauge with score (1-100), percentile text, target EUI (for 75), median EUI
4. **Result without score** — Same card layout but shows "Score not available for this building type" with median EUI and reasons displayed
5. **Stale warning** — If inputs change after assessment but before/after scoring: inline banner "Inputs have changed since last assessment. Re-run analysis for an accurate score." with re-run button

### Layout

Dedicated section between BaselineSummary and MeasuresTable. Always visible once triggered (not collapsible). Compact horizontal card:
- Left: circular score gauge
- Right: score context (percentile text, target EUI, median EUI)

### Data Flow

- Receives `building` (BuildingInput), `baseline` (BaselineResult), and `address` (string | null) as props from `AssessmentView`
- On button click, calls `POST /energy-star/score` with those props
- Stores result in local component state
- Stale detection: watches for input changes after last assessment timestamp

### Stale State Handling

`AssessmentView` tracks when the last assessment was run. If the user modifies building inputs after the assessment completes (but before or after requesting the ENERGY STAR score), the component shows a warning with a button to re-run the assessment. The ENERGY STAR score endpoint is never called with stale data — the UI prevents it.

## Out of Scope

- **Persistence** — no saving scores to DB (SQLite effort in progress separately)
- **Post-upgrade scoring** — Phase 2: let users select upgrade measures and see how score changes
- **User ESPM accounts** — Phase 2: let users connect their own ESPM credentials
- **Full property creation** — Phase 2: push buildings to ESPM portfolio for ongoing tracking
- **CRUD for buildings/assessments** — separate effort

## Testing

- Unit tests for building type mapping
- Unit tests for XML construction (verify generated XML matches expected structure)
- Unit tests for response parsing (mock ESPM responses)
- Integration test hitting the ESPM test environment (behind `--run-e2e` flag)
- Frontend component tests for state transitions
