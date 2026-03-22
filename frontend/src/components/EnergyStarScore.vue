<script setup lang="ts">
import { computed } from 'vue'
import { PTypography, PIcon, PButton } from '@partnerdevops/partner-components'
import { useEnergyStarScore } from '../composables/useEnergyStarScore'
import type { BuildingInput, BaselineResult, ProjectedEui, EnergyStarResponse } from '../types/assessment'

const props = defineProps<{
  building: BuildingInput
  baseline: BaselineResult
  address?: string | null
  selectedCount?: number
  projectedEui?: ProjectedEui | null
  projectedEspm?: EnergyStarResponse | null
  projectedLoading?: boolean
  projectedError?: string | null
}>()

const emit = defineEmits<{
  'calculate-projected': []
}>()

const { loading, error, result, fetchScore } = useEnergyStarScore()

function handleClick() {
  fetchScore(props.building, props.baseline, props.address)
}

function formatNumber(value: number): string {
  return value.toLocaleString('en-US', { maximumFractionDigits: 1 })
}

// ---- State machine ----
type ScoreState = 'trigger' | 'baseline-only' | 'measures-selected' | 'projected'

const scoreState = computed<ScoreState>(() => {
  if (!result.value) return 'trigger'
  if (props.projectedEspm) return 'projected'
  if ((props.selectedCount ?? 0) > 0) return 'measures-selected'
  return 'baseline-only'
})

// ---- Score color using Partner tokens ----
function scoreColor(score: number | null): string {
  if (score == null) return 'var(--partner-gray-5)'
  if (score >= 75) return 'var(--partner-green-7)'
  if (score >= 50) return 'var(--partner-yellow-7)'
  return 'var(--partner-orange-7)'
}

function scoreDasharray(score: number | null): string {
  if (score == null) return '0 314'
  return `${(score / 100) * 314} 314`
}

// ---- Baseline label changes based on state ----
const baselineLabel = computed(() =>
  scoreState.value === 'trigger' || scoreState.value === 'baseline-only'
    ? 'ENERGY STAR\u00AE Score'
    : 'Baseline Score'
)

// ---- Score delta for arrow divider ----
const scoreDelta = computed(() => {
  if (!result.value?.score || !props.projectedEspm?.score) return null
  return props.projectedEspm.score - result.value.score
})
</script>

