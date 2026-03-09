# Bill Savings Fix & Frontend Redesign

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Use superpowers:frontend-design for all frontend tasks.

**Goal:** Fix incorrect bill savings/payback calculations caused by unclamped negative XGB predictions, then redesign the frontend dashboard using the @partnerdevops/partner-components library.

**Architecture:** Backend fix clamps per-fuel EUI predictions to >= 0 before computing bill savings (XGBoost can predict negative values which inflates savings). Frontend redesign replaces generic Tailwind with Partner component library (PTable, PBadge, PButton, PLayout, PTypography) and adds annual bill savings ($), installed cost, and payback columns to the measures table.

**Tech Stack:** Python/FastAPI (backend), Vue 3 + TypeScript + @partnerdevops/partner-components (frontend)

---

## Phase 1: Backend — Fix Bill Savings Calculation

### Task 1: Write failing test for negative EUI clamping

**Files:**
- Create: `backend/tests/test_assessment_bill_savings.py`

**Step 1: Write the failing test**

```python
"""Tests for bill savings calculation in the assessment pipeline."""

import pytest
from unittest.mock import MagicMock, patch
from app.services.assessment import _assess_single
from app.schemas.request import BuildingInput


def _make_mocks(baseline_eui, post_eui, rates, sizing=None):
    """Create mock ModelManager and CostCalculator."""
    mm = MagicMock()
    mm.predict_baseline.return_value = baseline_eui
    mm.predict_sizing.return_value = sizing or {
        "heating_capacity": 100, "cooling_capacity": 50,
        "wall_area": 1000, "roof_area": 500, "window_area": 200,
    }
    mm.predict_rates.return_value = rates
    mm.get_available_upgrades.return_value = [1]
    mm.predict_upgrade.return_value = post_eui

    cc = MagicMock()
    cc._comstock = {}
    cc._resstock = {}
    cc.calculate_cost.return_value = MagicMock(
        installed_cost_per_sf=5.0, installed_cost_total=50000.0,
        cost_range={"low": 40000, "high": 60000},
        useful_life_years=20, regional_factor=1.0, confidence="medium",
    )
    return mm, cc


@pytest.fixture
def office_building():
    return BuildingInput(
        building_type="Office", sqft=10000, num_stories=2, zipcode="20001",
    )


@patch("app.services.assessment._check_applicability", return_value=True)
def test_negative_post_eui_clamped_to_zero(mock_app, office_building):
    """XGB may predict negative post-upgrade EUI; savings must not be inflated."""
    baseline = {"electricity": 10.0, "natural_gas": 8.0, "fuel_oil": 0.0, "propane": 0.0}
    # Negative natural_gas = XGB artifact; should be treated as 0, not inflate savings
    post = {"electricity": 15.0, "natural_gas": -3.0, "fuel_oil": 0.0, "propane": 0.0}
    rates = {"electricity": 0.12, "natural_gas": 0.04, "fuel_oil": 0.0, "propane": 0.0}

    mm, cc = _make_mocks(baseline, post, rates)
    result = _assess_single(office_building, 0, mm, cc)

    measure = next(m for m in result.measures if m.upgrade_id == 1)
    # With clamping: elec savings = 10 - 15 = -5 * 0.12 = -0.60
    #                gas savings  = 8 - 0 = 8 * 0.04 = 0.32  (post clamped from -3 to 0)
    #                total = -0.28
    # Without clamping: gas savings = 8 - (-3) = 11 * 0.04 = 0.44 (WRONG — inflated)
    # Bill savings should be -0.28 (net cost increase, no payback)
    assert measure.utility_bill_savings_per_sf is not None
    assert measure.utility_bill_savings_per_sf < 0  # net cost increase
    assert measure.simple_payback_years is None  # no payback when savings <= 0


@patch("app.services.assessment._check_applicability", return_value=True)
def test_negative_baseline_eui_clamped_to_zero(mock_app, office_building):
    """Negative baseline EUI (XGB artifact) should not create phantom savings."""
    baseline = {"electricity": 10.0, "natural_gas": -2.0, "fuel_oil": 0.0, "propane": 0.0}
    post = {"electricity": 8.0, "natural_gas": 0.0, "fuel_oil": 0.0, "propane": 0.0}
    rates = {"electricity": 0.12, "natural_gas": 0.04, "fuel_oil": 0.0, "propane": 0.0}

    mm, cc = _make_mocks(baseline, post, rates)
    result = _assess_single(office_building, 0, mm, cc)

    measure = next(m for m in result.measures if m.upgrade_id == 1)
    # Baseline gas clamped to 0, post gas = 0 → gas savings = 0
    # Elec savings = 10 - 8 = 2 * 0.12 = 0.24
    assert measure.utility_bill_savings_per_sf == pytest.approx(0.24, abs=0.01)


@patch("app.services.assessment._check_applicability", return_value=True)
def test_normal_bill_savings_calculation(mock_app, office_building):
    """Happy path: positive EUIs produce correct bill savings."""
    baseline = {"electricity": 10.0, "natural_gas": 8.0, "fuel_oil": 0.0, "propane": 0.0}
    post = {"electricity": 7.0, "natural_gas": 5.0, "fuel_oil": 0.0, "propane": 0.0}
    rates = {"electricity": 0.12, "natural_gas": 0.04, "fuel_oil": 0.0, "propane": 0.0}

    mm, cc = _make_mocks(baseline, post, rates)
    result = _assess_single(office_building, 0, mm, cc)

    measure = next(m for m in result.measures if m.upgrade_id == 1)
    # elec: (10-7) * 0.12 = 0.36, gas: (8-5) * 0.04 = 0.12, total = 0.48
    assert measure.utility_bill_savings_per_sf == pytest.approx(0.48, abs=0.01)
    # payback = 5.0 / 0.48 = ~10.4 years
    assert measure.simple_payback_years == pytest.approx(10.4, abs=0.5)
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_assessment_bill_savings.py -v`
Expected: `test_negative_post_eui_clamped_to_zero` FAILS (savings inflated, not negative)

