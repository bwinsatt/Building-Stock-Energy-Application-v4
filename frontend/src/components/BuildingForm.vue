<script setup>
import { reactive, ref, watch, computed } from 'vue'
import {
  BUILDING_TYPES,
  HEATING_FUELS,
  DHW_FUELS,
  getHvacCategoriesForDataset,
  getHvacCategoryForValue,
} from '../config/dropdowns'
import { PTextInput, PNumericInput, PButton, PTypography, PIcon } from '@partnerdevops/partner-components'
import AdvancedDetails from './AdvancedDetails.vue'
import AddressLookup from './AddressLookup.vue'
import BuildingMapViewer from './BuildingMapViewer.vue'
import { useAddressLookup } from '../composables/useAddressLookup'
import { useBpsSearch } from '../composables/useBpsSearch'

defineProps({
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['submit', 'lookup-complete'])

const form = reactive({
  building_type: '',
  sqft: 0,
  num_stories: 1,
  zipcode: '',
  year_built: undefined,
})

const advancedFields = ref({})
const hvacCategory = ref('')

// Utility data section state
const showUtilityData = ref(false)
const showExtraFuels = ref(false)

// Utility data fields (kept separate to make filtering easier)
const utilityData = reactive({})

const isCommercialBuilding = computed(() => form.building_type !== 'Multi-Family')

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

const bpsSearch = useBpsSearch()
const bpsDismissed = ref(false)

// Track which fields were auto-filled and their source
const fieldSources = ref({})

const PUBLIC_RECORD_SOURCES = new Set(['osm', 'nyc_opendata', 'chicago_opendata'])
function sourceLabel(source) {
  if (source === 'benchmarking') return 'Benchmarking'
  return source && PUBLIC_RECORD_SOURCES.has(source) ? 'Public records' : 'Estimated'
}

const lastRawAddress = ref('')

function onAddressLookup(address) {
  lastRawAddress.value = address
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
  const fieldMap = {
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
        ;form[formKey] = field.value
      }
      fieldSources.value[lookupKey] = field
    }
  }

  // Advanced fields
  const advancedMap = {
    wall_construction: 'wall_construction',
    window_type: 'window_type',
    window_to_wall_ratio: 'window_to_wall_ratio',
    lighting_type: 'lighting_type',
  }

  for (const [lookupKey, advKey] of Object.entries(advancedMap)) {
    const field = fields[lookupKey]
    if (field?.value != null) {
      advancedFields.value[advKey] = field.value
      fieldSources.value[lookupKey] = field
    }
  }

  emit('lookup-complete', result, lastRawAddress.value)

  // Allow watchers to fire normally after this tick
  setTimeout(() => { populatingFromLookup.value = false }, 0)
})

// Reset BPS state when address changes
watch(() => lookupResult.value, () => {
  bpsSearch.clear()
  bpsDismissed.value = false
})

function importBpsData(bpsResult, includeSquareFootage = false) {
  if (bpsResult.has_per_fuel_data) {
    if (bpsResult.electricity_kwh != null) {
      utilityData.annual_electricity_kwh = bpsResult.electricity_kwh
      fieldSources.value['annual_electricity_kwh'] = { value: bpsResult.electricity_kwh, source: 'benchmarking', confidence: bpsResult.match_confidence }
    }
    if (bpsResult.natural_gas_therms != null) {
      utilityData.annual_natural_gas_therms = bpsResult.natural_gas_therms
      fieldSources.value['annual_natural_gas_therms'] = { value: bpsResult.natural_gas_therms, source: 'benchmarking', confidence: bpsResult.match_confidence }
    }
    if (bpsResult.fuel_oil_gallons != null) {
      utilityData.annual_fuel_oil_gallons = bpsResult.fuel_oil_gallons
      fieldSources.value['annual_fuel_oil_gallons'] = { value: bpsResult.fuel_oil_gallons, source: 'benchmarking', confidence: bpsResult.match_confidence }
    }
    if (bpsResult.district_heating_kbtu != null) {
      utilityData.annual_district_heating_kbtu = bpsResult.district_heating_kbtu
      fieldSources.value['annual_district_heating_kbtu'] = { value: bpsResult.district_heating_kbtu, source: 'benchmarking', confidence: bpsResult.match_confidence }
    }
  }

  if (includeSquareFootage && bpsResult.reported_gross_floor_area != null) {
    populatingFromLookup.value = true
    form.sqft = Math.round(bpsResult.reported_gross_floor_area)
    fieldSources.value['sqft'] = { value: Math.round(bpsResult.reported_gross_floor_area), source: 'benchmarking', confidence: bpsResult.match_confidence }
    setTimeout(() => { populatingFromLookup.value = false }, 0)
  }

  showUtilityData.value = true
  bpsDismissed.value = true
}

