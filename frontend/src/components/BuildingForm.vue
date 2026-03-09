<script setup lang="ts">
import { reactive, ref, watch, computed } from 'vue'
import type { BuildingInput } from '../types/assessment'
import type { FieldResult } from '../types/lookup'
import {
  BUILDING_TYPES,
  HEATING_FUELS,
  DHW_FUELS,
  getHvacCategoriesForDataset,
  getHvacCategoryForValue,
} from '../config/dropdowns'
import { PTextInput, PNumericInput, PButton, PTypography } from '@partnerdevops/partner-components'
import AdvancedDetails from './AdvancedDetails.vue'
import AddressLookup from './AddressLookup.vue'
import BuildingMapViewer from './BuildingMapViewer.vue'
import { useAddressLookup } from '../composables/useAddressLookup'

defineProps<{
  disabled?: boolean
}>()

const emit = defineEmits<{
  submit: [payload: BuildingInput]
}>()

const form = reactive<BuildingInput>({
  building_type: '',
  sqft: 0,
  num_stories: 1,
  zipcode: '',
  year_built: undefined as unknown as number,
})

const advancedFields = ref<Partial<BuildingInput>>({})
const hvacCategory = ref('')

const availableHvacCategories = computed(() => getHvacCategoriesForDataset(form.building_type))

watch(hvacCategory, (newCat) => {
  if (!newCat) {
    form.hvac_system_type = undefined
    return
  }
  const cat = availableHvacCategories.value.find(c => c.key === newCat)
  if (cat) {
    form.hvac_system_type = cat.defaultVariant
  }
})

watch(() => form.building_type, () => {
  const validKeys = availableHvacCategories.value.map(c => c.key)
  if (hvacCategory.value && !validKeys.includes(hvacCategory.value)) {
    hvacCategory.value = ''
  }
})

const { loading: lookupLoading, error: lookupError, lookupResult, lookup } = useAddressLookup()

// Track which fields were auto-filled and their source
const fieldSources = ref<Record<string, FieldResult>>({})

function onAddressLookup(address: string) {
  lookup(address)
}

// When lookup completes, populate form fields
watch(lookupResult, (result) => {
  if (!result) return

  populatingFromLookup.value = true

  const fields = result.building_fields
  fieldSources.value = {}

  // Zipcode
  if (result.zipcode) {
    form.zipcode = result.zipcode
  }

  // Direct field mapping
  const fieldMap: Record<string, keyof typeof form> = {
    building_type: 'building_type',
    sqft: 'sqft',
    num_stories: 'num_stories',
    year_built: 'year_built',
    heating_fuel: 'heating_fuel',
    dhw_fuel: 'dhw_fuel',
    hvac_system_type: 'hvac_system_type',
  }

  for (const [lookupKey, formKey] of Object.entries(fieldMap)) {
    const field = fields[lookupKey]
    if (field?.value != null) {
      if (lookupKey === 'hvac_system_type') {
        // Reverse-map to category
        const cat = getHvacCategoryForValue(String(field.value))
        if (cat) {
          hvacCategory.value = cat.key
          // form.hvac_system_type will be set by the hvacCategory watcher
        }
      } else {
        ;(form as any)[formKey] = field.value
      }
      fieldSources.value[lookupKey] = field
    }
  }

  // Advanced fields
  const advancedMap: Record<string, string> = {
    wall_construction: 'wall_construction',
    window_type: 'window_type',
    window_to_wall_ratio: 'window_to_wall_ratio',
    lighting_type: 'lighting_type',
  }

  for (const [lookupKey, advKey] of Object.entries(advancedMap)) {
    const field = fields[lookupKey]
    if (field?.value != null) {
      advancedFields.value[advKey as keyof typeof advancedFields.value] = field.value as any
      fieldSources.value[lookupKey] = field
    }
  }

  // Allow watchers to fire normally after this tick
  setTimeout(() => { populatingFromLookup.value = false }, 0)
})

// Clear source badge when user manually changes a field
const populatingFromLookup = ref(false)

const formFieldKeys: Record<string, string> = {
  building_type: 'building_type',
  sqft: 'sqft',
  num_stories: 'num_stories',
  year_built: 'year_built',
  heating_fuel: 'heating_fuel',
  dhw_fuel: 'dhw_fuel',
}