**Step 3: Commit test**

```bash
git add backend/tests/test_assessment_bill_savings.py
git commit -m "test: add failing tests for negative EUI clamping in bill savings"
```

---

### Task 2: Fix EUI clamping in assessment.py

**Files:**
- Modify: `backend/app/services/assessment.py:112,136,158-163`

**Step 1: Apply the fix**

In `_assess_single`, make these changes:

1. **Line 136** — Clamp post_kbtu like baseline_kbtu:
```python
# Before:
post_kbtu = {fuel: eui * KWH_TO_KBTU for fuel, eui in post_eui.items()}

# After:
post_kbtu = {fuel: max(0.0, eui * KWH_TO_KBTU) for fuel, eui in post_eui.items()}
```

2. **Lines 158-163** — Clamp per-fuel kWh before computing bill savings:
```python
# Before:
bill_savings_per_sf = 0.0
for fuel in baseline_eui:
    energy_saved_kwh = baseline_eui.get(fuel, 0) - post_eui.get(fuel, 0)
    rate = rates.get(fuel, 0)
    bill_savings_per_sf += energy_saved_kwh * rate

# After:
bill_savings_per_sf = 0.0
for fuel in baseline_eui:
    baseline_kwh = max(0.0, baseline_eui.get(fuel, 0))
    post_kwh = max(0.0, post_eui.get(fuel, 0))
    energy_saved_kwh = baseline_kwh - post_kwh
    rate = rates.get(fuel, 0)
    bill_savings_per_sf += energy_saved_kwh * rate
```

**Step 2: Run the bill savings tests**

Run: `cd backend && pytest tests/test_assessment_bill_savings.py -v`
Expected: All 3 tests PASS

**Step 3: Run full test suite**

Run: `cd backend && pytest`
Expected: All 69+ tests PASS

**Step 4: Commit fix**

```bash
git add backend/app/services/assessment.py
git commit -m "fix: clamp negative XGB EUI predictions to zero in bill savings calculation"
```

---

## Phase 2: Frontend Redesign with Partner Components

> **REQUIRED:** Use superpowers:frontend-design skill for all frontend tasks below.

### Task 3: Verify partner-components installation and imports

**Files:**
- Check: `frontend/package.json` (already has `@partnerdevops/partner-components`)
- Check: `frontend/node_modules/@partnerdevops/partner-components/`

**Step 1: Verify the dependency resolves**

Run: `cd frontend && npm ls @partnerdevops/partner-components`
Expected: Shows the installed version (0.0.15)

**Step 2: Verify import works**

Check that the partner-components index exports match what we need. Key imports:
```typescript
import {
  PButton,
  PBadge,
  PTable, PTableHead, PTableHeader, PTableBody, PTableRow, PTableCell,
  PTypography,
  PTextInput,
  PNumericInput,
  PChip,
  PTooltip,
  PIcon,
} from '@partnerdevops/partner-components'
```