// Clear source badge when user manually changes a field
const populatingFromLookup = ref(false)

const formFieldKeys = {
  building_type: 'building_type',
  sqft: 'sqft',
  num_stories: 'num_stories',
  year_built: 'year_built',
  heating_fuel: 'heating_fuel',
  dhw_fuel: 'dhw_fuel',
}

for (const [lookupKey, formKey] of Object.entries(formFieldKeys)) {
  watch(() => form[formKey], () => {
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
    const k = key
    if (newVal[k] !== oldVal?.[k]) {
      delete fieldSources.value[key]
    }
  }
}, { deep: true })

const validationError = ref(null)

function onSubmit() {
  validationError.value = null

  const requiredChecks = [
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
    ...utilityData,
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
  )
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

    <!-- BPS Benchmarking Banner -->
    <div v-if="lookupResult?.bps_available && !bpsDismissed" class="bps-banner">
      <!-- State 1: Available (not yet searched) -->
      <div v-if="!bpsSearch.searched.value && !bpsSearch.loading.value" class="bps-banner__available">
        <div class="bps-banner__icon">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M8 1L10 5.5L15 6.5L11.5 10L12.5 15L8 12.5L3.5 15L4.5 10L1 6.5L6 5.5L8 1Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
          </svg>
        </div>
        <div class="bps-banner__content">
          <span class="bps-banner__text">
            <strong>{{ lookupResult.bps_ordinance_name }}</strong> benchmarking data may be available for this address.
          </span>
          <button
            type="button"
            class="bps-banner__action"
            @click="bpsSearch.search(lastRawAddress, lookupResult?.city, lookupResult?.state, lookupResult?.zipcode, lookupResult?.bbl)"
          >
            Search Records
          </button>
        </div>
        <button type="button" class="bps-banner__dismiss" @click="bpsDismissed = true" aria-label="Dismiss">&times;</button>
      </div>

      <!-- State 2: Loading -->
      <div v-else-if="bpsSearch.loading.value" class="bps-banner__loading">
        <div class="bps-banner__spinner"></div>
        <span class="bps-banner__text">Searching {{ lookupResult.bps_ordinance_name }} records...</span>
      </div>

      <!-- State 3: Found -->
      <div v-else-if="bpsSearch.result.value" class="bps-banner__found">
        <div class="bps-banner__found-header">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M13.5 4.5L6 12L2.5 8.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span><strong>{{ bpsSearch.result.value.ordinance_name }}</strong> record found</span>
          <button type="button" class="bps-banner__dismiss" @click="bpsDismissed = true" aria-label="Dismiss">&times;</button>
        </div>
        <div class="bps-banner__data">
          <div v-if="bpsSearch.result.value.property_name" class="bps-banner__data-item">
            <span class="bps-banner__data-label">Property</span>
            <span class="bps-banner__data-value">{{ bpsSearch.result.value.property_name }}</span>
          </div>
          <div v-if="bpsSearch.result.value.site_eui_kbtu_sf" class="bps-banner__data-item">
            <span class="bps-banner__data-label">Site EUI</span>
            <span class="bps-banner__data-value">{{ bpsSearch.result.value.site_eui_kbtu_sf.toFixed(1) }} kBtu/ft²</span>
          </div>
          <div v-if="bpsSearch.result.value.electricity_kwh" class="bps-banner__data-item">
            <span class="bps-banner__data-label">Electricity</span>
            <span class="bps-banner__data-value">{{ Math.round(bpsSearch.result.value.electricity_kwh).toLocaleString() }} kWh</span>
          </div>
          <div v-if="bpsSearch.result.value.natural_gas_therms" class="bps-banner__data-item">
            <span class="bps-banner__data-label">Natural Gas</span>
            <span class="bps-banner__data-value">{{ Math.round(bpsSearch.result.value.natural_gas_therms).toLocaleString() }} therms</span>
          </div>
          <div v-if="bpsSearch.result.value.district_heating_kbtu" class="bps-banner__data-item">
            <span class="bps-banner__data-label">District Steam</span>
            <span class="bps-banner__data-value">{{ Math.round(bpsSearch.result.value.district_heating_kbtu).toLocaleString() }} kBtu</span>
          </div>
          <div v-if="bpsSearch.result.value.energy_star_score" class="bps-banner__data-item">
            <span class="bps-banner__data-label">ENERGY STAR</span>
            <span class="bps-banner__data-value">{{ bpsSearch.result.value.energy_star_score }}</span>
          </div>
        </div>
        <!-- Square footage comparison (when benchmarking reports gross floor area) -->
        <div v-if="bpsSearch.result.value.reported_gross_floor_area" class="bps-banner__sqft-comparison">
          <span class="bps-banner__data-label">Square Footage Comparison</span>
          <div class="bps-banner__sqft-values">
            <span class="bps-banner__sqft-item">
              <span class="bps-banner__sqft-label">Reported (Benchmarking):</span>
              <span class="bps-banner__sqft-reported">{{ Math.round(bpsSearch.result.value.reported_gross_floor_area).toLocaleString() }} ft²</span>
            </span>
            <span v-if="form.sqft" class="bps-banner__sqft-vs">vs</span>
            <span v-if="form.sqft" class="bps-banner__sqft-item">
              <span class="bps-banner__sqft-label">Estimated ({{ fieldSources['sqft']?.source === 'benchmarking' ? 'Benchmarking' : 'OSM' }}):</span>
              <span class="bps-banner__sqft-estimated">{{ Number(form.sqft).toLocaleString() }} ft²</span>
            </span>
          </div>
        </div>

        <div class="bps-banner__actions">
          <!-- Two-button layout when sqft data is available -->
          <template v-if="bpsSearch.result.value.reported_gross_floor_area">
            <PButton variant="success" size="small" @click="importBpsData(bpsSearch.result.value, true)">
              Import All Data
            </PButton>
            <button type="button" class="bps-banner__energy-only" @click="importBpsData(bpsSearch.result.value, false)">
              Import Energy Data Only
            </button>
          </template>
          <!-- Fallback single button when no sqft data -->
          <template v-else>
            <PButton variant="success" size="small" @click="importBpsData(bpsSearch.result.value, false)">
              Import to Utility Data
            </PButton>
          </template>
        </div>
      </div>

      <!-- State 4: Not found -->
      <div v-else-if="bpsSearch.searched.value && !bpsSearch.result.value && !bpsSearch.error.value && !bpsSearch.loading.value" class="bps-banner__not-found">
        <span class="bps-banner__text">No matching record found in {{ lookupResult.bps_ordinance_name }}.</span>
        <button type="button" class="bps-banner__dismiss" @click="bpsDismissed = true" aria-label="Dismiss">&times;</button>
      </div>

      <!-- State 5: Error -->
      <div v-else-if="bpsSearch.error.value" class="bps-banner__error">
        <span class="bps-banner__text">Search failed. Please try again.</span>
        <button
          type="button"
          class="bps-banner__action"
          @click="bpsSearch.search(lastRawAddress, lookupResult?.city, lookupResult?.state, lookupResult?.zipcode, lookupResult?.bbl)"
        >
          Retry
        </button>
        <button type="button" class="bps-banner__dismiss" @click="bpsDismissed = true" aria-label="Dismiss">&times;</button>
      </div>
    </div>

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
            {{ sourceLabel(fieldSources['building_type'].source) }}
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
            {{ sourceLabel(fieldSources['sqft'].source) }}
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
            {{ sourceLabel(fieldSources['num_stories'].source) }}
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
            {{ sourceLabel(fieldSources['year_built'].source) }}
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
            {{ sourceLabel(fieldSources['heating_fuel'].source) }}
          </span>
        </label>
        <select
          id="heating-fuel"
          v-model="form.heating_fuel"
          class="form-select"
        >
          <option value="">-- Select --</option>
          <option v-for="fuel in HEATING_FUELS" :key="fuel.value" :value="fuel.value">{{ fuel.label }}</option>
        </select>
      </div>

      <!-- DHW Fuel -->
      <div class="form-field">
        <label class="form-label" for="dhw-fuel">
          DHW Fuel
          <span v-if="fieldSources['dhw_fuel']" class="field-badge" :class="'field-badge--' + fieldSources['dhw_fuel'].source">
            {{ sourceLabel(fieldSources['dhw_fuel'].source) }}
          </span>
        </label>
        <select
          id="dhw-fuel"
          v-model="form.dhw_fuel"
          class="form-select"
        >
          <option value="">-- Select --</option>
          <option v-for="fuel in DHW_FUELS" :key="fuel.value" :value="fuel.value">{{ fuel.label }}</option>
        </select>
      </div>

      <!-- HVAC Type -->
      <div class="form-field">
        <label class="form-label" for="hvac-system">
          HVAC Type
          <span v-if="fieldSources['hvac_system_type']" class="field-badge" :class="'field-badge--' + fieldSources['hvac_system_type'].source">
            {{ sourceLabel(fieldSources['hvac_system_type'].source) }}
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
      @update:hvac-variant="(v) => form.hvac_system_type = v"
    />

    <!-- Section: Utility Data (collapsible) -->
    <div class="utility-section">
      <button
        type="button"
        class="utility-toggle"
        @click="showUtilityData = !showUtilityData"
        :aria-expanded="showUtilityData"
      >
        <span class="utility-toggle__label">Have utility bills? <span class="utility-toggle__optional">(Optional)</span></span>
        <span class="utility-toggle__icon" :class="{ 'utility-toggle__icon--open': showUtilityData }">
          <PIcon name="chevron-down" size="small" />
        </span>
      </button>

      <div v-if="showUtilityData" class="utility-fields">
        <p class="utility-fields__desc">Enter annual consumption data to calibrate the energy model to your building's actual usage.</p>

        <div class="form-grid">
          <!-- Annual Electricity -->
          <div class="form-field">
            <label class="form-label" for="annual-electricity">
              Annual Electricity (kWh)
              <span v-if="fieldSources['annual_electricity_kwh']" class="field-badge" :class="'field-badge--' + fieldSources['annual_electricity_kwh'].source">
                {{ sourceLabel(fieldSources['annual_electricity_kwh'].source) }}
              </span>
            </label>
            <PNumericInput
              id="annual-electricity"
              v-model="utilityData.annual_electricity_kwh"
              :min="0"
              :step="1000"
              size="medium"
            />
          </div>

          <!-- Annual Natural Gas -->
          <div class="form-field">
            <label class="form-label" for="annual-natural-gas">
              Annual Natural Gas (therms)
              <span v-if="fieldSources['annual_natural_gas_therms']" class="field-badge" :class="'field-badge--' + fieldSources['annual_natural_gas_therms'].source">
                {{ sourceLabel(fieldSources['annual_natural_gas_therms'].source) }}
              </span>
            </label>
            <PNumericInput
              id="annual-natural-gas"
              v-model="utilityData.annual_natural_gas_therms"
              :min="0"
              :step="100"
              size="medium"
            />
          </div>
        </div>

        <!-- Add more fuel types link -->
        <button
          v-if="!showExtraFuels"
          type="button"
          class="utility-more-link"
          @click="showExtraFuels = true"
        >
          + Add more fuel types
        </button>

        <!-- Extra fuel types -->
        <div v-if="showExtraFuels" class="form-grid utility-extra-fuels">
          <!-- Annual Fuel Oil -->
          <div class="form-field">
            <label class="form-label" for="annual-fuel-oil">
              Annual Fuel Oil (gallons)
              <span v-if="fieldSources['annual_fuel_oil_gallons']" class="field-badge" :class="'field-badge--' + fieldSources['annual_fuel_oil_gallons'].source">
                {{ sourceLabel(fieldSources['annual_fuel_oil_gallons'].source) }}
              </span>
            </label>
            <PNumericInput
              id="annual-fuel-oil"
              v-model="utilityData.annual_fuel_oil_gallons"
              :min="0"
              :step="10"
              size="medium"
            />
          </div>

          <!-- Annual Propane -->
          <div class="form-field">
            <label class="form-label" for="annual-propane">Annual Propane (gallons)</label>
            <PNumericInput
              id="annual-propane"
              v-model="utilityData.annual_propane_gallons"
              :min="0"
              :step="10"
              size="medium"
            />
          </div>

          <!-- Annual District Heating (commercial only) -->
          <div v-if="isCommercialBuilding" class="form-field">
            <label class="form-label" for="annual-district-heating">Annual District Heating (kBtu)</label>
            <PNumericInput
              id="annual-district-heating"
              v-model="utilityData.annual_district_heating_kbtu"
              :min="0"
              :step="10000"
              size="medium"
            />
          </div>
        </div>
      </div>
    </div>

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
  border: 1px solid var(--partner-gray-2);
  border-radius: var(--partner-radius-lg);
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
  border-top: 1px solid var(--partner-gray-2);
}