<template>
  <div class="es-section">
    <!-- State 1: Trigger (no baseline score yet) -->
    <button
      v-if="scoreState === 'trigger' && !loading && !error"
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

    <!-- Loading state for baseline -->
    <div v-else-if="loading" class="es-card es-card--loading">
      <div class="es-loading-spinner" aria-label="Calculating score">
        <svg viewBox="0 0 50 50">
          <circle cx="25" cy="25" r="20" fill="none" stroke-width="4" stroke="var(--partner-gray-2)" />
          <circle cx="25" cy="25" r="20" fill="none" stroke-width="4" stroke="var(--partner-blue-7)"
                  stroke-linecap="round" stroke-dasharray="80, 200" />
        </svg>
      </div>
      <PTypography variant="body2" class="es-loading-text">
        Calculating ENERGY STAR score...
      </PTypography>
    </div>

    <!-- Error state for baseline -->
    <div v-else-if="error" class="es-card es-card--error">
      <PTypography variant="body2" class="es-error-text">{{ error }}</PTypography>
      <button class="es-retry-btn" @click="handleClick">Retry</button>
    </div>

    <!-- States 2-4: Split layout (result exists) -->
    <div v-else-if="result" class="es-card es-split">
      <!-- LEFT HALF: Baseline -->
      <div class="es-half">
        <div class="es-gauge">
          <svg viewBox="0 0 120 120" class="es-gauge__svg">
            <circle cx="60" cy="60" r="50" fill="none" stroke="var(--partner-gray-2)" stroke-width="8" />
            <circle
              v-if="result.eligible && result.score != null"
              cx="60" cy="60" r="50" fill="none"
              :stroke="scoreColor(result.score)"
              stroke-width="8" stroke-linecap="round"
              :stroke-dasharray="scoreDasharray(result.score)"
              transform="rotate(-90 60 60)"
            />
          </svg>
          <div class="es-gauge__value">
            <template v-if="result.eligible && result.score != null">
              <span class="es-gauge__number" :style="{ color: scoreColor(result.score) }">{{ result.score }}</span>
              <span class="es-gauge__label">out of 100</span>
            </template>
            <template v-else>
              <span class="es-gauge__na">N/A</span>
              <span class="es-gauge__label">not eligible</span>
            </template>
          </div>
          <div class="es-gauge__caption">{{ baselineLabel }}</div>
        </div>

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

      <!-- DIVIDER -->
      <div v-if="scoreState === 'projected'" class="es-arrow-divider">
        <div class="es-arrow-divider__line"></div>
        <div class="es-arrow-divider__circle">&#8594;</div>
        <div v-if="scoreDelta != null" class="es-arrow-divider__delta">
          {{ scoreDelta > 0 ? '+' : '' }}{{ scoreDelta }} pts
        </div>
      </div>
      <div v-else class="es-divider"></div>

      <!-- RIGHT HALF: State 2 — empty/instructional -->
      <div v-if="scoreState === 'baseline-only'" class="es-empty">
        <div class="es-empty__inner">
          <div class="es-empty__icon">&#11088;</div>
          <div class="es-empty__text">
            Select upgrades below to calculate your<br>
            post-retrofit ENERGY STAR score
          </div>
        </div>
      </div>

      <!-- RIGHT HALF: State 3 — measures selected, ready to calculate -->
      <div v-else-if="scoreState === 'measures-selected' && !projectedLoading && !projectedError" class="es-ready">
        <div class="es-ready__inner">
          <div class="es-ready__count">{{ selectedCount }} upgrade{{ selectedCount === 1 ? '' : 's' }} selected</div>
          <div class="es-ready__eui">
            Projected EUI: <span class="es-ready__eui-val">{{ projectedEui?.total_eui_kbtu_sf?.toFixed(1) }} kBtu/sf</span>
            <span class="es-ready__eui-pct">(-{{ projectedEui?.reduction_pct?.toFixed(1) }}%)</span>
          </div>
          <button class="es-btn" @click="emit('calculate-projected')">
            &#11088; Calculate Projected Score
          </button>
        </div>
      </div>

      <!-- RIGHT HALF: State 3 loading -->
      <div v-else-if="projectedLoading" class="es-ready">
        <div class="es-ready__inner">
          <div class="es-loading-spinner es-loading-spinner--small">
            <svg viewBox="0 0 50 50">
              <circle cx="25" cy="25" r="20" fill="none" stroke-width="4" stroke="var(--partner-gray-2)" />
              <circle cx="25" cy="25" r="20" fill="none" stroke-width="4" stroke="var(--partner-blue-7)"
                      stroke-linecap="round" stroke-dasharray="80, 200" />
            </svg>
          </div>
          <PTypography variant="body2" class="es-loading-text">
            Calculating projected score...
          </PTypography>
        </div>
      </div>

      <!-- RIGHT HALF: State 3 error -->
      <div v-else-if="projectedError" class="es-ready">
        <div class="es-ready__inner">
          <PTypography variant="body2" class="es-error-text">{{ projectedError }}</PTypography>
          <button class="es-retry-btn" style="margin-top: 0.5rem;" @click="emit('calculate-projected')">Retry</button>
        </div>
      </div>

      <!-- RIGHT HALF: State 4 — projected score -->
      <div v-else-if="scoreState === 'projected'" class="es-half es-half--projected">
        <div class="es-gauge">
          <svg viewBox="0 0 120 120" class="es-gauge__svg">
            <circle cx="60" cy="60" r="50" fill="none" stroke="var(--partner-gray-2)" stroke-width="8" />
            <circle
              v-if="projectedEspm?.eligible && projectedEspm?.score != null"
              cx="60" cy="60" r="50" fill="none"
              :stroke="scoreColor(projectedEspm.score)"
              stroke-width="8" stroke-linecap="round"
              :stroke-dasharray="scoreDasharray(projectedEspm.score)"
              transform="rotate(-90 60 60)"
            />
          </svg>
          <div class="es-gauge__value">
            <template v-if="projectedEspm?.eligible && projectedEspm?.score != null">
              <span class="es-gauge__number" :style="{ color: scoreColor(projectedEspm.score) }">{{ projectedEspm.score }}</span>
              <span class="es-gauge__label">out of 100</span>
            </template>
            <template v-else>
              <span class="es-gauge__na">N/A</span>
              <span class="es-gauge__label">not eligible</span>
            </template>
          </div>
          <div class="es-gauge__caption es-gauge__caption--projected">Projected Score</div>
        </div>

        <div class="es-metrics">
          <div v-if="projectedEspm?.eligible && projectedEspm?.score" class="es-metrics__headline">
            Would be better than {{ projectedEspm.score }}% of similar buildings
          </div>

          <div class="es-metrics__cards">
            <div v-if="projectedEui" class="es-metric-chip es-metric-chip--green">
              <span class="es-metric-chip__label es-metric-chip__label--green">Projected EUI</span>
              <span class="es-metric-chip__value es-metric-chip__value--green">{{ projectedEui.total_eui_kbtu_sf.toFixed(1) }} kBtu/sf</span>
            </div>
            <div v-if="projectedEui" class="es-metric-chip es-metric-chip--green">
              <span class="es-metric-chip__label es-metric-chip__label--green">EUI Reduction</span>
              <span class="es-metric-chip__value es-metric-chip__value--green">-{{ projectedEui.reduction_pct.toFixed(1) }}%</span>
            </div>
          </div>

          <PTypography variant="body2" class="es-metrics__type">
            {{ selectedCount }} upgrade{{ selectedCount === 1 ? '' : 's' }} selected
          </PTypography>
          <button class="es-btn es-btn--outline" @click="emit('calculate-projected')">Recalculate</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ---- Trigger button ---- */