for (const [lookupKey, formKey] of Object.entries(formFieldKeys)) {
  watch(() => (form as any)[formKey], () => {
    if (!populatingFromLookup.value) {
      delete fieldSources.value[lookupKey]
    }
  })
}

watch(hvacCategory, () => {
  if (!populatingFromLookup.value) {
    delete fieldSources.value['hvac_system_type']
  }
})

// Also clear source badges when advanced fields change manually
const advancedFieldKeys = ['wall_construction', 'window_type', 'window_to_wall_ratio', 'lighting_type', 'operating_hours', 'hvac_heating_efficiency', 'hvac_cooling_efficiency', 'water_heater_efficiency', 'insulation_wall', 'infiltration']
watch(advancedFields, (newVal, oldVal) => {
  if (populatingFromLookup.value) return
  for (const key of advancedFieldKeys) {
    const k = key as keyof typeof newVal
    if (newVal[k] !== oldVal?.[k]) {
      delete fieldSources.value[key]
    }
  }
}, { deep: true })

const validationError = ref<string | null>(null)

function onSubmit() {
  validationError.value = null

  const requiredChecks: { field: string; label: string; value: unknown }[] = [
    { field: 'building_type', label: 'Building Type', value: form.building_type },
    { field: 'sqft', label: 'Square Footage', value: form.sqft },
    { field: 'num_stories', label: 'Number of Stories', value: form.num_stories },
    { field: 'zipcode', label: 'Zip Code', value: form.zipcode },
    { field: 'year_built', label: 'Year Built', value: form.year_built },
  ]

  const missing = requiredChecks.filter(
    (c) => c.value === undefined || c.value === null || c.value === '' || c.value === 0,
  )
  if (missing.length > 0) {
    validationError.value = `Please fill out: ${missing.map((m) => m.label).join(', ')}`
    return
  }

  const merged = {
    ...form,
    ...advancedFields.value,
  }
  // Strip empty strings, undefined, and fields that were auto-imputed by the
  // address lookup so the backend re-imputes them and populates imputed_details
  // for the Assumptions panel.
  const payload = Object.fromEntries(
    Object.entries(merged).filter(([key, v]) => {
      if (v === undefined || v === '') return false
      const src = fieldSources.value[key]
      if (src && src.source === 'imputed') return false
      return true
    }),
  ) as unknown as BuildingInput
  emit('submit', payload)
}
</script>