.form-section__title {
  font-family: var(--font-display);
  color: var(--partner-gray-7);
  letter-spacing: -0.01em;
  margin: 0;
}

.form-section__desc {
  font-family: var(--font-display);
  font-size: 0.75rem;
  color: var(--partner-text-secondary);
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
  color: var(--partner-text-secondary);
  line-height: 1.25rem;
}

.form-label__required {
  color: var(--partner-error-main);
}

/* Native select styled to match Partner input styling */
.form-select {
  display: flex;
  width: 100%;
  height: 2rem;
  border-radius: var(--partner-radius-sm);
  border: 1px solid var(--partner-border-default);
  background-color: transparent;
  padding: 0 2rem 0 0.75rem;
  font-family: inherit;
  font-size: 0.875rem;
  line-height: 1.25rem;
  color: var(--partner-text-primary);
  transition: border-color 0.15s, box-shadow 0.15s;
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%236F7881' d='M2.5 4.5L6 8l3.5-3.5'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 0.625rem center;
  background-size: 12px;
}

.form-select:hover {
  border-color: var(--partner-border-hovered);
}

.form-select:focus {
  border-color: var(--partner-border-active);
  outline: none;
  box-shadow: 0 0 0 1px var(--partner-border-active);
}

.form-select:disabled {
  cursor: not-allowed;
  opacity: 0.5;
  border-color: var(--partner-border-disabled);
}