.es-trigger {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem 1.25rem;
  background: var(--partner-white, #fff);
  border: 1px solid var(--partner-gray-2);
  border-radius: var(--partner-radius-lg);
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
  text-align: left;
}
.es-trigger:hover {
  border-color: var(--partner-blue-7);
  box-shadow: 0 0 0 1px var(--partner-blue-6);
}
.es-trigger__icon { font-size: 1.5rem; }
.es-trigger__text { flex: 1; display: flex; flex-direction: column; }
.es-trigger__title {
  font-weight: 600;
  font-size: 0.9375rem;
  color: var(--partner-gray-7);
}
.es-trigger__subtitle {
  font-size: 0.8125rem;
  color: var(--partner-gray-6);
  margin-top: 0.125rem;
}
.es-trigger__arrow { color: var(--partner-gray-5); font-size: 1.25rem; }

/* ---- Card container ---- */
.es-card {
  background: var(--partner-white, #fff);
  border: 1px solid var(--partner-gray-2);
  border-radius: var(--partner-radius-lg);
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
  border-left: 3px solid var(--partner-orange-7);
}

/* ---- Loading spinner ---- */
.es-loading-spinner {
  width: 2rem;
  height: 2rem;
  flex-shrink: 0;
}
.es-loading-spinner svg { animation: es-spin 1.2s linear infinite; }
.es-loading-spinner--small {
  width: 1.5rem;
  height: 1.5rem;
  margin: 0 auto 0.5rem;
}
.es-loading-text { color: var(--partner-gray-6); }
@keyframes es-spin { 100% { transform: rotate(360deg); } }

/* ---- Error / Retry ---- */
.es-error-text { color: var(--partner-orange-7); }
.es-retry-btn {
  padding: 0.375rem 0.75rem;
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--partner-gray-7);
  background: transparent;
  border: 1px solid var(--partner-gray-2);
  border-radius: var(--partner-radius-md);
  cursor: pointer;
  white-space: nowrap;
}
.es-retry-btn:hover {
  background: var(--partner-gray-1);
  border-color: var(--partner-gray-3);
}

/* ---- Split layout ---- */
.es-split {
  display: flex;
  min-height: 190px;
  padding: 0;
}
.es-half {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 1.25rem;
  padding: 1.5rem 1.75rem;
}
.es-divider {
  width: 1px;
  background: var(--partner-gray-2);
  align-self: stretch;
  margin: 1.25rem 0;
}

/* ---- Gauge ---- */
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
.es-gauge__label { font-size: 0.6875rem; color: var(--partner-gray-5); }
.es-gauge__na { font-size: 1.25rem; font-weight: 600; color: var(--partner-gray-5); }
.es-gauge__caption {
  font-size: 0.6875rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--partner-gray-6);
  font-weight: 600;
  margin-top: 0.875rem;
}
.es-gauge__caption--projected { color: var(--partner-green-7); }