<template>
  <form
    class="form-card"
    @submit.prevent="onSubmit"
  >
    <!-- Address Lookup -->
    <AddressLookup
      :loading="lookupLoading"
      :error="lookupError"
      @lookup="onAddressLookup"
    />

    <!-- Map Viewer (shown after successful lookup) -->
    <BuildingMapViewer
      v-if="lookupResult?.target_building_polygon"
      :lat="lookupResult.lat"
      :lon="lookupResult.lon"
      :target-polygon="lookupResult.target_building_polygon"
      :nearby-buildings="lookupResult.nearby_buildings"
      :num-stories="Number(lookupResult.building_fields.num_stories?.value ?? 1)"
    />

    <!-- Section: Required Fields -->
    <div class="form-section">
      <PTypography variant="h5" component="h2" class="form-section__title">
        Building Information
      </PTypography>
      <p class="form-section__desc">Required parameters for baseline energy analysis</p>
    </div>

    <div class="form-grid">
      <!-- Building Type -->
      <div class="form-field">
        <label class="form-label" for="building-type">
          Building Type <span class="form-label__required">*</span>
          <span v-if="fieldSources['building_type']" class="field-badge" :class="'field-badge--' + fieldSources['building_type'].source">
            {{ fieldSources['building_type'].source === 'osm' ? 'public records' : 'estimated' }}
          </span>
        </label>
        <select
          id="building-type"
          v-model="form.building_type"
          required
          class="form-select"
        >
          <option value="" disabled>-- Select --</option>
          <option v-for="bt in BUILDING_TYPES" :key="bt" :value="bt">{{ bt }}</option>
        </select>
      </div>

      <!-- Square Footage -->
      <div class="form-field">
        <label class="form-label" for="sqft">
          Square Footage <span class="form-label__required">*</span>
          <span v-if="fieldSources['sqft']" class="field-badge" :class="'field-badge--' + fieldSources['sqft'].source">
            {{ fieldSources['sqft'].source === 'osm' ? 'public records' : 'estimated' }}
          </span>
        </label>
        <PNumericInput
          id="sqft"
          v-model="form.sqft"
          :min="1"
          :step="100"
          required
          size="medium"
        />
      </div>

      <!-- Number of Stories -->
      <div class="form-field">
        <label class="form-label" for="num-stories">
          Number of Stories <span class="form-label__required">*</span>
          <span v-if="fieldSources['num_stories']" class="field-badge" :class="'field-badge--' + fieldSources['num_stories'].source">
            {{ fieldSources['num_stories'].source === 'osm' ? 'public records' : 'estimated' }}
          </span>
        </label>
        <PNumericInput
          id="num-stories"
          v-model="form.num_stories"
          :min="1"
          :max="200"
          :step="1"
          required
          size="medium"
        />
      </div>

      <!-- Zip Code -->
      <PTextInput
        v-model="form.zipcode"
        label="Zip Code"
        placeholder="e.g. 10001"
        required
        size="medium"
        maxlength="5"
      />

      <!-- Year Built -->
      <div class="form-field">
        <label class="form-label" for="year-built">
          Year Built <span class="form-label__required">*</span>
          <span v-if="fieldSources['year_built']" class="field-badge" :class="'field-badge--' + fieldSources['year_built'].source">
            {{ fieldSources['year_built'].source === 'osm' ? 'public records' : 'estimated' }}
          </span>
        </label>
        <PNumericInput
          id="year-built"
          v-model="form.year_built"
          :min="1800"
          :max="2030"
          required
          size="medium"
          :format-options="{ useGrouping: false }"
        />
      </div>
    </div>

    <!-- Section: Optional Details -->
    <div class="form-section form-section--optional">
      <PTypography variant="h6" component="h3" class="form-section__title">
        Optional Details
      </PTypography>
      <p class="form-section__desc">Improve prediction accuracy with additional building data</p>
    </div>

    <div class="form-grid">
      <!-- Heating Fuel -->
      <div class="form-field">
        <label class="form-label" for="heating-fuel">
          Heating Fuel
          <span v-if="fieldSources['heating_fuel']" class="field-badge" :class="'field-badge--' + fieldSources['heating_fuel'].source">
            {{ fieldSources['heating_fuel'].source === 'osm' ? 'public records' : 'estimated' }}
          </span>
        </label>
        <select
          id="heating-fuel"
          v-model="form.heating_fuel"
          class="form-select"
        >
          <option value="">-- Select --</option>
          <option v-for="fuel in HEATING_FUELS" :key="fuel" :value="fuel">{{ fuel }}</option>
        </select>
      </div>

      <!-- DHW Fuel -->
      <div class="form-field">
        <label class="form-label" for="dhw-fuel">
          DHW Fuel
          <span v-if="fieldSources['dhw_fuel']" class="field-badge" :class="'field-badge--' + fieldSources['dhw_fuel'].source">
            {{ fieldSources['dhw_fuel'].source === 'osm' ? 'public records' : 'estimated' }}
          </span>
        </label>
        <select
          id="dhw-fuel"
          v-model="form.dhw_fuel"
          class="form-select"
        >
          <option value="">-- Select --</option>
          <option v-for="fuel in DHW_FUELS" :key="fuel" :value="fuel">{{ fuel }}</option>
        </select>
      </div>

      <!-- HVAC Type -->
      <div class="form-field">
        <label class="form-label" for="hvac-system">
          HVAC Type
          <span v-if="fieldSources['hvac_system_type']" class="field-badge" :class="'field-badge--' + fieldSources['hvac_system_type'].source">
            {{ fieldSources['hvac_system_type'].source === 'osm' ? 'public records' : 'estimated' }}
          </span>
        </label>
        <select
          id="hvac-system"
          v-model="hvacCategory"
          class="form-select"
        >
          <option value="">-- Select --</option>
          <option v-for="cat in availableHvacCategories" :key="cat.key" :value="cat.key">{{ cat.label }}</option>
        </select>
      </div>
    </div>

    <!-- Advanced Details -->
    <AdvancedDetails
      v-model="advancedFields"
      :hvac-category="hvacCategory"
      :building-type="form.building_type"
      @update:hvac-variant="(v: string) => form.hvac_system_type = v"
    />

    <!-- Submit -->
    <div class="form-actions">
      <p v-if="validationError" class="form-validation-error">{{ validationError }}</p>
      <PButton
        type="submit"
        variant="primary"
        size="large"
        :disabled="disabled"
      >
        Run Assessment
      </PButton>
    </div>
  </form>