/* Source badges for auto-filled fields */
.field-badge {
  display: inline-block;
  font-family: var(--font-display);
  font-size: 0.6875rem;
  font-weight: 500;
  letter-spacing: 0.01em;
  padding: 0.125rem 0.4375rem;
  border-radius: var(--partner-radius-sm);
  margin-left: 0.5rem;
  vertical-align: middle;
}

.field-badge--osm,
.field-badge--nyc_opendata,
.field-badge--chicago_opendata {
  background-color: var(--partner-blue-2);
  color: var(--partner-blue-8);
}

.field-badge--computed {
  background-color: var(--partner-blue-1);
  color: var(--partner-blue-9);
}

.field-badge--imputed {
  background-color: var(--partner-yellow-1);
  color: var(--partner-yellow-9);
}

/* Validation error */
.form-validation-error {
  font-family: var(--font-display);
  font-size: 0.875rem;
  color: var(--partner-error-main);
  background-color: var(--partner-red-1);
  border: 1px solid var(--partner-red-2);
  border-radius: var(--partner-radius-md);
  padding: 0.625rem 0.875rem;
  margin: 0 0 1rem;
}

/* Actions */
.form-actions {
  margin-top: 2.5rem;
  padding-top: 2rem;
  border-top: 1px solid var(--partner-gray-2);
}

