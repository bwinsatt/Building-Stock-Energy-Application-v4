# Assessment Persistence Wiring — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the assessment pipeline to the SQLite persistence layer with autosave — assessments automatically persist to a selected project after running, and saved results render fully in ProjectDetail.

**Architecture:** Add a project selector to AssessmentView that enables autosave. On assessment success, auto-create a building record (with lookup/map data) and save the assessment result. Backend returns assessments nested inside buildings when fetching a project. ProjectDetail renders saved results using the existing BaselineSummary, MeasuresTable, and EnergyStarScore components. A dedicated SavedAssessmentView component handles the full read-only rendering of a saved assessment.

**Tech Stack:** Vue 3 Composition API, TypeScript, FastAPI, SQLite, existing partner-components library

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `backend/app/services/database.py` | Add `lookup_data` column to buildings, include assessments in get_project response |
| Modify | `backend/app/api/projects.py` | Add GET building endpoint, accept `lookup_data` in CreateBuildingRequest |
| Modify | `frontend/src/types/projects.ts` | Add `assessments` to Building type, add `lookup_data` field (using `LookupResponse`) |
| Modify | `frontend/src/composables/useProjects.ts` | Add `fetchBuilding` method, error handling on fetch calls |
| Create | `frontend/src/components/ProjectSelector.vue` | Dropdown to select/create a project for autosave |
| Modify | `frontend/src/views/AssessmentView.vue` | Add ProjectSelector, autosave on assessment success |
| Modify | `frontend/src/components/BuildingForm.vue` | Emit `lookup-complete` from `watch(lookupResult)` watcher |
| Modify | `frontend/src/components/ProjectDetail.vue` | Render assessment history per building, link to full view |
| Create | `frontend/src/components/SavedAssessmentView.vue` | Full read-only view of a saved assessment (baseline, measures, ENERGY STAR, map) |
| Modify | `frontend/src/components/ProjectsView.vue` | Handle navigation to saved assessment view |

---

### Task 1: Backend — Include assessments in project response & add lookup_data

**Files:**
- Modify: `backend/app/services/database.py:76-87` (get_project) and `database.py:21-47` (init)
- Modify: `backend/app/api/projects.py:12-15` (CreateBuildingRequest)
- Test: `backend/tests/test_database.py` (if exists, or create)

- [ ] **Step 1: Add lookup_data column to buildings schema**

In `database.py`, update the `init()` method's CREATE TABLE for buildings to include `lookup_data JSON`. Also add an ALTER TABLE migration fallback so existing databases get the column:

```python
# In init(), after the CREATE TABLE statements, add:
try:
    conn.execute("ALTER TABLE buildings ADD COLUMN lookup_data JSON")
except sqlite3.OperationalError:
    pass  # Column already exists
```

- [ ] **Step 2: Update create_building to accept and store lookup_data**

In `database.py`, update `create_building`:

```python
def create_building(
    self, project_id: int, address: str,
    building_input: dict, utility_data: dict | None = None,
    lookup_data: dict | None = None,
) -> dict:
    with self._connect() as conn:
        cursor = conn.execute(
            "INSERT INTO buildings (project_id, address, building_input, utility_data, lookup_data) VALUES (?, ?, ?, ?, ?)",
            (project_id, address, json.dumps(building_input),
             json.dumps(utility_data) if utility_data else None,
             json.dumps(lookup_data) if lookup_data else None),
        )
        return self._row_to_dict(
            conn.execute("SELECT * FROM buildings WHERE id = ?", (cursor.lastrowid,)).fetchone()
        )
```

Update `_row_to_dict` to also parse `lookup_data`:

```python
for key in ("building_input", "utility_data", "result", "lookup_data"):
```

- [ ] **Step 3: Update get_project to nest assessments inside each building**

In `database.py`, update `get_project`:

```python
def get_project(self, project_id: int) -> dict | None:
    with self._connect() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if row is None:
            return None
        project = self._row_to_dict(row)
        buildings = conn.execute(
            "SELECT * FROM buildings WHERE project_id = ? ORDER BY created_at",
            (project_id,),
        ).fetchall()
        project["buildings"] = []
        for b in buildings:
            building = self._row_to_dict(b)
            assessments = conn.execute(
                "SELECT * FROM assessments WHERE building_id = ? ORDER BY created_at DESC",
                (building["id"],),
            ).fetchall()
            building["assessments"] = [self._row_to_dict(a) for a in assessments]
            project["buildings"].append(building)
        return project
```

- [ ] **Step 4: Update CreateBuildingRequest to accept lookup_data**

In `projects.py`:

```python
class CreateBuildingRequest(BaseModel):
    address: str
    building_input: dict
    utility_data: dict | None = None
    lookup_data: dict | None = None
```

And update `create_building` endpoint to pass it through:

```python
return request.app.state.database.create_building(
    project_id=project_id,
    address=req.address,
    building_input=req.building_input,
    utility_data=req.utility_data,
    lookup_data=req.lookup_data,
)
```

- [ ] **Step 5: Add get_building method to Database class**

In `database.py`, add a proper `get_building` method (avoids accessing private `_connect` from the route handler):

```python
def get_building(self, project_id: int, building_id: int) -> dict | None:
    with self._connect() as conn:
        row = conn.execute(
            "SELECT * FROM buildings WHERE id = ? AND project_id = ?",
            (building_id, project_id),
        ).fetchone()
        if row is None:
            return None
        building = self._row_to_dict(row)
        assessments = conn.execute(
            "SELECT * FROM assessments WHERE building_id = ? ORDER BY created_at DESC",
            (building_id,),
        ).fetchall()
        building["assessments"] = [self._row_to_dict(a) for a in assessments]
        return building
```

- [ ] **Step 6: Add GET endpoint for single building in projects.py**

In `projects.py`:

```python
@router.get("/{project_id}/buildings/{building_id}")
def get_building(project_id: int, building_id: int, request: Request):
    building = request.app.state.database.get_building(project_id, building_id)
    if building is None:
        raise HTTPException(status_code=404, detail="Building not found")
    return building
```

- [ ] **Step 7: Run backend tests**

Run: `cd backend && pytest tests/ -v`
Expected: All existing tests pass. The schema migration is additive-only.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/database.py backend/app/api/projects.py
git commit -m "feat: include assessments in project response, add lookup_data to buildings"
```

---

### Task 2: Frontend types — Update project types for assessments and lookup_data

**Files:**
- Modify: `frontend/src/types/projects.ts`
- Modify: `frontend/src/composables/useProjects.ts`

- [ ] **Step 1: Update Building and Assessment types**

In `types/projects.ts`, import `LookupResponse` and use it for `lookup_data` (the full LookupResponse is stored, not a subset):

```typescript
import type { LookupResponse } from './lookup'

export interface Building {
  id: number
  project_id: number
  address: string
  building_input: Record<string, unknown>
  utility_data: Record<string, unknown> | null
  lookup_data: LookupResponse | null
  assessments?: Assessment[]
  created_at: string
  updated_at: string
}

