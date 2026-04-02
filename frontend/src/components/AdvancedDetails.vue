<script setup>
import { ref, computed, watch } from 'vue'
import {
  WALL_CONSTRUCTIONS,
  WINDOW_TYPES,
  WINDOW_TO_WALL_RATIOS,
  LIGHTING_TYPES,
  HVAC_CATEGORIES,
  HVAC_HEATING_EFFICIENCIES_RESSTOCK,
  HVAC_COOLING_EFFICIENCIES_RESSTOCK,
  WATER_HEATER_EFFICIENCIES_RESSTOCK,
  WALL_INSULATIONS_RESSTOCK,
  INFILTRATION_RATES_RESSTOCK,
} from '../config/dropdowns'
import { PNumericInput, PButton, PTypography, PIcon } from '@partnerdevops/partner-components'

const CENTRAL_SYSTEM_VARIANTS = ['Fan Coil Units', 'Baseboards / Radiators']

const props = defineProps({
  modelValue: { type: Object, required: true },
  hvacCategory: { type: String, required: true },
  buildingType: { type: String, required: true },
})

const emit = defineEmits(['update:modelValue', 'update:hvacVariant'])

const expanded = ref(false)
const selectedVariant = ref('')

const currentDataset = computed(() => props.buildingType === 'Multi-Family' ? 'resstock' : 'comstock')

const hvacVariants = computed(() => {
  if (!props.hvacCategory) return []
  const cat = HVAC_CATEGORIES.find(c => c.key === props.hvacCategory)
  if (!cat) return []
  return cat.variants.filter(v => !v.dataset || v.dataset === currentDataset.value)
})

const isCentralSystem = computed(() => CENTRAL_SYSTEM_VARIANTS.includes(selectedVariant.value))

// Filter water heater efficiencies by selected DHW fuel (show all if none selected)
const DHW_FUEL_PREFIX = {
  NaturalGas: 'Natural Gas',
  Electricity: 'Electric',
  FuelOil: 'Fuel Oil',
  Propane: 'Propane',
  DistrictHeating: 'Other Fuel',
}
const filteredWaterHeaterEfficiencies = computed(() => {
  const fuel = props.modelValue.dhw_fuel
  if (!fuel) return WATER_HEATER_EFFICIENCIES_RESSTOCK
  const prefix = DHW_FUEL_PREFIX[fuel]
  if (!prefix) return WATER_HEATER_EFFICIENCIES_RESSTOCK
  return WATER_HEATER_EFFICIENCIES_RESSTOCK.filter(opt => opt.value.startsWith(prefix))
})

// Only show variant dropdown if the category has more than 1 variant
const showVariantDropdown = computed(() => hvacVariants.value.length > 1)

// When category changes, reset the selected variant
watch(() => props.hvacCategory, () => {
  selectedVariant.value = ''
})

// When variant changes, emit to parent
watch(selectedVariant, (val) => {
  if (val) {
    emit('update:hvacVariant', val)
  }
})

function update(field, value) {
  emit('update:modelValue', { ...props.modelValue, [field]: value })
}
</script>