/* Utility data collapsible section */
.utility-section {
  margin-top: 2rem;
  padding-top: 2rem;
  border-top: 1px solid var(--partner-gray-2);
}

.utility-toggle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  width: 100%;
  text-align: left;
}

.utility-toggle__label {
  font-family: var(--font-display);
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--partner-gray-7);
}

.utility-toggle__optional {
  font-weight: 400;
  color: var(--partner-text-secondary);
}

.utility-toggle__icon {
  display: flex;
  align-items: center;
  color: var(--partner-text-secondary);
  transition: transform 0.2s ease;
}

.utility-toggle__icon--open {
  transform: rotate(180deg);
}

.utility-fields {
  margin-top: 1rem;
}

.utility-fields__desc {
  font-family: var(--font-display);
  font-size: 0.75rem;
  color: var(--partner-text-secondary);
  margin: 0 0 1rem;
}

.utility-more-link {
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  font-family: var(--font-display);
  font-size: 0.8125rem;
  color: var(--partner-primary-main);
  margin-top: 0.75rem;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.utility-more-link:hover {
  color: var(--partner-primary-dark);
}

.utility-extra-fuels {
  margin-top: 1rem;
}

/* BPS Benchmarking Banner */
.bps-banner {
  margin-bottom: 1.5rem;
  border-radius: var(--partner-radius-lg);
  font-family: var(--font-display);
  font-size: 0.8125rem;
}

.bps-banner__available {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  padding: 0.75rem 1rem;
  background: linear-gradient(135deg, var(--partner-green-1), var(--partner-green-1));
  border: 1px solid var(--partner-green-3);
  border-radius: var(--partner-radius-lg);
}

.bps-banner__icon {
  flex-shrink: 0;
  color: var(--partner-green-6);
}

.bps-banner__content {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex: 1;
  flex-wrap: wrap;
}

.bps-banner__text {
  color: var(--partner-green-10);
  line-height: 1.4;
}

.bps-banner__action {
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  font-family: var(--font-display);
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--partner-green-6);
  text-decoration: underline;
  text-underline-offset: 2px;
  white-space: nowrap;
}