</template>

<style scoped>
.form-card {
  background-color: var(--app-surface-raised);
  border: 1px solid #e2e6ea;
  border-radius: 6px;
  padding: 2rem;
}

@media (min-width: 768px) {
  .form-card {
    padding: 2.5rem;
  }
}

/* Section headers */
.form-section {
  margin-bottom: 1.25rem;
}

.form-section--optional {
  margin-top: 2.5rem;
  padding-top: 2rem;
  border-top: 1px solid #e2e6ea;
}

.form-section__title {
  font-family: var(--font-display);
  color: var(--app-header-bg);
  letter-spacing: -0.01em;
  margin: 0;
}

.form-section__desc {
  font-family: var(--font-display);
  font-size: 0.75rem;
  color: #6b7a8a;
  letter-spacing: 0.01em;
  margin: 0.25rem 0 0;
}

/* Grid layout */
.form-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem 1.5rem;
}

@media (min-width: 768px) {
  .form-grid {
    grid-template-columns: 1fr 1fr;
  }
}

/* Field wrapper for native selects */
.form-field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

/* Labels styled to match Partner PLabel / inputLabel */
.form-label {
  font-family: var(--font-display);
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--partner-text-secondary, #5f6d79);
  line-height: 1.25rem;
}

.form-label__required {
  color: var(--partner-error-main, #dc2626);
}

/* Native select styled to match Partner input styling */
.form-select {
  display: flex;
  width: 100%;
  height: 2rem; /* matches medium size h-8 */
  border-radius: 2px; /* rounded-sm */
  border: 1px solid var(--partner-border-default, #c4cdd5);
  background-color: transparent;
  padding: 0 2rem 0 0.75rem;
  font-family: inherit;
  font-size: 0.875rem;
  line-height: 1.25rem;
  color: var(--partner-text-primary, #333e47);
  transition: border-color 0.15s, box-shadow 0.15s;
  cursor: pointer;

  /* Custom dropdown arrow */
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%235f6d79' d='M2.5 4.5L6 8l3.5-3.5'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 0.625rem center;
  background-size: 12px;
}

.form-select:hover {
  border-color: var(--partner-border-hovered, #919eab);
}

.form-select:focus {
  border-color: var(--partner-border-active, var(--app-accent));
  outline: none;
  box-shadow: 0 0 0 1px var(--partner-border-active, var(--app-accent));
}

.form-select:disabled {
  cursor: not-allowed;
  opacity: 0.5;
  border-color: var(--partner-border-disabled, #dfe3e8);
}

/* Source badges for auto-filled fields */
.field-badge {
  display: inline-block;
  font-family: var(--font-mono);
  font-size: 0.625rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  padding: 0.125rem 0.375rem;
  border-radius: 2px;
  margin-left: 0.5rem;
  vertical-align: middle;
}

.field-badge--osm {
  background-color: #dbeafe;
  color: #1e40af;
}

.field-badge--computed {
  background-color: #e0e7ff;
  color: #3730a3;
}

.field-badge--imputed {
  background-color: #fef3c7;
  color: #92400e;
}

/* Validation error */
.form-validation-error {
  font-family: var(--font-display);
  font-size: 0.875rem;
  color: var(--partner-error-main, #dc2626);
  background-color: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 4px;
  padding: 0.625rem 0.875rem;
  margin: 0 0 1rem;
}

/* Actions */
.form-actions {
  margin-top: 2.5rem;
  padding-top: 2rem;
  border-top: 1px solid #e2e6ea;
}
</style>