<template>
  <div class="advanced-section">
    <PButton
      type="button"
      variant="neutral"
      appearance="text"
      size="small"
      @click="expanded = !expanded"
    >
      <span class="advanced-toggle">
        <PIcon
          name="chevron-down"
          size="small"
          :class="['advanced-toggle__icon', { 'advanced-toggle__icon--open': expanded }]"
        />
        {{ expanded ? 'Hide Advanced Details' : 'Show Advanced Details' }}
      </span>
    </PButton>

    <div v-if="expanded" class="advanced-content">
      <div class="advanced-header">
        <PTypography variant="subhead" component="p" class="advanced-header__label">
          Envelope &amp; Systems
        </PTypography>
        <div class="advanced-header__line" />
      </div>

      <div class="advanced-grid">
        <!-- Specific HVAC Variant (only shown when category has multiple variants) -->
        <div v-if="showVariantDropdown" class="form-field">
          <label class="form-label" for="hvac-variant">Specific HVAC System</label>
          <select
            id="hvac-variant"
            v-model="selectedVariant"
            class="form-select"
          >
            <option value="">-- Use Default --</option>
            <option v-for="v in hvacVariants" :key="v.value" :value="v.value">{{ v.label }}</option>
          </select>
        </div>

        <!-- Wall Construction -->
        <div class="form-field">
          <label class="form-label" for="wall-construction">Wall Construction</label>
          <select
            id="wall-construction"
            :value="modelValue.wall_construction ?? ''"
            class="form-select"
            @change="update('wall_construction', $event.target.value || undefined)"
          >
            <option value="">-- Select --</option>
            <option v-for="opt in WALL_CONSTRUCTIONS" :key="opt" :value="opt">{{ opt }}</option>
          </select>
        </div>

        <!-- Window Type -->
        <div class="form-field">
          <label class="form-label" for="window-type">Window Type</label>
          <select
            id="window-type"
            :value="modelValue.window_type ?? ''"
            class="form-select"
            @change="update('window_type', $event.target.value || undefined)"
          >
            <option value="">-- Select --</option>
            <option v-for="opt in WINDOW_TYPES" :key="opt" :value="opt">{{ opt }}</option>
          </select>
        </div>

        <!-- Window-to-Wall Ratio -->
        <div class="form-field">
          <label class="form-label" for="wwr">Window-to-Wall Ratio</label>
          <select
            id="wwr"
            :value="modelValue.window_to_wall_ratio ?? ''"
            class="form-select"
            @change="update('window_to_wall_ratio', $event.target.value || undefined)"
          >
            <option value="">-- Select --</option>
            <option v-for="opt in WINDOW_TO_WALL_RATIOS" :key="opt" :value="opt">{{ opt }}</option>
          </select>
        </div>

        <!-- Lighting Type -->
        <div class="form-field">
          <label class="form-label" for="lighting-type">Lighting Type</label>
          <select
            id="lighting-type"
            :value="modelValue.lighting_type ?? ''"
            class="form-select"
            @change="update('lighting_type', $event.target.value || undefined)"
          >
            <option value="">-- Select --</option>
            <option v-for="opt in LIGHTING_TYPES" :key="opt" :value="opt">{{ opt }}</option>
          </select>
        </div>

        <!-- Operating Hours -->
        <PNumericInput
          :model-value="modelValue.operating_hours ?? undefined"
          label="Operating Hours (per week)"
          :min="0"
          :max="168"
          :step="1"
          size="medium"
          @update:model-value="update('operating_hours', $event || undefined)"
        />

        <!-- ResStock Efficiency Fields (only for Multi-Family) -->
        <template v-if="props.buildingType === 'Multi-Family'">
          <!-- HVAC Heating Efficiency -->
          <div class="form-field">
            <label class="form-label" for="heating-efficiency">Heating Efficiency</label>
            <select
              id="heating-efficiency"
              :value="isCentralSystem ? 'Shared Heating' : (modelValue.hvac_heating_efficiency ?? '')"
              class="form-select"
              :disabled="isCentralSystem"
              @change="update('hvac_heating_efficiency', $event.target.value || undefined)"
            >
              <option value="">-- Auto --</option>
              <option v-for="opt in HVAC_HEATING_EFFICIENCIES_RESSTOCK" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </div>

          <!-- HVAC Cooling Efficiency -->
          <div class="form-field">
            <label class="form-label" for="cooling-efficiency">Cooling Efficiency</label>
            <select
              id="cooling-efficiency"
              :value="isCentralSystem ? 'Shared Cooling' : (modelValue.hvac_cooling_efficiency ?? '')"
              class="form-select"
              :disabled="isCentralSystem"
              @change="update('hvac_cooling_efficiency', $event.target.value || undefined)"
            >
              <option value="">-- Auto --</option>
              <option v-for="opt in HVAC_COOLING_EFFICIENCIES_RESSTOCK" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </div>

          <!-- Water Heater Efficiency -->
          <div class="form-field">
            <label class="form-label" for="wh-efficiency">Water Heater Efficiency</label>
            <select
              id="wh-efficiency"
              :value="modelValue.water_heater_efficiency ?? ''"
              class="form-select"
              @change="update('water_heater_efficiency', $event.target.value || undefined)"
            >
              <option value="">-- Auto --</option>
              <option v-for="opt in filteredWaterHeaterEfficiencies" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </div>

          <!-- Wall Insulation -->
          <div class="form-field">
            <label class="form-label" for="wall-insulation">Wall Insulation</label>
            <select
              id="wall-insulation"
              :value="modelValue.insulation_wall ?? ''"
              class="form-select"
              @change="update('insulation_wall', $event.target.value || undefined)"
            >
              <option value="">-- Auto --</option>
              <option v-for="opt in WALL_INSULATIONS_RESSTOCK" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </div>

          <!-- Infiltration -->
          <div class="form-field">
            <label class="form-label" for="infiltration">Air Tightness</label>
            <select
              id="infiltration"
              :value="modelValue.infiltration ?? ''"
              class="form-select"
              @change="update('infiltration', $event.target.value || undefined)"
            >
              <option value="">-- Auto --</option>
              <option v-for="opt in INFILTRATION_RATES_RESSTOCK" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.advanced-section {
  margin-top: 2rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--partner-gray-2);
}

.advanced-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  font-family: var(--font-display);
  font-size: 0.8125rem;
  font-weight: 500;
  letter-spacing: 0.01em;
}

.advanced-toggle__icon {
  display: inline-flex;
  transition: transform 0.2s ease;
}

.advanced-toggle__icon--open {
  transform: rotate(180deg);
}

.advanced-content {
  margin-top: 1.25rem;
}

.advanced-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.advanced-header__label {
  flex-shrink: 0;
  font-family: var(--font-display);
  font-size: 0.6875rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--partner-gray-5);
  margin: 0;
}

.advanced-header__line {
  flex: 1;
  height: 1px;
  background-color: var(--partner-gray-2);
}

.advanced-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem 1.5rem;
}

@media (min-width: 768px) {
  .advanced-grid {
    grid-template-columns: 1fr 1fr;
  }
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.form-label {
  font-family: var(--font-display);
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--partner-text-secondary);
  line-height: 1.25rem;
}

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
</style>
