# Sticky Table & Description Expand Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the measures table header and left two columns (Measure, Category) sticky during scroll, add description text truncation with per-row and expand-all toggle controls, matching the SL Heaven asset planner table pattern.

**Architecture:** Pure CSS sticky positioning on the existing PTable component structure. No partner-components library changes — all done via scoped CSS overrides with code comments noting the deviation. Description expand state managed via a `Set<number>` for per-row tracking and a boolean for expand-all, with smooth height transitions.

**Tech Stack:** Vue 3 Composition API, scoped CSS, PIcon (Carbon `chevron-right`/`chevron-down` icons), existing partner-components PTable

---

### Task 1: Add Sticky Table Container, Header, and Left Columns

**Files:**
- Modify: `frontend/src/components/MeasuresTable.vue` (CSS + minor template class additions)

**Context:** The table wrapper currently has `overflow-x: auto`. We need both axes scrollable in the same container for sticky to work on both dimensions. The SL Heaven asset planner uses `max-height: 75vh; overflow-y: auto; overflow-x: scroll; position: relative`. Sticky columns use `background-color: inherit` (no different background) with a subtle `border-right` divider on the last sticky column (Category). Z-index layering: body sticky cells (3), header cells (10), header+sticky intersection (11).

**Step 1: Update the table wrapper CSS**

In `frontend/src/components/MeasuresTable.vue`, replace the `.measures-table-wrapper` CSS rule:

```css
/* OLD */
.measures-table-wrapper {
  overflow-x: auto;
}
```

with:

```css
/*
 * NOTE: Sticky columns and sticky header are implemented via scoped CSS here
 * because the partner-components PTable does not yet support sticky/pinned columns.
 * When integrating into the main application (SL Heaven), these overrides should
 * be migrated to the partner-components library as proper PTable props/features.
 * Reference: SL Heaven AssetPlanner table pattern.
 */
.measures-table-wrapper {
  max-height: 75vh;
  overflow-y: auto;
  overflow-x: scroll;
  position: relative;
}
```

**Step 2: Add sticky header CSS**

Add after the `.measures-table` rule:

```css
/* ---- Sticky header ---- */
.measures-table :deep(thead) {
  position: sticky;
  top: 0;
  z-index: 10;
  background-color: inherit;
}
```

**Step 3: Add sticky left column CSS for header cells**

Replace the existing `.measures-th--name` and `.measures-th--category` rules with:

```css
.measures-th--name {
  min-width: 220px;
  position: sticky;
  left: 0;
  z-index: 11;
  background-color: inherit;
}

.measures-th--category {
  min-width: 120px;
  position: sticky;
  left: 220px;
  z-index: 11;
  background-color: inherit;
  border-right: 1px solid var(--partner-border-divider, #e2e8f0);
}
```

**Step 4: Add sticky left column CSS for body cells**

Replace the existing `.measures-cell--name` rule with:

```css
.measures-cell--name {
  font-weight: 500;
  color: var(--partner-text-primary, #333e47);
  min-width: 220px;
  position: sticky;
  left: 0;
  z-index: 3;
  background-color: inherit;
}
```

Add a new rule for the category body cell (we need a new class):

```css
.measures-cell--category {
  min-width: 120px;
  position: sticky;
  left: 220px;
  z-index: 3;
  background-color: inherit;
  border-right: 1px solid var(--partner-border-divider, #e2e8f0);
}
```

**Step 5: Add the `measures-cell--category` class to category body cells**

In the template, for both applicable and non-applicable rows, change the Category `<PTableCell>`:

Applicable rows (currently line 265):
```html
<!-- OLD -->
<PTableCell class="measures-cell">
<!-- NEW -->
<PTableCell class="measures-cell measures-cell--category">
```

Non-applicable rows (currently line 368):
```html
<!-- OLD -->
<PTableCell class="measures-cell">
<!-- NEW -->
<PTableCell class="measures-cell measures-cell--category">
```

**Step 6: Ensure striped row backgrounds propagate to sticky cells**

The striped rows use `background: var(--app-surface)` which is set on the `<tr>`. For sticky cells to pick this up via `inherit`, we need the row background to actually be on the row element. The existing `.measures-row--striped` already does this. For non-striped rows, we need an explicit background so `inherit` has something to inherit:

Add to the `.measures-table` CSS:

```css
.measures-table :deep(tbody tr) {
  background-color: var(--app-surface-raised, white);
}
```

**Step 7: Run type check and visually verify**

