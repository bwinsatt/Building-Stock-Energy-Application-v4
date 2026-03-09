<script setup lang="ts">
import { ref } from 'vue'
import { PTypography, PIcon } from '@partnerdevops/partner-components'
import { useAssessment } from '../composables/useAssessment'
import BuildingForm from '../components/BuildingForm.vue'
import BaselineSummary from '../components/BaselineSummary.vue'
import MeasuresTable from '../components/MeasuresTable.vue'
import AssumptionsPanel from '../components/AssumptionsPanel.vue'
import type { BuildingInput } from '../types/assessment'

const { loading, error, result, assess } = useAssessment()
const lastSqft = ref(0)

function onSubmit(input: BuildingInput) {
  lastSqft.value = input.sqft
  assess(input)
}
</script>

<template>
  <div class="assessment-view">
    <!-- Form -->
    <BuildingForm @submit="onSubmit" :disabled="loading" />

    <!-- Loading state -->
    <div v-if="loading" class="loading-card">
      <div class="loading-card__spinner" aria-label="Loading">
        <svg class="loading-card__svg" viewBox="0 0 50 50">
          <circle
            class="loading-card__track"
            cx="25" cy="25" r="20"
            fill="none"
            stroke-width="4"
          />
          <circle
            class="loading-card__arc"
            cx="25" cy="25" r="20"
            fill="none"
            stroke-width="4"
            stroke-linecap="round"
          />
        </svg>
      </div>
      <PTypography variant="h5" class="loading-card__title">
        Analyzing building...
      </PTypography>
      <p class="loading-card__subtitle">
        Running 476 models...
      </p>
    </div>

    <!-- Error state -->
    <div v-if="error" class="error-card">
      <div class="error-card__icon-wrap">
        <PIcon name="warning-alt" class="error-card__icon" />
      </div>
      <div class="error-card__content">
        <PTypography variant="h6" class="error-card__heading">
          Analysis Failed
        </PTypography>
        <PTypography variant="body2" class="error-card__message">
          {{ error }}
        </PTypography>
      </div>
    </div>

    <!-- Results -->
    <template v-if="result">
      <!-- Results section divider -->
      <div class="results-divider">
        <PTypography variant="subhead" class="results-divider__label">
          Results
        </PTypography>
        <div class="results-divider__line" aria-hidden="true" />
      </div>

      <AssumptionsPanel :summary="result.input_summary" />

      <BaselineSummary :baseline="result.baseline" :sqft="lastSqft" />

      <!-- Separator between baseline and measures -->
      <div class="section-separator" aria-hidden="true" />

      <MeasuresTable :measures="result.measures" :sqft="lastSqft" />
    </template>
  </div>
</template>

<style scoped>
/* ---- Layout ---- */
.assessment-view {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

/* ---- Results divider ---- */
.results-divider {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-top: 0.5rem;
}

.results-divider__label {
  flex-shrink: 0;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 0.6875rem;
  color: #64748b;
  white-space: nowrap;
}

.results-divider__line {
  flex: 1;
  height: 2px;
  background: linear-gradient(
    90deg,
    var(--app-accent) 0%,
    var(--app-accent-muted) 40%,
    transparent 100%
  );
}

/* ---- Section separator ---- */
.section-separator {
  height: 1px;
  background: #e2e8f0;
  margin: 0.25rem 0;
}

/* ---- Loading card ---- */
.loading-card {
  background: var(--app-surface-raised);
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  padding: 3rem 1.5rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.loading-card__spinner {
  width: 3rem;
  height: 3rem;
  margin-bottom: 1.25rem;
}

.loading-card__svg {
  width: 100%;
  height: 100%;
  animation: spin 1.2s linear infinite;
}

.loading-card__track {
  stroke: #e2e8f0;
}

.loading-card__arc {
  stroke: var(--app-accent);
  stroke-dasharray: 80, 200;
  stroke-dashoffset: 0;
}

.loading-card__title {
  color: var(--partner-text-primary, #333e47);
  animation: pulse-text 2s ease-in-out infinite;
}

.loading-card__subtitle {
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  color: #94a3b8;
  margin-top: 0.375rem;
  letter-spacing: 0.02em;
  animation: pulse-text 2s ease-in-out infinite;
}

@keyframes spin {
  100% {
    transform: rotate(360deg);
  }
}

@keyframes pulse-text {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

/* ---- Error card ---- */
.error-card {
  background: var(--app-surface-raised);
  border: 1px solid #e2e8f0;
  border-left: 3px solid #ef4444;
  border-radius: 0.5rem;
  padding: 1.25rem 1.5rem;
  display: flex;
  align-items: flex-start;
  gap: 1rem;
}

.error-card__icon-wrap {
  flex-shrink: 0;
  color: #ef4444;
  font-size: 1.25rem;
  margin-top: 0.125rem;
}

.error-card__icon {
  display: block;
}

.error-card__content {
  flex: 1;
  min-width: 0;
}

.error-card__heading {
  color: #dc2626;
  margin-bottom: 0.25rem;
}

.error-card__message {
  color: #64748b;
  word-break: break-word;
}

/* ---- Responsive ---- */
@media (max-width: 640px) {
  .loading-card {
    padding: 2rem 1rem;
  }
}
</style>