/* ---- Metrics ---- */
.es-metrics { flex: 1; min-width: 0; }
.es-metrics__headline {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--partner-gray-7);
  margin-bottom: 0.75rem;
}
.es-metrics__headline--muted { color: var(--partner-gray-5); }
.es-metrics__reasons { margin-bottom: 0.75rem; color: var(--partner-gray-6); }
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
  background: var(--partner-gray-1);
  border: 1px solid var(--partner-gray-2);
  border-radius: var(--partner-radius-md);
}
.es-metric-chip--green {
  background: var(--partner-green-1);
  border-color: var(--partner-green-2);
}
.es-metric-chip__label {
  font-size: 0.6875rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--partner-gray-6);
}
.es-metric-chip__label--green { color: var(--partner-green-7); }
.es-metric-chip__value {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--partner-gray-7);
}
.es-metric-chip__value--green { color: var(--partner-green-7); }
.es-metrics__type { color: var(--partner-gray-5); }

/* ---- Empty state (right half, state 2) ---- */
.es-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem 1.75rem;
}
.es-empty__inner { text-align: center; max-width: 280px; }
.es-empty__icon { font-size: 1.75rem; margin-bottom: 0.5rem; opacity: 0.25; }
.es-empty__text {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--partner-gray-6);
  line-height: 1.5;
}

/* ---- Ready state (right half, state 3) ---- */
.es-ready {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem 1.75rem;
}
.es-ready__inner { text-align: center; }
.es-ready__count { font-size: 0.8125rem; color: var(--partner-gray-6); margin-bottom: 0.25rem; }
.es-ready__eui { font-size: 0.8125rem; color: var(--partner-gray-7); margin-bottom: 1rem; }
.es-ready__eui-val { font-weight: 600; color: var(--partner-green-7); }
.es-ready__eui-pct { font-size: 0.6875rem; color: var(--partner-green-7); }

/* ---- Calculate / Recalculate buttons ---- */
.es-btn {
  background: var(--partner-blue-7);
  color: var(--partner-white, #fff);
  border: none;
  padding: 0.625rem 1.5rem;
  border-radius: var(--partner-radius-lg);
  font-size: 0.8125rem;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 1px 3px rgba(0, 81, 153, 0.25);
}
.es-btn:hover { background: var(--partner-blue-8); }
.es-btn--outline {
  background: transparent;
  color: var(--partner-blue-7);
  border: 1px solid var(--partner-blue-7);
  box-shadow: none;
  padding: 0.3125rem 0.875rem;
  font-size: 0.6875rem;
  margin-top: 0.625rem;
}
.es-btn--outline:hover { background: var(--partner-blue-1); }

/* ---- Projected half (green treatment) ---- */
.es-half--projected {
  background: linear-gradient(135deg, var(--partner-green-1) 0%, var(--partner-white, #fff) 100%);
  border-radius: 0 var(--partner-radius-lg) var(--partner-radius-lg) 0;
}

/* ---- Arrow divider (state 4) ---- */
.es-arrow-divider {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 0 0.375rem;
  position: relative;
}
.es-arrow-divider__line {
  width: 1px;
  background: var(--partner-gray-2);
  position: absolute;
  top: 1.25rem;
  bottom: 1.25rem;
}
.es-arrow-divider__circle {
  background: var(--partner-white, #fff);
  border: 1px solid var(--partner-gray-2);
  border-radius: 50%;
  width: 2rem;
  height: 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  z-index: 1;
  font-size: 1rem;
  color: var(--partner-green-7);
}
.es-arrow-divider__delta {
  font-size: 0.625rem;
  font-weight: 600;
  color: var(--partner-green-7);
  margin-top: 0.25rem;
  position: relative;
  z-index: 1;
  background: var(--partner-white, #fff);
  padding: 0 0.25rem;
}

/* ---- Responsive ---- */
@media (max-width: 640px) {
  .es-split { flex-direction: column; }
  .es-half { flex-direction: column; }
  .es-divider {
    width: auto;
    height: 1px;
    margin: 0 1.25rem;
  }
  .es-arrow-divider {
    flex-direction: row;
    padding: 0.375rem 0;
  }
  .es-arrow-divider__line {
    width: auto;
    height: 1px;
    top: auto;
    bottom: auto;
    left: 1.25rem;
    right: 1.25rem;
  }
  .es-gauge { margin: 0 auto; }
  .es-metrics__cards { flex-direction: column; }
  .es-half--projected {
    border-radius: 0 0 var(--partner-radius-lg) var(--partner-radius-lg);
  }
}
</style>
