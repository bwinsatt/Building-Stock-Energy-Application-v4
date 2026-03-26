# Measure Selection Conflict UX Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Align package/individual measure selection behavior with the intended UX, using corrected package constituent mappings and a revised immediate-replace notification flow instead of a confirmation dialog.

**Architecture:** Keep the existing `useMeasureSelections` composable as the single source of truth for selection state and conflict handling. Correct the backend-provided package constituent metadata, revise the design/spec documents to reflect the approved UX change, and update the frontend notification behavior and styling so the touched surfaces use Partner components and tokens.

**Tech Stack:** Python/FastAPI, SQLite, Vue 3 Composition API, Partner Components library, Partner CSS token system

---

## Scope Decisions

- In scope:
  - Correct ComStock package constituent mappings that drive conflict detection.
  - Preserve `Package -> Individual` lockout.
  - Change `Individual -> Package` behavior to immediate replacement with a lightweight inline notification.
  - Use Partner tokens/components for the notification and any new touched UI styling.
  - Add regression coverage for mapping and conflict behavior.

- Out of scope:
  - Migrating or backfilling old saved assessment rows in SQLite.
  - Broad cleanup of existing hardcoded table styling unrelated to this UX.
  - Adding undo in this pass.
  - Adding a global toast system.

## Behavior To Implement

### Final UX Contract

1. If a user selects a package first:
   - The package is selected.
   - Its constituent individual measures become disabled/grayed out.
   - Hover/focus tooltip reads `Included in [Package Name]`.

2. If a user selects one or more individual measures first, then selects a package containing them:
   - The package remains selectable.
   - The overlapping individual measures are immediately deselected.
   - The package becomes selected in the same action.
   - A lightweight inline notification appears near the measures table header explaining what was replaced.
   - No confirmation step.

3. Saved historical assessments:
   - No data migration in this task.
   - New behavior is guaranteed for new assessments and any saved assessments already carrying correct `constituent_upgrade_ids`.

### UX Copy

- Disabled individual tooltip:
  - `Included in [Package Name]`

- Immediate-replace notification:
  - Singular:
    - `[Measure Name] was deselected because it is included in [Package Name].`
  - Plural:
    - `[Measure A], [Measure B], and [Measure C] were deselected because they are included in [Package Name].`

- Notification behavior:
  - Auto-dismiss after 4 seconds.
  - Replaced by the latest package-selection event.
  - No stacking.

Recommendation: keep this as an inline notification banner inside `MeasuresTable.vue`, not a toast. That matches the current UI architecture and avoids introducing new infrastructure.

---

### Task 1: Update Design Docs To Match Approved UX

**Files:**
- Modify: `docs/superpowers/specs/2026-03-22-measure-selection-projected-score-design.md`
- Modify: `docs/superpowers/plans/2026-03-22-measure-selection-projected-score.md`
- Create: `docs/superpowers/plans/2026-03-25-measure-selection-conflict-ux.md`

**Step 1: Update the spec language**

Revise the selection-rules section so it says:

- `Package -> Individual lockout` stays unchanged.
- `Individual -> Package conflict` becomes immediate replacement with inline notification.
- Remove all references to confirmation dialog / on-confirm replacement.

**Step 2: Update the older implementation plan**

Change the 2026-03-22 plan to reflect:

- no confirmation dialog
- package rows remain selectable
- composable performs immediate replacement
- view displays notification copy based on returned metadata

**Step 3: Cross-link the revised plan**

Add a short note at the top of the 2026-03-22 plan referencing this 2026-03-25 plan as the superseding UX decision for conflict handling.

**Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-03-22-measure-selection-projected-score-design.md docs/superpowers/plans/2026-03-22-measure-selection-projected-score.md docs/superpowers/plans/2026-03-25-measure-selection-conflict-ux.md
git commit -m "docs: revise measure selection conflict UX to immediate replace"
```

---

### Task 2: Correct Package Constituent Mappings At The Source

**Files:**
- Modify: `backend/app/inference/applicability.py`
- Modify: `backend/tests/test_applicability.py`

**Step 1: Strengthen the failing backend test**

Replace the current weak structural assertions with exact constituent assertions for the known ComStock packages:

```python
from app.inference.applicability import PACKAGE_CONSTITUENTS


def test_package_constituents_match_comstock_package_definitions():
    assert PACKAGE_CONSTITUENTS[54] == [48, 49, 52]
    assert PACKAGE_CONSTITUENTS[55] == [43, 1, 15]
    assert PACKAGE_CONSTITUENTS[56] == [43, 4]
    assert PACKAGE_CONSTITUENTS[57] == [48, 49, 52, 43, 1, 15]
    assert PACKAGE_CONSTITUENTS[58] == [1, 15, 19, 20, 21]
    assert PACKAGE_CONSTITUENTS[59] == [28, 29, 30]
    assert PACKAGE_CONSTITUENTS[63] == [48, 49, 52, 28]
    assert PACKAGE_CONSTITUENTS[64] == [48, 49, 52, 28, 43]
    assert PACKAGE_CONSTITUENTS[65] == [46, 49]