.bps-banner__action:hover {
  color: var(--partner-green-7);
}

.bps-banner__dismiss {
  flex-shrink: 0;
  background: none;
  border: none;
  padding: 0.125rem;
  cursor: pointer;
  font-size: 1.125rem;
  line-height: 1;
  color: var(--partner-gray-6);
  opacity: 0.6;
}

.bps-banner__dismiss:hover {
  opacity: 1;
}

.bps-banner__loading {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  padding: 0.75rem 1rem;
  background: var(--partner-green-1);
  border: 1px solid var(--partner-green-3);
  border-radius: var(--partner-radius-lg);
  color: var(--partner-green-10);
}

.bps-banner__spinner {
  width: 16px;
  height: 16px;
  border: 2px solid var(--partner-green-3);
  border-top-color: var(--partner-green-6);
  border-radius: 50%;
  animation: bps-spin 0.6s linear infinite;
}

@keyframes bps-spin {
  to { transform: rotate(360deg); }
}

.bps-banner__found {
  padding: 0.75rem 1rem;
  background: linear-gradient(135deg, var(--partner-green-1), var(--partner-green-1));
  border: 1px solid var(--partner-green-3);
  border-radius: var(--partner-radius-lg);
}

.bps-banner__found-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--partner-green-8);
  font-weight: 500;
  margin-bottom: 0.625rem;
}

.bps-banner__data {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 1.5rem;
  margin-bottom: 0.625rem;
}

.bps-banner__data-item {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}

.bps-banner__data-label {
  font-size: 0.625rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--partner-gray-6);
}

.bps-banner__data-value {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--partner-gray-7);
}

.bps-banner__actions {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}

.bps-banner__sqft-comparison {
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid var(--partner-gray-3);
  border-radius: var(--partner-radius-md);
  padding: 0.625rem 0.875rem;
  margin-bottom: 0.625rem;
}

.bps-banner__sqft-values {
  display: flex;
  align-items: baseline;
  gap: 1rem;
  flex-wrap: wrap;
  margin-top: 0.375rem;
}

.bps-banner__sqft-item {
  display: flex;
  align-items: baseline;
  gap: 0.375rem;
}

.bps-banner__sqft-label {
  font-size: 0.75rem;
  color: var(--partner-text-secondary);
  line-height: 1.5;
}

.bps-banner__sqft-reported {
  font-size: 0.875rem;
  font-weight: 700;
  color: var(--partner-text-primary);
  line-height: 1.43;
}

.bps-banner__sqft-estimated {
  font-size: 0.875rem;
  font-weight: 400;
  color: var(--partner-text-secondary);
  line-height: 1.43;
}

.bps-banner__sqft-vs {
  font-size: 0.75rem;
  color: var(--partner-text-disabled);
}

.bps-banner__energy-only {
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  font-family: var(--font-display);
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--partner-text-secondary);
  text-decoration: underline;
  text-underline-offset: 2px;
  letter-spacing: 0.02em;
}

.bps-banner__energy-only:hover {
  color: var(--partner-text-primary);
}

.bps-banner__not-found {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  padding: 0.75rem 1rem;
  background: var(--partner-yellow-1);
  border: 1px solid var(--partner-yellow-3);
  border-radius: var(--partner-radius-lg);
  color: var(--partner-yellow-10);
}

.bps-banner__error {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  padding: 0.75rem 1rem;
  background: var(--partner-red-1);
  border: 1px solid var(--partner-red-2);
  border-radius: var(--partner-radius-lg);
  color: var(--partner-red-7);
}

.field-badge--benchmarking {
  background: var(--partner-green-1);
  color: var(--partner-green-9);
}
</style>
