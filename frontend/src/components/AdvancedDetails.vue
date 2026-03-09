<script setup lang="ts">
import { ref } from 'vue'
import type { BuildingInput } from '../types/assessment'
import {
  WALL_CONSTRUCTIONS,
  WINDOW_TYPES,
  WINDOW_TO_WALL_RATIOS,
  LIGHTING_TYPES,
} from '../config/dropdowns'
import { PNumericInput, PButton, PTypography } from '@partnerdevops/partner-components'

const props = defineProps<{
  modelValue: Partial<BuildingInput>
}>()

const emit = defineEmits<{
  'update:modelValue': [value: Partial<BuildingInput>]
}>()

const expanded = ref(false)

function update(field: keyof BuildingInput, value: string | number | undefined) {
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
        <span class="advanced-toggle__icon" :class="{ 'advanced-toggle__icon--open': expanded }">
          &#9662;
        </span>
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
        <!-- Wall Construction -->
        <div class="form-field">
          <label class="form-label" for="wall-construction">Wall Construction</label>
          <select
            id="wall-construction"
            :value="modelValue.wall_construction ?? ''"
            class="form-select"
            @change="update('wall_construction', ($event.target as HTMLSelectElement).value || undefined)"
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
            @change="update('window_type', ($event.target as HTMLSelectElement).value || undefined)"
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
            @change="update('window_to_wall_ratio', ($event.target as HTMLSelectElement).value || undefined)"
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
            @change="update('lighting_type', ($event.target as HTMLSelectElement).value || undefined)"
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
      </div>
    </div>
  </div>
</template>

<style scoped>
.advanced-section {
  margin-top: 2rem;
  padding-top: 1.5rem;
  border-top: 1px solid #e2e6ea;
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
  display: inline-block;
  font-size: 0.625rem;
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
  color: #8b95a1;
  margin: 0;
}

.advanced-header__line {
  flex: 1;
  height: 1px;
  background-color: #e2e6ea;
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

/* Field wrapper for native selects — mirrors BuildingForm */
.form-field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.form-label {
  font-family: var(--font-display);
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--partner-text-secondary, #5f6d79);
  line-height: 1.25rem;
}

/* Native select — matches Partner input styling */
.form-select {
  display: flex;
  width: 100%;
  height: 2rem;
  border-radius: 2px;
  border: 1px solid var(--partner-border-default, #c4cdd5);
  background-color: transparent;
  padding: 0 2rem 0 0.75rem;
  font-family: inherit;
  font-size: 0.875rem;
  line-height: 1.25rem;
  color: var(--partner-text-primary, #333e47);
  transition: border-color 0.15s, box-shadow 0.15s;
  cursor: pointer;
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
</style>