---

### Task 4: Redesign BaselineSummary component

**Files:**
- Modify: `frontend/src/components/BaselineSummary.vue`

**Step 1: Rewrite BaselineSummary using Partner components**

Replace the entire file with a design that uses PTypography for text, and a card-based fuel breakdown with PBadge for non-zero fuels. Show total EUI prominently with fuel breakdown cards below.

Key design requirements:
- Large hero number for total EUI using PTypography variant="h1"
- Grid of fuel cards (only show fuels with > 0 kBtu/sf)
- Use PBadge for fuel type labels
- Use Partner design tokens for colors (CSS custom properties)
- Pass `sqft` prop (from parent) to show total annual energy (kBtu/sf × sqft)

**Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: No TypeScript or build errors

**Step 3: Commit**

```bash
git add frontend/src/components/BaselineSummary.vue
git commit -m "refactor: redesign BaselineSummary with partner-components"
```

---

### Task 5: Redesign MeasuresTable with new columns

**Files:**
- Modify: `frontend/src/components/MeasuresTable.vue`
- Modify: `frontend/src/types/assessment.ts` (add `sqft` to props if needed)

**Step 1: Rewrite MeasuresTable using PTable system**

Key design requirements:
- Use PTable, PTableHead, PTableHeader (with sortable), PTableBody, PTableRow, PTableCell
- Columns: Measure Name, Category (PBadge), Savings %, Annual Bill Savings ($/yr), Installed Cost ($), Payback (yrs)
- **Annual Bill Savings**: `utility_bill_savings_per_sf * sqft` (needs sqft prop from parent)
- **Installed Cost**: `cost.installed_cost_total` (already available)
- **Payback**: `simple_payback_years` with color coding (green < 5yr, yellow 5-15yr, red > 15yr)
- Sort by payback ascending by default (best payback first)
- Use PBadge for category badges
- Use PChip for confidence level on cost
- Non-applicable measures collapsed in an expandable section or hidden with a toggle
- Format currency with Intl.NumberFormat

**Step 2: Update AssessmentView to pass sqft**

The MeasuresTable needs `sqft` to compute annual bill savings from per-sf values. Pass it from AssessmentView.

**Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: No errors

**Step 4: Commit**

```bash
git add frontend/src/components/MeasuresTable.vue frontend/src/views/AssessmentView.vue
git commit -m "refactor: redesign MeasuresTable with partner-components, add cost/payback columns"
```

---

### Task 6: Redesign BuildingForm with Partner form components

**Files:**
- Modify: `frontend/src/components/BuildingForm.vue`
- Modify: `frontend/src/components/AdvancedDetails.vue`

**Step 1: Rewrite BuildingForm using Partner form components**

Key design requirements:
- Use PTextInput for text fields (zipcode)
- Use PNumericInput for numeric fields (sqft, num_stories, year_built)
- Use PButton variant="primary" for submit
- Use Partner typography and spacing
- Keep the same form logic (reactive, emit submit)
- Select dropdowns: partner-components doesn't have a PSelect, so keep native `<select>` styled with Partner CSS tokens
- Use PTypography for section headings

**Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: No errors

**Step 3: Commit**

```bash
git add frontend/src/components/BuildingForm.vue frontend/src/components/AdvancedDetails.vue
git commit -m "refactor: redesign BuildingForm with partner-components"
```

---

### Task 7: Redesign AssessmentView layout

**Files:**
- Modify: `frontend/src/views/AssessmentView.vue`

**Step 1: Update AssessmentView**

Key design requirements:
- Use Partner design tokens for the page layout
- Add input summary section using PBadge/PChip for climate zone, cluster, state
- Pass `sqft` down to MeasuresTable
- Error state uses PBadge variant="error"
- Loading state with Partner-styled spinner
- Clean section separation between baseline and measures

**Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: No errors

**Step 3: Commit**

```bash
git add frontend/src/views/AssessmentView.vue
git commit -m "refactor: redesign AssessmentView layout with partner-components"
```

---

### Task 8: Final build verification and visual QA

**Step 1: Full build**

Run: `cd frontend && npm run build`
Expected: Clean build with no errors

**Step 2: Type check**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: No type errors

**Step 3: Commit all remaining changes**

```bash
git add -A
git commit -m "chore: frontend redesign complete with partner-components"
```