Run: `cd frontend && npx vue-tsc -b`
Expected: Only pre-existing BaselineSummary errors

Run: `cd frontend && npx vite build`
Expected: Build succeeds

**Step 8: Commit**

```bash
git add frontend/src/components/MeasuresTable.vue
git commit -m "feat: add sticky header and sticky left columns to measures table"
```

---

### Task 2: Add Description Expand/Collapse State and Truncation Logic

**Files:**
- Modify: `frontend/src/components/MeasuresTable.vue` (script section)

**Context:** We need two expand mechanisms: a global toggle (all rows) and per-row toggles. State is a `Set<number>` of expanded upgrade_ids plus a boolean for expand-all. Text truncation uses a helper function (~90 chars max) matching the SL Heaven pattern.

**Step 1: Add expand state and helpers to the script section**

After the `// ---- Payback color ----` section (after line 165), add:

```typescript
// ---- Description expand/collapse ----

const DESC_TRUNCATE_LENGTH = 90

const allDescExpanded = ref(false)
const expandedDescIds = ref(new Set<number>())

function isDescExpanded(upgradeId: number): boolean {
  return allDescExpanded.value || expandedDescIds.value.has(upgradeId)
}

function toggleDescRow(upgradeId: number) {
  const ids = new Set(expandedDescIds.value)
  if (ids.has(upgradeId)) {
    ids.delete(upgradeId)
    // If we were in expand-all mode and user collapses one, exit expand-all
    allDescExpanded.value = false
  } else {
    ids.add(upgradeId)
  }
  expandedDescIds.value = ids
}

function toggleDescAll() {
  allDescExpanded.value = !allDescExpanded.value
  // Clear individual overrides when toggling global
  expandedDescIds.value = new Set()
}

function truncateText(text: string | undefined | null, maxLength: number): string {
  if (!text) return '\u2014'
  if (text.length <= maxLength) return text
  return text.substring(0, maxLength) + '...'
}
```

**Step 2: Add PIcon import**

Update the import from partner-components (line 3-14) to include PIcon:

```typescript
import {
  PTable,
  PTableHeader,
  PTableHead,
  PTableBody,
  PTableRow,
  PTableCell,
  PBadge,
  PButton,
  PTypography,
  PTooltip,
  PIcon,
} from '@partnerdevops/partner-components'
```

**Step 3: Run type check**

Run: `cd frontend && npx vue-tsc -b`
Expected: Only pre-existing errors

**Step 4: Commit**

```bash
git add frontend/src/components/MeasuresTable.vue
git commit -m "feat: add description expand/collapse state and text truncation helpers"
```

---

### Task 3: Update Description Column Header with Expand-All Toggle

**Files:**
- Modify: `frontend/src/components/MeasuresTable.vue` (template + CSS)

**Context:** Replace the static "Description" header text with a clickable header containing a chevron icon that toggles all descriptions.

**Step 1: Replace the Description header**

Replace the Description `<PTableHead>` (currently line 250-252):

```html
<!-- OLD -->
<PTableHead class="measures-th measures-th--desc">
  Description
</PTableHead>
```

with:

```html
<PTableHead class="measures-th measures-th--desc">
  <span class="measures-desc-toggle" @click="toggleDescAll">
    <PIcon
      :name="allDescExpanded ? 'chevron-down' : 'chevron-right'"
      size="small"
      class="measures-desc-toggle__icon"
    />
    Description
  </span>
</PTableHead>
```

**Step 2: Add CSS for the header toggle**

Add to the `<style scoped>` section:

```css
/* ---- Description expand toggle ---- */
.measures-desc-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  cursor: pointer;
  user-select: none;
}

.measures-desc-toggle:hover {
  color: var(--partner-text-primary, #333e47);
}

.measures-desc-toggle__icon {
  transition: transform 0.2s ease;
  flex-shrink: 0;
}
```

**Step 3: Run type check**

Run: `cd frontend && npx vue-tsc -b`
Expected: Only pre-existing errors

**Step 4: Commit**

```bash
git add frontend/src/components/MeasuresTable.vue
git commit -m "feat: add expand-all chevron toggle to description column header"
```

---

### Task 4: Update Description Cells with Per-Row Toggle and Truncation

**Files:**
- Modify: `frontend/src/components/MeasuresTable.vue` (template + CSS)

**Context:** Each description cell gets a small chevron before the text. Collapsed: truncated to 90 chars with "...". Expanded: full text. Row height hugs content naturally with smooth transition. Both applicable and non-applicable rows need this treatment.