```

**Step 2: Run the targeted test to verify it fails**

Run:

```bash
cd backend && pytest tests/test_applicability.py::test_package_constituents_match_comstock_package_definitions -v
```

Expected: FAIL on package `54` and missing `65`.

**Step 3: Fix the mapping**

In `backend/app/inference/applicability.py`, update `PACKAGE_CONSTITUENTS` to:

```python
PACKAGE_CONSTITUENTS: dict[int, list[int]] = {
    54: [48, 49, 52],
    55: [43, 1, 15],
    56: [43, 4],
    57: [48, 49, 52, 43, 1, 15],
    58: [1, 15, 19, 20, 21],
    59: [28, 29, 30],
    63: [48, 49, 52, 28],
    64: [48, 49, 52, 28, 43],
    65: [46, 49],
}
```

**Step 4: Run backend tests**

Run:

```bash
cd backend && pytest tests/test_applicability.py tests/test_integration_pipeline.py::test_package_measures_have_constituent_ids -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/inference/applicability.py backend/tests/test_applicability.py
git commit -m "fix: correct package constituent mappings for measure conflicts"
```

---

### Task 3: Make Conflict Metadata Explicit In The Frontend Composable

**Files:**
- Modify: `frontend/src/composables/useMeasureSelections.js`

**Step 1: Add a focused test harness or pure helper extraction**

Recommendation: extract the conflict-resolution branch into a small pure helper within the composable module or a sibling utility module so it can be unit-tested without mounting the whole view.

Suggested helper signature:

```javascript
export function resolveMeasureToggle({
  selectedUpgradeIds,
  packageConstituentMap,
  disabledByPackage,
  upgradeId,
}) {
  // returns next ids + metadata
}
```

**Step 2: Write failing tests for the helper**

Cases:

- package selected first disables individuals indirectly through `disabledByPackage`
- individual selected first then package selected:
  - overlapping individuals removed immediately
  - package added
  - return metadata includes package id and overlapping ids
- package with no overlap acts as normal select
- clicking disabled individual returns no-op

If frontend test wiring is not added in this task, document these as manual verification cases and test the pure helper with a one-off temporary script during implementation.

**Step 3: Normalize the return contract**

Revise `toggleMeasure()` so it returns richer metadata:

```javascript
{
  action: 'selected' | 'deselected' | 'replaced'
  packageId?: number
  replacedIds?: number[]
}
```

Use `replaced` rather than `replace` to describe a completed action.

**Step 4: Keep persistence behavior unchanged**

Do not add confirm-state buffering. Keep the optimistic single-click flow.

**Step 5: Commit**

```bash
git add frontend/src/composables/useMeasureSelections.js
git commit -m "refactor: return explicit replacement metadata from measure selection logic"
```

---

### Task 4: Replace The Ad-Hoc Message With A Partner-Styled Inline Notification

**Files:**
- Modify: `frontend/src/components/MeasuresTable.vue`
- Modify: `frontend/src/views/AssessmentView.vue`
- Modify: `frontend/src/components/SavedAssessmentView.vue`

**Step 1: Define the notification shape in parent views**

Replace the current raw string `replaceMessage` with a structured object:

```javascript
const replacementNotice = ref(null)
// { packageName: string, replacedNames: string[] }
```

**Step 2: Build copy in the parent**

When `toggleMeasure()` returns `action: 'replaced'`, resolve:

- package display name
- replaced individual display names

Generate singular/plural copy in the parent view and pass a structured prop or final string to `MeasuresTable`.

**Step 3: Render the notice in `MeasuresTable.vue` using Partner primitives**

Use existing Partner primitives already in scope:

- `PIcon` for info indicator
- `PTypography` for body copy
- optional `PButton` with `variant="neutral"` and `appearance="text"` only if a manual dismiss affordance is desired

Do not introduce a custom browser alert or confirm.

**Step 4: Use Partner tokens for styling**

For the inline notification:

- background: `var(--partner-blue-1)`
- text: `var(--partner-blue-7)` or `var(--partner-text-primary)` depending on contrast
- border: `1px solid var(--partner-blue-3)` or `border-top` if preserving current placement
- radius if boxed: `var(--partner-radius-sm)` or `var(--partner-radius-md)` based on surrounding table/card treatment

Avoid hardcoded values for:

- border radius
- action colors
- notification fill/border/text

**Step 5: Preserve the existing placement unless usability demands otherwise**

Recommendation: keep the notice just below the measures header and above the section toggles. This is already where users’ eyes are after interacting with checkboxes.

**Step 6: Commit**

```bash
git add frontend/src/components/MeasuresTable.vue frontend/src/views/AssessmentView.vue frontend/src/components/SavedAssessmentView.vue
git commit -m "feat: add partner-styled replacement notice for package conflicts"
```

---

### Task 5: Bring Touched Styling Back To Partner Tokens

**Files:**
- Modify: `frontend/src/components/MeasuresTable.vue`

**Step 1: Limit styling cleanup to touched conflict UX surfaces**

Normalize only the styles touched by this work:

- replacement notice
- any new dismiss control
- any new message spacing/layout

Do not broaden into a full table restyle.

**Step 2: Replace any new hardcoded radii/colors with Partner tokens**

Use:

- `var(--partner-radius-sm)` for button/input-like edges
- `var(--partner-radius-md)` for small card/banner containers
- `var(--partner-border-light)` / `var(--partner-border-default)`
- `var(--partner-background-gray)` / `var(--partner-blue-1)`
- `var(--partner-text-primary)` / `var(--partner-text-secondary)`

**Step 3: Leave existing unrelated hardcoded table values alone unless directly touched**

Document remaining debt in a brief code comment or PR note rather than expanding scope.

**Step 4: Commit**

```bash
git add frontend/src/components/MeasuresTable.vue
git commit -m "style: align measure conflict notification with partner tokens"
```

---

### Task 6: Add Minimal Frontend Verification Coverage

**Files:**
- Create: `frontend/vitest.config.js`
- Modify: `frontend/package.json`
- Create: `frontend/src/composables/useMeasureSelections.test.js`

**Step 1: Add frontend test runner scripts**

Since `frontend/` has no app-level test script today, add:

```json
"test": "vitest run",
"test:watch": "vitest"
```

If needed, add a minimal `vitest.config.js` for jsdom or node-based tests depending on helper extraction choice.

**Step 2: Add targeted tests for conflict behavior**

At minimum:

- `selecting package after roof insulation immediately replaces roof insulation`
- `selecting package first causes constituent individual ids to be treated as disabled`
- `package 12 conflict removes roof insulation when PV+Roof package selected`

If using a pure helper, keep tests at helper level. Avoid over-mounting Vue components.

**Step 3: Run the tests**

Run:

```bash
cd frontend && npm test
```

Expected: PASS

**Step 4: Commit**

```bash
git add frontend/package.json frontend/vitest.config.js frontend/src/composables/useMeasureSelections.test.js
git commit -m "test: cover package and individual measure conflict behavior"
```

---

### Task 7: Manual Verification On New Assessments

**Files:**
- No code changes

**Step 1: Build and run the frontend**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS

Then run:

```bash
cd frontend && npm run dev
```

**Step 2: Verify `Package -> Individual` lockout**

With a fresh ComStock assessment:

1. Select `Package 1, Wall + Roof Insulation + New Windows`
2. Verify `Wall Insulation`, `Roof Insulation`, and `New Windows` are disabled/grayed
3. Verify tooltip says `Included in Package 1, Wall + Roof Insulation + New Windows`

**Step 3: Verify `Individual -> Package` immediate replacement**

1. Select `Roof Insulation`
2. Select `Package 1, Wall + Roof Insulation + New Windows`
3. Verify `Roof Insulation` becomes deselected immediately
4. Verify package becomes selected
5. Verify inline replacement notice appears with correct copy

**Step 4: Verify package 12 edge case**

1. Select `Roof Insulation`
2. Select `Package 12, Photovoltaics with 40pct Roof Coverage + Roof Insulation`
3. Verify `Roof Insulation` is deselected
4. Verify package 12 is selected
5. Verify replacement notice is correct

**Step 5: Verify saved-project expectations**

Open an older saved assessment and note whether lockout works. If not, document that this is expected for stale saved payloads and that a re-assessment refreshes the data.

---

## Notes For Implementation

- The current spec and plan still mention confirmation dialog behavior. Update docs before implementation so the code is not “wrong” relative to stale docs.
- The app currently has no dedicated toast component. An inline Partner-styled notice is the lowest-risk path and fits the existing architecture.
- Do not add undo in this pass. It complicates persistence and state rollback. Treat it as a separate enhancement once the base interaction is correct and verified.

## Recommended Follow-Up (Separate Decision)

If you later want undo, implement it as a short-lived inline action that restores the previous selection set entirely from a captured pre-toggle snapshot. Do not partially reconstruct overlap state heuristically.

## Execution Order

1. Update docs to reflect approved UX.
2. Fix backend package mappings.
3. Refactor frontend toggle metadata.
4. Add Partner-styled replacement notice.
5. Add targeted tests.
6. Run manual verification on fresh assessments.

Plan complete and saved to `docs/superpowers/plans/2026-03-25-measure-selection-conflict-ux.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
