<script setup>
import { ref, computed } from 'vue'
import { PTypography, PBadge, PTooltip, PIcon } from '@partnerdevops/partner-components'

const props = defineProps({
  summary: { type: Object, required: true },
})

const expanded = ref(false)

const imputedDetails = computed(() => props.summary.imputed_details ?? {})

const hasImputedFields = computed(() =>
  Object.keys(imputedDetails.value).length > 0
)

const derivedFields = computed(() => [
  { label: 'Climate Zone', value: props.summary.climate_zone, source: 'zipcode' },
  { label: 'Region', value: props.summary.cluster_name, source: 'zipcode' },
  { label: 'State', value: props.summary.state, source: 'zipcode' },
  { label: 'Vintage Bucket', value: props.summary.vintage_bucket, source: 'year_built' },
])

function confidenceLabel(confidence) {
  if (confidence == null) return 'default'
  if (confidence >= 0.7) return 'high'
  if (confidence >= 0.4) return 'medium'
  return 'low'
}

function confidencePercent(confidence) {
  if (confidence == null) return ''
  return `${Math.round(confidence * 100)}%`
}
</script>

<template>
  <div class="assumptions-panel">
    <button
      class="assumptions-toggle"
      type="button"
      @click="expanded = !expanded"
    >
      <PIcon
        name="chevron-down"
        size="small"
        :class="['assumptions-toggle__icon', { 'assumptions-toggle__icon--open': expanded }]"
      />
      <PTypography variant="subhead" component="span" class="assumptions-toggle__label">
        Assumptions Used
      </PTypography>
      <span v-if="hasImputedFields" class="assumptions-toggle__count">
        {{ Object.keys(imputedDetails).length }} imputed
      </span>
    </button>

    <div v-if="expanded" class="assumptions-content">
      <!-- Derived fields (always shown) -->
      <div class="assumptions-section">
        <div class="assumptions-section__title">Derived from Input</div>
        <div class="assumptions-grid">
          <div
            v-for="field in derivedFields"
            :key="field.label"
            class="assumptions-item"
          >
            <span class="assumptions-item__label">{{ field.label }}</span>
            <span class="assumptions-item__value">{{ field.value }}</span>
            <PBadge variant="primary" appearance="standard" size="small">
              {{ field.source }}
            </PBadge>
          </div>
        </div>
      </div>

      <!-- Imputed fields -->
      <div v-if="hasImputedFields" class="assumptions-section">
        <div class="assumptions-section__title">Estimated Values</div>
        <p class="assumptions-section__desc">
          These fields were not provided and were estimated using an ML model or building-type defaults.
        </p>
        <div class="assumptions-grid">
          <div
            v-for="(field, key) in imputedDetails"
            :key="key"
            class="assumptions-item"
          >
            <span class="assumptions-item__label">{{ field.label }}</span>
            <span class="assumptions-item__value">{{ field.value }}</span>
            <PBadge v-if="field.source === 'user'" variant="primary" appearance="standard" size="small">
              user
            </PBadge>
            <PBadge v-else-if="field.source === 'derived'" variant="primary" appearance="standard" size="small">
              derived
            </PBadge>
            <PTooltip v-else-if="field.confidence != null" direction="top">
              <template #tooltip-trigger>
                <PBadge
                  :variant="confidenceLabel(field.confidence) === 'high' ? 'success' : confidenceLabel(field.confidence) === 'medium' ? 'warning' : 'error'"
                  appearance="standard"
                  size="small"
                >
                  {{ confidencePercent(field.confidence) }} confidence
                </PBadge>
              </template>
              <template #tooltip-content>
                ML model prediction ({{ field.source }})
              </template>
            </PTooltip>
            <PBadge v-else variant="neutral" appearance="standard" size="small">
              default
            </PBadge>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.assumptions-panel {
  background: var(--app-surface-raised);
  border: 1px solid var(--partner-gray-2);
  border-radius: var(--partner-radius-lg);
  overflow: hidden;
}

.assumptions-toggle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.75rem 1.25rem;
  background: none;
  border: none;
  cursor: pointer;
  text-align: left;
}

.assumptions-toggle:hover {
  background: var(--partner-fill-hovered);
}

.assumptions-toggle__icon {
  display: inline-flex;
  color: var(--partner-gray-6);
  transition: transform 0.2s ease;
}

.assumptions-toggle__icon--open {
  transform: rotate(180deg);
}

.assumptions-toggle__label {
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-size: 0.75rem;
  color: var(--partner-text-secondary);
}

.assumptions-toggle__count {
  font-family: 'Roboto', sans-serif;
  font-size: 0.6875rem;
  font-weight: 400;
  color: var(--partner-gray-5);
  margin-left: auto;
}

.assumptions-content {
  padding: 0 1.25rem 1.25rem;
}

.assumptions-section {
  padding-top: 0.75rem;
}

.assumptions-section + .assumptions-section {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--partner-gray-2);
}

.assumptions-section__title {
  font-family: 'Roboto', sans-serif;
  font-size: 0.6875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--partner-gray-6);
  margin-bottom: 0.5rem;
}

.assumptions-section__desc {
  font-family: 'Roboto', sans-serif;
  font-size: 0.75rem;
  font-weight: 400;
  color: var(--partner-gray-5);
  margin: 0 0 0.75rem;
}

.assumptions-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.5rem;
}

@media (min-width: 640px) {
  .assumptions-grid {
    grid-template-columns: 1fr 1fr;
  }
}

.assumptions-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.375rem 0.5rem;
  background: var(--app-surface);
  border-radius: var(--partner-radius-md);
}

.assumptions-item__label {
  font-family: 'Roboto', sans-serif;
  font-size: 0.75rem;
  font-weight: 400;
  letter-spacing: 0.026rem;
  color: var(--partner-text-secondary);
  min-width: 0;
  flex-shrink: 0;
}

.assumptions-item__value {
  font-family: 'Roboto', sans-serif;
  font-size: 0.875rem;
  font-weight: 600;
  line-height: 1.25rem;
  color: var(--partner-text-primary);
  flex: 1;
  text-align: right;
}
</style>