export interface Assessment {
  id: number
  building_id: number
  result: Record<string, unknown>
  calibrated: boolean
  created_at: string
}
```

- [ ] **Step 2: Add createBuilding lookup_data parameter and fetchBuilding to useProjects**

In `useProjects.ts`, update `createBuilding` to accept `lookupData` and add `resp.ok` checks:

```typescript
async function createBuilding(
  projectId: number, address: string,
  buildingInput: Record<string, unknown>,
  utilityData?: Record<string, unknown>,
  lookupData?: Record<string, unknown>,
) {
  const resp = await fetch(`${API_BASE}/projects/${projectId}/buildings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      address,
      building_input: buildingInput,
      utility_data: utilityData,
      lookup_data: lookupData,
    }),
  })
  if (!resp.ok) throw new Error('Failed to create building')
  return await resp.json()
}
```

Add `fetchBuilding`:

```typescript
async function fetchBuilding(projectId: number, buildingId: number) {
  const resp = await fetch(`${API_BASE}/projects/${projectId}/buildings/${buildingId}`)
  if (!resp.ok) throw new Error('Building not found')
  return await resp.json()
}
```

Also add `resp.ok` checks to the existing `saveAssessment` method:

```typescript
async function saveAssessment(
  projectId: number, buildingId: number,
  result: Record<string, unknown>, calibrated: boolean,
) {
  const resp = await fetch(
    `${API_BASE}/projects/${projectId}/buildings/${buildingId}/assessments`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ result, calibrated }),
    },
  )
  if (!resp.ok) throw new Error('Failed to save assessment')
  return await resp.json()
}
```

Return `fetchBuilding` from the composable.

- [ ] **Step 3: Run type check**

Run: `cd frontend && npm run type-check`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/projects.ts frontend/src/composables/useProjects.ts
git commit -m "feat: add lookup_data and assessments to project types"
```

---

### Task 3: ProjectSelector component — pick/create a project for autosave

**Files:**
- Create: `frontend/src/components/ProjectSelector.vue`

- [ ] **Step 1: Create ProjectSelector component**

This is a compact inline component that shows at the top of AssessmentView. It has:
- A dropdown of existing projects (fetched on mount)
- A "New Project" option that shows an inline text input
- Emits the selected project id

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useProjects } from '../composables/useProjects'

const emit = defineEmits<{
  'update:projectId': [id: number | null]
}>()

const { projects, fetchProjects, createProject } = useProjects()
const selectedId = ref<number | null>(null)
const creatingNew = ref(false)
const newName = ref('')

onMounted(() => {
  fetchProjects()
})

function onSelect(event: Event) {
  const val = (event.target as HTMLSelectElement).value
  if (val === '__new__') {
    creatingNew.value = true
    selectedId.value = null
    emit('update:projectId', null)
  } else if (val) {
    selectedId.value = Number(val)
    creatingNew.value = false
    emit('update:projectId', selectedId.value)
  } else {
    selectedId.value = null
    creatingNew.value = false
    emit('update:projectId', null)
  }
}

async function onCreateProject() {
  if (!newName.value.trim()) return
  const project = await createProject(newName.value.trim())
  selectedId.value = project.id
  creatingNew.value = false
  newName.value = ''
  emit('update:projectId', project.id)
}
</script>

<template>
  <div class="project-selector">
    <label class="project-selector__label">Save to Project</label>
    <div class="project-selector__row">
      <select
        class="project-selector__select"
        :value="creatingNew ? '__new__' : (selectedId ?? '')"
        @change="onSelect"
      >
        <option value="">None (don't save)</option>
        <option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option>
        <option value="__new__">+ New Project...</option>
      </select>
      <div v-if="creatingNew" class="project-selector__new">
        <input
          v-model="newName"
          class="project-selector__input"
          placeholder="Project name"
          @keyup.enter="onCreateProject"
        />
        <button class="project-selector__create-btn" @click="onCreateProject" :disabled="!newName.trim()">
          Create
        </button>
      </div>
    </div>
  </div>
</template>
```

Style it as a compact inline bar (matching the form aesthetics).

- [ ] **Step 2: Verify it renders**

Run: `cd frontend && npm run type-check`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ProjectSelector.vue
git commit -m "feat: add ProjectSelector component for autosave target"
```

---

### Task 4: AssessmentView autosave — save on assessment success

**Files:**
- Modify: `frontend/src/views/AssessmentView.vue`
- Modify: `frontend/src/components/BuildingForm.vue` (emit lookup data)

- [ ] **Step 1: Expose lookup result from BuildingForm**

BuildingForm currently holds the `lookupResult` internally via the `useAddressLookup` composable. The result arrives asynchronously and is consumed by the existing `watch(lookupResult, ...)` watcher at line 87 of BuildingForm.vue. We need to emit it so AssessmentView can store it for autosave.

In `BuildingForm.vue`, update the emits (line 22-24):
```typescript
const emit = defineEmits<{
  submit: [payload: BuildingInput]
  'lookup-complete': [result: LookupResponse | null, address: string]
}>()
```

Add `LookupResponse` to the imports from `'../types/lookup'` (line 4 already imports `FieldResult`).

Inside the existing `watch(lookupResult, (result) => { ... })` watcher (line 87), add the emit **at the end** of the watcher callback, after all form fields are populated:
```typescript
// At the end of the watch(lookupResult) callback:
emit('lookup-complete', result, result.address)
```

Note: use `result.address` (the geocoded/canonical address from the API), not the raw user input.

- [ ] **Step 2: Wire autosave into AssessmentView**

In `AssessmentView.vue`:

```vue
<script setup lang="ts">
import { ref, watch } from 'vue'
import { useAssessment } from '../composables/useAssessment'
import { useProjects } from '../composables/useProjects'
import ProjectSelector from '../components/ProjectSelector.vue'
import BuildingForm from '../components/BuildingForm.vue'
import BaselineSummary from '../components/BaselineSummary.vue'
import MeasuresTable from '../components/MeasuresTable.vue'
import AssumptionsPanel from '../components/AssumptionsPanel.vue'
import EnergyStarScore from '../components/EnergyStarScore.vue'
import type { BuildingInput } from '../types/assessment'
import type { LookupResponse } from '../types/lookup'

const { loading, error, result, assess } = useAssessment()
const { createBuilding, saveAssessment } = useProjects()

const lastSqft = ref(0)
const lastBuilding = ref<BuildingInput | null>(null)
const selectedProjectId = ref<number | null>(null)
const lastLookupResult = ref<LookupResponse | null>(null)
const lastAddress = ref('')
const saveStatus = ref<'idle' | 'saving' | 'saved' | 'error'>('idle')

function onLookupComplete(lookupResult: LookupResponse | null, address: string) {
  lastLookupResult.value = lookupResult
  lastAddress.value = address
}

function onSubmit(input: BuildingInput) {
  lastSqft.value = input.sqft
  lastBuilding.value = input
  saveStatus.value = 'idle'
  assess(input)
}

// Autosave: watch for assessment result and save when project is selected
watch(result, async (newResult) => {
  if (!newResult || !selectedProjectId.value || !lastBuilding.value) return
  saveStatus.value = 'saving'
  try {
    const building = await createBuilding(
      selectedProjectId.value,
      lastAddress.value || lastBuilding.value.zipcode,
      lastBuilding.value as unknown as Record<string, unknown>,
      undefined, // utility_data
      lastLookupResult.value as unknown as Record<string, unknown>,
    )
    await saveAssessment(
      selectedProjectId.value,
      building.id,
      newResult as unknown as Record<string, unknown>,
      newResult.calibrated ?? false,
    )
    saveStatus.value = 'saved'
  } catch {
    saveStatus.value = 'error'
  }
})
</script>
```

In the template, add the ProjectSelector above the form and a save indicator near the results divider:

```vue
<ProjectSelector v-model:project-id="selectedProjectId" />

<!-- After the results divider -->
<span v-if="saveStatus === 'saving'" class="save-indicator">Saving...</span>
<span v-else-if="saveStatus === 'saved'" class="save-indicator save-indicator--success">Saved to project</span>
<span v-else-if="saveStatus === 'error'" class="save-indicator save-indicator--error">Save failed</span>
```

- [ ] **Step 3: Run type check and dev server**

Run: `cd frontend && npm run type-check`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/AssessmentView.vue frontend/src/components/BuildingForm.vue frontend/src/components/ProjectSelector.vue
git commit -m "feat: autosave assessment results to selected project"
```

---

### Task 5: ProjectDetail — render saved assessments inline

**Files:**
- Modify: `frontend/src/components/ProjectDetail.vue`

- [ ] **Step 1: Update ProjectDetail to show assessment list per building**

Replace the placeholder "No assessments saved" section with actual assessment rendering. When a building is expanded, show a list of its assessments with date and calibrated badge. Each assessment is clickable to open the full view.

```vue
<!-- In the expanded building section, replace the placeholder -->
<div v-if="expandedBuildingId === building.id" class="assessment-section">
  <template v-if="building.assessments && building.assessments.length > 0">
    <div
      v-for="assessment in building.assessments"
      :key="assessment.id"
      class="assessment-row"
      @click="emit('view-assessment', building, assessment)"
    >
      <div class="assessment-row__info">
        <span class="assessment-row__date">{{ formatDate(assessment.created_at) }}</span>
        <span v-if="assessment.calibrated" class="calibrated-badge">Calibrated</span>
        <span v-if="assessment.result?.baseline" class="assessment-row__eui">
          {{ (assessment.result.baseline as any)?.total_eui_kbtu_sf?.toFixed(1) }} kBtu/sf
        </span>
      </div>
      <span class="assessment-row__arrow">&#x25B8;</span>
    </div>
  </template>
  <p v-else class="assessment-empty">No assessments saved for this building yet.</p>
</div>
```

Add the emit:
```typescript
const emit = defineEmits<{
  back: []
  'view-assessment': [building: Building, assessment: Assessment]
}>()
```

Add `Assessment` to the import from `../types/projects`.

- [ ] **Step 2: Add styles for assessment rows**

```css
.assessment-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 0.75rem;
  cursor: pointer;
  border-radius: 0.375rem;
  transition: background 0.1s;
}
.assessment-row:hover { background: #e2e8f0; }
.assessment-row__info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.assessment-row__date {
  font-size: 0.8125rem;
  color: #333e47;
  font-weight: 500;
}
.assessment-row__eui {
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  color: #64748b;
}
.calibrated-badge {
  display: inline-flex;
  align-items: center;
  background: #dcfce7;
  color: #166534;
  font-size: 0.6875rem;
  font-weight: 500;
  padding: 0.0625rem 0.375rem;
  border-radius: 9999px;
}
.assessment-row__arrow {
  color: #94a3b8;
  font-size: 0.75rem;
}
```

- [ ] **Step 3: Run type check**

Run: `cd frontend && npm run type-check`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ProjectDetail.vue
git commit -m "feat: render assessment history in ProjectDetail building list"
```

---

### Task 6: SavedAssessmentView — full read-only view of a saved assessment

**Files:**
- Create: `frontend/src/components/SavedAssessmentView.vue`

- [ ] **Step 1: Create SavedAssessmentView**

This component accepts a `Building` and `Assessment` and renders the full results using existing components. It extracts the typed data from the `result` JSON blob.

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { PTypography } from '@partnerdevops/partner-components'
import BaselineSummary from './BaselineSummary.vue'
import MeasuresTable from './MeasuresTable.vue'
import AssumptionsPanel from './AssumptionsPanel.vue'
import EnergyStarScore from './EnergyStarScore.vue'
import BuildingMapViewer from './BuildingMapViewer.vue'
import type { Building, Assessment } from '../types/projects'
import type { BuildingResult, BuildingInput, BaselineResult, MeasureResult, InputSummary } from '../types/assessment'

const props = defineProps<{
  building: Building
  assessment: Assessment
}>()

const emit = defineEmits<{ back: [] }>()

const buildingResult = computed<BuildingResult | null>(() => {
  return (props.assessment.result as unknown as BuildingResult) ?? null
})

const buildingInput = computed<BuildingInput>(() => {
  return props.building.building_input as unknown as BuildingInput
})

const sqft = computed(() => buildingInput.value?.sqft ?? 0)

const baseline = computed<BaselineResult | null>(() => buildingResult.value?.baseline ?? null)
const measures = computed<MeasureResult[]>(() => buildingResult.value?.measures ?? [])
const inputSummary = computed<InputSummary | null>(() => buildingResult.value?.input_summary ?? null)
const calibrated = computed(() => props.assessment.calibrated)

// Map data from lookup_data stored on the building
const lookupData = computed(() => props.building.lookup_data)
</script>

<template>
  <div class="saved-assessment">
    <button class="back-btn" @click="emit('back')">&larr; Back to Project</button>

    <div class="saved-assessment__header">
      <PTypography variant="h4">{{ building.address }}</PTypography>
      <span class="saved-assessment__date">
        Assessment from {{ new Date(assessment.created_at).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }) }}
      </span>
    </div>

    <!-- Map -->
    <BuildingMapViewer
      v-if="lookupData?.target_building_polygon"
      :lat="lookupData.lat"
      :lon="lookupData.lon"
      :target-polygon="lookupData.target_building_polygon"
      :nearby-buildings="lookupData.nearby_buildings"
      :num-stories="Number(buildingInput?.num_stories ?? 1)"
    />

    <!-- Results -->
    <template v-if="buildingResult && baseline">
      <AssumptionsPanel v-if="inputSummary" :summary="inputSummary" />
      <BaselineSummary :baseline="baseline" :sqft="sqft" :calibrated="calibrated" />
      <EnergyStarScore
        :building="buildingInput"
        :baseline="baseline"
        :address="building.address"
      />
      <div class="section-separator" aria-hidden="true" />
      <MeasuresTable :measures="measures" :sqft="sqft" />
    </template>

    <div v-else class="empty-state">
      <p>Assessment data could not be loaded.</p>
    </div>
  </div>
</template>

<style scoped>
.saved-assessment {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}
.back-btn {
  align-self: flex-start;
  background: transparent;
  border: none;
  color: #005199;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  padding: 0;
}
.back-btn:hover { opacity: 0.75; }
.saved-assessment__header {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.saved-assessment__date {
  font-size: 0.8125rem;
  color: #64748b;
}
.section-separator {
  height: 1px;
  background: #e2e8f0;
  margin: 0.25rem 0;
}
.empty-state {
  text-align: center;
  padding: 2rem;
  color: #94a3b8;
}
</style>
```

- [ ] **Step 2: Run type check**

Run: `cd frontend && npm run type-check`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/SavedAssessmentView.vue
git commit -m "feat: add SavedAssessmentView for rendering persisted assessment results"
```

---

### Task 7: Navigation wiring — ProjectsView handles view-assessment routing

**Files:**
- Modify: `frontend/src/components/ProjectsView.vue`

- [ ] **Step 1: Read current ProjectsView to understand navigation state**

ProjectsView currently manages a `selectedProjectId` ref and toggles between the project list and ProjectDetail. Add a third state for viewing a saved assessment.

- [ ] **Step 2: Add saved assessment view state**

Add state for the selected building/assessment and wire the `view-assessment` event from ProjectDetail to show SavedAssessmentView:

```typescript
import SavedAssessmentView from './SavedAssessmentView.vue'
import type { Building, Assessment } from '../types/projects'

const viewingAssessment = ref<{ building: Building; assessment: Assessment } | null>(null)

function onViewAssessment(building: Building, assessment: Assessment) {
  viewingAssessment.value = { building, assessment }
}

function onBackFromAssessment() {
  viewingAssessment.value = null
}
```

In the template, add a third conditional:

```vue
<SavedAssessmentView
  v-if="viewingAssessment"
  :building="viewingAssessment.building"
  :assessment="viewingAssessment.assessment"
  @back="onBackFromAssessment"
/>
<ProjectDetail
  v-else-if="selectedProjectId"
  :project-id="selectedProjectId"
  @back="selectedProjectId = null"
  @view-assessment="onViewAssessment"
/>
<!-- else: project list -->
```

- [ ] **Step 3: Run type check and verify navigation flow**

Run: `cd frontend && npm run type-check`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ProjectsView.vue
git commit -m "feat: wire ProjectsView navigation to SavedAssessmentView"
```

---

### Task 8: Manual integration test

- [ ] **Step 1: Start backend and frontend**

```bash
cd backend && uvicorn app.main:app --reload &
cd frontend && npm run dev &
```

- [ ] **Step 2: Test autosave flow**

1. Go to Energy Audit Lite tab
2. Select "+ New Project..." in the project selector, create "Test Project"
3. Enter an address, fill out form, submit assessment
4. Verify "Saved to project" indicator appears after results load
5. Switch to Projects tab
6. Open "Test Project" — verify the building appears with an assessment row
7. Click the assessment row — verify full results render (baseline, measures, map if lookup was done)
8. Click "Back to Project" — verify navigation returns to project detail

- [ ] **Step 3: Test no-project flow**

1. Set project selector to "None (don't save)"
2. Run an assessment
3. Verify results display normally with no save attempt

- [ ] **Step 4: Commit any fixes**

```bash
git add -u
git commit -m "fix: integration test fixes for assessment persistence"
```
