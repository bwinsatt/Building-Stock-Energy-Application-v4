<script setup lang="ts">
import { PTypography, PIcon } from '@partnerdevops/partner-components'
import { useEnergyStarScore } from '../composables/useEnergyStarScore'
import type { BuildingInput, BaselineResult } from '../types/assessment'

const props = defineProps<{
  building: BuildingInput
  baseline: BaselineResult
  address?: string | null
}>()

const { loading, error, result, fetchScore } = useEnergyStarScore()

function handleClick() {
  fetchScore(props.building, props.baseline, props.address)
}

function formatNumber(value: number): string {
  return value.toLocaleString('en-US', { maximumFractionDigits: 1 })
}
</script>

<template>
  <div class="es-section">
    <!-- Ready state: button -->
    <button
      v-if="!result && !loading && !error"
      class="es-trigger"
      @click="handleClick"
    >
      <span class="es-trigger__icon">&#11088;</span>
      <span class="es-trigger__text">
        <span class="es-trigger__title">Calculate ENERGY STAR Score</span>
        <span class="es-trigger__subtitle">Compare against similar buildings nationwide</span>
      </span>
      <PIcon name="chevron-right" class="es-trigger__arrow" />
    </button>

    <!-- Loading state -->
    <div v-if="loading" class="es-card es-card--loading">
      <div class="es-loading-spinner" aria-label="Calculating score">
        <svg viewBox="0 0 50 50">
          <circle cx="25" cy="25" r="20" fill="none" stroke-width="4" stroke="#e2e8f0" />
          <circle cx="25" cy="25" r="20" fill="none" stroke-width="4" stroke="var(--app-accent)"
                  stroke-linecap="round" stroke-dasharray="80, 200" />
        </svg>
      </div>
      <PTypography variant="body2" class="es-loading-text">
        Calculating ENERGY STAR score...
      </PTypography>
    </div>

    <!-- Error state -->
    <div v-if="error" class="es-card es-card--error">
      <PTypography variant="body2" class="es-error-text">{{ error }}</PTypography>
      <button class="es-retry-btn" @click="handleClick">Retry</button>
    </div>

    <!-- Result state -->
    <div v-if="result" class="es-card">
      <div class="es-result">
        <!-- Score gauge -->
        <div class="es-gauge">
          <svg viewBox="0 0 120 120" class="es-gauge__svg">
            <circle cx="60" cy="60" r="50" fill="none" stroke="#e2e8f0" stroke-width="8" />
            <circle
              v-if="result.eligible && result.score != null"
              cx="60" cy="60" r="50" fill="none"
              :stroke="result.score >= 75 ? '#22c55e' : result.score >= 50 ? '#eab308' : '#ef4444'"
              stroke-width="8" stroke-linecap="round"
              :stroke-dasharray="`${(result.score / 100) * 314} 314`"
              transform="rotate(-90 60 60)"
            />
          </svg>
          <div class="es-gauge__value">
            <template v-if="result.eligible && result.score != null">
              <span class="es-gauge__number" :style="{
                color: result.score >= 75 ? '#22c55e' : result.score >= 50 ? '#eab308' : '#ef4444'
              }">{{ result.score }}</span>
              <span class="es-gauge__label">out of 100</span>
            </template>
            <template v-else>
              <span class="es-gauge__na">N/A</span>
              <span class="es-gauge__label">not eligible</span>
            </template>
          </div>
          <div class="es-gauge__caption">ENERGY STAR&reg; Score</div>
        </div>

        <!-- Metrics -->
        <div class="es-metrics">
          <div v-if="result.eligible && result.percentile_text" class="es-metrics__headline">
            {{ result.percentile_text }}
          </div>
          <div v-else class="es-metrics__headline es-metrics__headline--muted">
            Score not available for this building type
          </div>

          <div v-if="result.reasons_for_no_score" class="es-metrics__reasons">
            <PTypography v-for="reason in result.reasons_for_no_score" :key="reason" variant="body2">
              {{ reason }}
            </PTypography>
          </div>

          <div class="es-metrics__cards">
            <div v-if="result.target_eui_kbtu_sf != null" class="es-metric-chip">
              <span class="es-metric-chip__label">Target EUI (75)</span>
              <span class="es-metric-chip__value">{{ formatNumber(result.target_eui_kbtu_sf) }} kBtu/sf</span>
            </div>
            <div v-if="result.median_eui_kbtu_sf != null" class="es-metric-chip">
              <span class="es-metric-chip__label">Median EUI</span>
              <span class="es-metric-chip__value">{{ formatNumber(result.median_eui_kbtu_sf) }} kBtu/sf</span>
            </div>
            <div v-if="result.design_eui_kbtu_sf != null" class="es-metric-chip">
              <span class="es-metric-chip__label">Your EUI</span>
              <span class="es-metric-chip__value">{{ formatNumber(result.design_eui_kbtu_sf) }} kBtu/sf</span>
            </div>
          </div>

          <PTypography variant="body2" class="es-metrics__type">
            ESPM property type: {{ result.espm_property_type }}
          </PTypography>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.es-trigger {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem 1.25rem;
  background: var(--app-surface-raised);
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
  text-align: left;
}
.es-trigger:hover {
  border-color: var(--app-accent);
  box-shadow: 0 0 0 1px var(--app-accent-muted);
}
.es-trigger__icon { font-size: 1.5rem; }
.es-trigger__text { flex: 1; display: flex; flex-direction: column; }
.es-trigger__title {
  font-weight: 600;
  font-size: 0.9375rem;
  color: var(--partner-text-primary, #333e47);
}
.es-trigger__subtitle {
  font-size: 0.8125rem;
  color: #64748b;
  margin-top: 0.125rem;
}
.es-trigger__arrow { color: #94a3b8; font-size: 1.25rem; }

.es-card {
  background: var(--app-surface-raised);
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  padding: 1.5rem;
}
.es-card--loading {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1.25rem 1.5rem;
}
.es-card--error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-left: 3px solid #ef4444;
}

.es-loading-spinner {
  width: 2rem;
  height: 2rem;
  flex-shrink: 0;
}
.es-loading-spinner svg { animation: es-spin 1.2s linear infinite; }
.es-loading-text { color: #64748b; }
@keyframes es-spin { 100% { transform: rotate(360deg); } }

.es-error-text { color: #ef4444; }
.es-retry-btn {
  padding: 0.375rem 0.75rem;
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--partner-text-primary, #333e47);
  background: transparent;
  border: 1px solid #e2e8f0;
  border-radius: 0.375rem;
  cursor: pointer;
  white-space: nowrap;
}
.es-retry-btn:hover {
  background: #f8fafc;
  border-color: #cbd5e1;
}

.es-result {
  display: flex;
  align-items: center;
  gap: 2rem;
}

.es-gauge {
  flex-shrink: 0;
  text-align: center;
  width: 120px;
}
.es-gauge__svg { width: 100px; height: 100px; display: block; margin: 0 auto; }
.es-gauge__value {
  margin-top: -70px;
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 60px;
}
.es-gauge__number { font-size: 2rem; font-weight: 700; line-height: 1; }
.es-gauge__label { font-size: 0.6875rem; color: #94a3b8; }
.es-gauge__na { font-size: 1.25rem; font-weight: 600; color: #94a3b8; }
.es-gauge__caption {
  font-size: 0.6875rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
  margin-top: 0.5rem;
}

.es-metrics { flex: 1; min-width: 0; }
.es-metrics__headline {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--partner-text-primary, #333e47);
  margin-bottom: 0.75rem;
}
.es-metrics__headline--muted { color: #94a3b8; }
.es-metrics__reasons { margin-bottom: 0.75rem; color: #64748b; }
.es-metrics__cards {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin-bottom: 0.75rem;
}
.es-metric-chip {
  display: flex;
  flex-direction: column;
  padding: 0.5rem 0.75rem;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 0.375rem;
}
.es-metric-chip__label {
  font-size: 0.6875rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #64748b;
}
.es-metric-chip__value {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--partner-text-primary, #333e47);
}
.es-metrics__type { color: #94a3b8; }

@media (max-width: 640px) {
  .es-result { flex-direction: column; align-items: stretch; }
  .es-gauge { margin: 0 auto; }
  .es-metrics__cards { flex-direction: column; }
}
</style>