**Step 1: Replace the applicable row description cell**

Replace the description cell in applicable rows (currently lines 332-337):

```html
<!-- OLD -->
<PTableCell class="measures-cell measures-cell--desc">
  <PTypography variant="body2" component="span">
    {{ m.description ?? '\u2014' }}
  </PTypography>
</PTableCell>
```

with:

```html
<!-- Description -->
<PTableCell class="measures-cell measures-cell--desc">
  <div class="measures-desc-content" v-if="m.description">
    <PIcon
      :name="isDescExpanded(m.upgrade_id) ? 'chevron-down' : 'chevron-right'"
      size="small"
      class="measures-desc-row-icon"
      @click="toggleDescRow(m.upgrade_id)"
    />
    <PTypography variant="body2" component="span">
      {{ isDescExpanded(m.upgrade_id) ? m.description : truncateText(m.description, DESC_TRUNCATE_LENGTH) }}
    </PTypography>
  </div>
  <PTypography v-else variant="body2" component="span">&#8212;</PTypography>
</PTableCell>
```

**Step 2: Replace the non-applicable row description cell**

Replace the description cell in non-applicable rows (currently lines 401-405):

```html
<!-- OLD -->
<PTableCell class="measures-cell measures-cell--desc">
  <PTypography variant="body2" component="span">
    {{ m.description ?? '\u2014' }}
  </PTypography>
</PTableCell>
```

with:

```html
<PTableCell class="measures-cell measures-cell--desc">
  <div class="measures-desc-content" v-if="m.description">
    <PIcon
      :name="isDescExpanded(m.upgrade_id) ? 'chevron-down' : 'chevron-right'"
      size="small"
      class="measures-desc-row-icon"
      @click="toggleDescRow(m.upgrade_id)"
    />
    <PTypography variant="body2" component="span">
      {{ isDescExpanded(m.upgrade_id) ? m.description : truncateText(m.description, DESC_TRUNCATE_LENGTH) }}
    </PTypography>
  </div>
  <PTypography v-else variant="body2" component="span">&#8212;</PTypography>
</PTableCell>
```

**Step 3: Update the description cell CSS**

Replace the existing `.measures-th--desc` and `.measures-cell--desc` rules with:

```css
.measures-th--desc {
  min-width: 280px;
}

.measures-cell--desc {
  min-width: 280px;
  max-width: 400px;
  white-space: normal;
  line-height: 1.4;
}

.measures-desc-content {
  display: flex;
  align-items: flex-start;
  gap: 0.25rem;
}

.measures-desc-row-icon {
  flex-shrink: 0;
  cursor: pointer;
  margin-top: 0.125rem;
  transition: transform 0.2s ease;
}

.measures-desc-row-icon:hover {
  color: var(--partner-text-primary, #333e47);
}
```

**Step 4: Run type check and build**

Run: `cd frontend && npx vue-tsc -b`
Expected: Only pre-existing errors

Run: `cd frontend && npx vite build`
Expected: Build succeeds

**Step 5: Commit**

```bash
git add frontend/src/components/MeasuresTable.vue
git commit -m "feat: add per-row description expand/collapse with chevron toggles"
```

---

### Task 5: Non-Applicable Table Sticky Alignment and Final Polish

**Files:**
- Modify: `frontend/src/components/MeasuresTable.vue` (template + CSS)

**Context:** The non-applicable measures table is a separate `<PTable>` inside a collapsible section. It needs matching sticky columns so they align visually with the main table above. It also needs the same wrapper treatment.

**Step 1: Update the non-applicable table wrapper**

The non-applicable table wrapper (currently line 355) uses `measures-table-wrapper` class. This will inherit the `max-height: 75vh` from the main wrapper, which is too much for a secondary table. Add a modifier:

Replace:
```html
<div v-if="showNonApplicable" class="measures-table-wrapper measures-nonapplicable__table">
```
with:
```html
<div v-if="showNonApplicable" class="measures-table-wrapper measures-nonapplicable__table measures-table-wrapper--secondary">
```

Add CSS:
```css
.measures-table-wrapper--secondary {
  max-height: 40vh;
}
```

**Step 2: Run type check and build**

Run: `cd frontend && npx vue-tsc -b`
Expected: Only pre-existing errors

Run: `cd frontend && npx vite build`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add frontend/src/components/MeasuresTable.vue
git commit -m "feat: align non-applicable table sticky columns and finalize polish"
```
