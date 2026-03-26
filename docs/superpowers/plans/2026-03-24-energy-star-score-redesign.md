# Energy Star Score UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Energy Star Score card's KPI chips with a linear zone gauge, fix the button border-radius, and patch a null-safety bug in projected EUI calculation for older saved assessments.

**Architecture:** Two isolated changes: (1) a one-line→block fix in `useMeasureSelections.js`; (2) a full rewrite of `EnergyStarScore.vue`'s script helpers, template, and CSS. No new files, no backend changes, no routing changes.

**Tech Stack:** Vue 3 Composition API, inline SVG, scoped CSS, Partner Design System tokens

**Spec:** `docs/superpowers/specs/2026-03-24-energy-star-score-redesign.md`
**Approved mockup:** `.superpowers/brainstorm/35258-1774406385/linear-gauge-v6.html`

---

## File Map

| File | Change |
|---|---|
| `frontend/src/composables/useMeasureSelections.js` | Fix lines 60–68: add `savings_by_fuel` proportional fallback |
| `frontend/src/components/EnergyStarScore.vue` | Full rewrite of script helpers, template, and CSS |

---

## Task 1: Fix `projectedEui` for saved assessments missing `savings_by_fuel`

**Files:**
- Modify: `frontend/src/composables/useMeasureSelections.js:60-68`

**Context:** Older saved assessments have `savings_by_fuel: null` on measures (the field was added to the schema after those assessments were saved). Line 62 silently skips the measure with `if (!m?.savings_by_fuel) continue`, producing 0% savings even when `savings_kbtu_sf` is correct.

- [ ] **Step 1: Read the buggy block**

Open `frontend/src/composables/useMeasureSelections.js` and locate the `projectedEui` computed (lines 49–86). The bug is in the `for` loop at lines 60–68:

```js
for (const uid of selectedUpgradeIds.value) {
  const m = measures.value.find(m => m.upgrade_id === uid)
  if (!m?.savings_by_fuel) continue   // ← BUG: skips the whole measure if null
  elec -= m.savings_by_fuel.electricity
  gas -= m.savings_by_fuel.natural_gas
  oil -= m.savings_by_fuel.fuel_oil
  propane -= m.savings_by_fuel.propane
  district -= m.savings_by_fuel.district_heating
}
```

- [ ] **Step 2: Replace the loop with the guarded fallback**

Replace the entire `for` loop (lines 60–68) with:

```js
for (const uid of selectedUpgradeIds.value) {
  const m = measures.value.find(m => m.upgrade_id === uid)
  if (!m) continue

  if (m.savings_by_fuel) {
    elec     -= m.savings_by_fuel.electricity
    gas      -= m.savings_by_fuel.natural_gas
    oil      -= m.savings_by_fuel.fuel_oil
    propane  -= m.savings_by_fuel.propane
    district -= m.savings_by_fuel.district_heating
  } else if (m.savings_kbtu_sf != null && baseline.value.total_eui_kbtu_sf > 0) {
    // Proportional fallback for older saved assessments that predate savings_by_fuel
    const ratio = m.savings_kbtu_sf / baseline.value.total_eui_kbtu_sf
    elec     -= baseByFuel.electricity      * ratio
    gas      -= baseByFuel.natural_gas      * ratio
    oil      -= baseByFuel.fuel_oil         * ratio
    propane  -= baseByFuel.propane          * ratio
    district -= baseByFuel.district_heating * ratio
  }
}
```

- [ ] **Step 3: Verify no other references to `savings_by_fuel` need the same treatment**

Run:
```bash
grep -n "savings_by_fuel" frontend/src/composables/useMeasureSelections.js
```
Expected: the block you just edited is the only occurrence.

- [ ] **Step 4: Commit**

```bash
cd "frontend"
git add src/composables/useMeasureSelections.js
git commit -m "fix: proportional fallback for savings_by_fuel null in older assessments"
```

---

## Task 2: Rewrite `EnergyStarScore.vue`

**Files:**
- Modify: `frontend/src/components/EnergyStarScore.vue`

This task rewrites three sections of the SFC: script helpers, template, and CSS. Read the full current file before starting (595 lines).

### Step-by-step

- [ ] **Step 1: Read the current file**

```bash
# Confirm the file and line count
wc -l frontend/src/components/EnergyStarScore.vue
```

Open `frontend/src/components/EnergyStarScore.vue`. The file has three sections: `<script setup>`, `<template>`, and `<style scoped>`. You will replace all three sections in subsequent steps.

---

- [ ] **Step 2: Replace the `<script setup>` block**

Replace the entire `<script setup>` section (lines 1–63) with:

```vue
<script setup>
import { computed } from 'vue'
import { PTypography, PIcon } from '@partnerdevops/partner-components'
import { useEnergyStarScore } from '../composables/useEnergyStarScore'

const props = defineProps({
  building: { type: Object, required: true },
  baseline: { type: Object, required: true },
  address: { type: String, default: null },
  selectedCount: { type: Number, default: 0 },
  projectedEui: { type: Object, default: null },
  projectedEspm: { type: Object, default: null },
  projectedLoading: { type: Boolean, default: false },
  projectedError: { type: String, default: null },
})

const emit = defineEmits(['calculate-projected'])

const { loading, error, result, fetchScore } = useEnergyStarScore()

function handleClick() {
  fetchScore(props.building, props.baseline, props.address)
}

function formatNumber(value) {
  return value.toLocaleString('en-US', { maximumFractionDigits: 1 })
}

// ---- State machine ----
// 'trigger'           → baseline not yet fetched
// 'baseline-only'     → baseline fetched, no projected score
// 'measures-selected' → measures chosen, no projected score yet
// 'projected'         → projected score available
const scoreState = computed(() => {
  if (!result.value) return 'trigger'
  if (props.projectedEspm) return 'projected'
  if ((props.selectedCount ?? 0) > 0) return 'measures-selected'
  return 'baseline-only'
})

// ---- Zone color: thresholds at 65 / 30 ----
function zoneColor(score) {
  if (score == null) return 'var(--partner-gray-5)'
  if (score >= 65) return 'var(--partner-green-7)'
  if (score >= 30) return 'var(--partner-yellow-7)'
  return 'var(--partner-orange-7)'
}

// Callout CSS modifier class for projected pointer/callout (baseline is always blue)
function projectedColorClass(score, prefix) {
  if (score == null || score < 30) return `${prefix}--orange`
  if (score < 65) return `${prefix}--amber`
  return `${prefix}--green`
}

// ---- Gauge circumference: r=42, viewBox 100×100 → 2π×42 ≈ 263.9 ----
function scoreDasharray(score) {
  if (score == null) return '0 263.9'
  return `${(score / 100) * 263.9} 263.9`
}

// ---- Score positions as percentage strings for :style left ----
const baselineScorePct = computed(() =>
  result.value?.score != null ? result.value.score + '%' : '0%'
)
const projectedScorePct = computed(() =>
  props.projectedEspm?.score != null ? props.projectedEspm.score + '%' : '0%'
)

// ---- Close-score: projected within 5 pts of baseline → move label below track ----
const isCloseScore = computed(() => {
  if (scoreState.value !== 'projected') return false
  const base = result.value?.score ?? 0
  const proj = props.projectedEspm?.score ?? 0
  return Math.abs(proj - base) <= 5  // ≤5 matches spec's "~5 pts" language
})

// ---- Green gradient on left panel only when projected score ≥ 65 ----
const isImproving = computed(() =>
  scoreState.value === 'projected' && (props.projectedEspm?.score ?? 0) >= 65
)

// ---- Arrow: delta direction and color ----
const scoreDelta = computed(() => {
  if (!result.value?.score || !props.projectedEspm?.score) return null
  return props.projectedEspm.score - result.value.score
})

// SVG arrow stroke color (gray when no projected, zone-colored when projected)
const arrowStroke = computed(() => {
  if (scoreState.value !== 'projected') return 'var(--partner-gray-3)'
  return zoneColor(props.projectedEspm?.score)
})

// ---- Right-panel EUI stat ----
// Color = zone color of projected if reduction is positive, orange if EUI increased
const euiStatColor = computed(() => {
  if (!props.projectedEui) return 'var(--partner-gray-7)'
  return props.projectedEui.reduction_pct >= 0
    ? zoneColor(props.projectedEspm?.score)
    : 'var(--partner-orange-7)'
})
// Label changes to "EUI change" when EUI increased
const euiStatLabel = computed(() =>
  props.projectedEui?.reduction_pct < 0 ? 'EUI change' : 'EUI reduction'
)
// Value: positive reduction shown as "X.X%", increase as "−X.X%"
const euiStatValue = computed(() => {
  if (!props.projectedEui) return '—'
  const r = props.projectedEui.reduction_pct
  return r < 0
    ? `\u2212${Math.abs(r).toFixed(1)}%`
    : `${r.toFixed(1)}%`
})
</script>
```

---

- [ ] **Step 3: Replace the `<template>` block**

Replace the entire `<template>` section (lines 65–277) with:

```vue
<template>
  <div class="es-section">
    <!-- State: Trigger (no baseline score yet) -->
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

    <!-- Loading: baseline -->
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

    <!-- Error: baseline -->
    <div v-else-if="error" class="es-card es-card--error">
      <PTypography variant="body2" class="es-error-text">{{ error }}</PTypography>
      <button class="es-retry-btn" @click="handleClick">Retry</button>
    </div>

    <!-- States 2–4: 3/4 + 1/4 permanent layout -->
    <div v-else-if="result" class="es-card es-split">

      <!-- LEFT 3/4: donut pair + linear gauge -->
      <div class="es-main" :class="{ 'es-main--improving': isImproving }">

        <!-- Donut column -->
        <div class="donut-col">
          <!-- Percentile headline (muted, above donuts) -->
          <div
            v-if="result.eligible && result.percentile_text"
            class="es-headline"
          >{{ result.percentile_text }}</div>
          <div v-else class="es-headline es-headline--muted">
            Score not available for this building type
          </div>

          <!-- Donut pair: baseline ← arrow → projected/placeholder -->
          <div class="donut-pair">

            <!-- Baseline donut -->
            <div class="donut-wrap">
              <svg width="110" height="110" viewBox="0 0 100 100" class="donut-svg">
                <circle cx="50" cy="50" r="42" fill="none" stroke="var(--partner-gray-2)" stroke-width="7"/>
                <circle
                  v-if="result.eligible && result.score != null"
                  cx="50" cy="50" r="42" fill="none"
                  :stroke="zoneColor(result.score)"
                  stroke-width="7" stroke-linecap="round"
                  :stroke-dasharray="scoreDasharray(result.score)"
                  transform="rotate(-90 50 50)"
                />
                <text
                  x="50" y="45"
                  text-anchor="middle" dominant-baseline="middle"
                  font-size="24" font-weight="700"
                  :fill="result.eligible && result.score != null ? zoneColor(result.score) : '#A6ADB4'"
                >{{ result.eligible && result.score != null ? result.score : '—' }}</text>
                <text
                  x="50" y="62"
                  text-anchor="middle" dominant-baseline="middle"
                  font-size="7" fill="#A6ADB4"
                >out of 100</text>
              </svg>
              <div class="donut-caption">Baseline Score</div>
            </div>

            <!-- SVG arrow (faint in state 1, colored with badge in state 2) -->
            <div class="donut-arrow" :style="{ opacity: scoreState === 'projected' ? 1 : 0.2 }">
              <svg width="26" height="18" viewBox="0 0 26 18" fill="none" class="arrow-svg">
                <path
                  d="M2 9H22M16 3L22 9L16 15"
                  :stroke="arrowStroke"
                  stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"
                />
              </svg>
              <div
                v-if="scoreState === 'projected' && scoreDelta != null"
                class="donut-arrow__badge"
                :style="(() => {
                  const s = props.projectedEspm?.score
                  if (s == null || s < 30) return { background: 'var(--partner-orange-1, #FFF1EE)', color: 'var(--partner-orange-7)', border: '1px solid var(--partner-orange-3)' }
                  if (s < 65)             return { background: 'var(--partner-yellow-1)', color: 'var(--partner-yellow-8, #C46F00)', border: '1px solid var(--partner-yellow-2)' }
                  return                         { background: 'var(--partner-green-1)', color: 'var(--partner-green-7)', border: '1px solid var(--partner-green-3)' }
                })()"
              >{{ scoreDelta > 0 ? '▲' : '▼' }} {{ scoreDelta > 0 ? '+' : '' }}{{ scoreDelta }} pt{{ Math.abs(scoreDelta) === 1 ? '' : 's' }}</div>
            </div>

            <!-- Projected donut (or dashed placeholder) -->
            <div class="donut-wrap">
              <template v-if="scoreState === 'projected' && props.projectedEspm?.score != null">
                <svg width="110" height="110" viewBox="0 0 100 100" class="donut-svg">
                  <circle cx="50" cy="50" r="42" fill="none" stroke="var(--partner-gray-2)" stroke-width="7"/>
                  <circle
                    cx="50" cy="50" r="42" fill="none"
                    :stroke="zoneColor(props.projectedEspm.score)"
                    stroke-width="7" stroke-linecap="round"
                    :stroke-dasharray="scoreDasharray(props.projectedEspm.score)"
                    transform="rotate(-90 50 50)"
                  />
                  <text
                    x="50" y="45"
                    text-anchor="middle" dominant-baseline="middle"
                    font-size="24" font-weight="700"
                    :fill="zoneColor(props.projectedEspm.score)"
                  >{{ props.projectedEspm.score }}</text>
                  <text
                    x="50" y="62"
                    text-anchor="middle" dominant-baseline="middle"
                    font-size="7" fill="#A6ADB4"
                  >out of 100</text>
                </svg>
                <div class="donut-caption" :style="{ color: zoneColor(props.projectedEspm.score) }">Projected Score</div>
              </template>
              <template v-else>
                <div class="donut-placeholder">—</div>
                <div class="donut-caption donut-caption--muted">Projected</div>
              </template>
            </div>

          </div><!-- /donut-pair -->
        </div><!-- /donut-col -->

        <!-- Linear gauge -->
        <div class="lg-panel">

          <!-- Above-track: callout + optional baseline label (normal placement) -->
          <div class="lg-above">
            <!-- Baseline label above track (post-retrofit, non-close-score only) -->
            <div
              v-if="scoreState === 'projected' && !isCloseScore"
              class="lg-baseline-label"
              :style="{ left: baselineScorePct }"
            >{{ result.score }} baseline</div>

            <!-- Main callout (baseline score in state 1; projected score in state 2) -->
            <div
              class="lg-callout"
              :class="scoreState === 'projected'
                ? projectedColorClass(props.projectedEspm?.score, 'lg-callout')
                : 'lg-callout--blue'"
              :style="{ left: scoreState === 'projected' ? projectedScorePct : baselineScorePct }"
            >
              <span class="lg-c-score">{{
                scoreState === 'projected' ? props.projectedEspm.score : result.score
              }}</span>
              <span class="lg-c-eui">{{
                scoreState === 'projected'
                  ? (props.projectedEui?.total_eui_kbtu_sf?.toFixed(1) ?? '—') + ' kBtu/sf · Projected EUI'
                  : (result.design_eui_kbtu_sf != null ? formatNumber(result.design_eui_kbtu_sf) : '—') + ' kBtu/sf · Calculated EUI'
              }}</span>
            </div>

            <!-- Connector line from callout down to track -->
            <div
              class="lg-connector"
              :class="scoreState === 'projected'
                ? projectedColorClass(props.projectedEspm?.score, 'lg-connector')
                : 'lg-connector--blue'"
              :style="{ left: scoreState === 'projected' ? projectedScorePct : baselineScorePct }"
            ></div>
          </div>

          <!-- Track + pointers + blue baseline dot -->
          <div class="lg-track-wrap">
            <!-- Projected pointer triangle (state 2 only) -->
            <div
              v-if="scoreState === 'projected'"
              class="lg-ptr"
              :class="projectedColorClass(props.projectedEspm?.score, 'lg-ptr')"
              :style="{ left: projectedScorePct }"
            ></div>
            <!-- Baseline pointer triangle (state 1 only) -->
            <div
              v-else
              class="lg-ptr lg-ptr--blue"
              :style="{ left: baselineScorePct }"
            ></div>

            <!-- Zone track -->
            <div class="lg-track">
              <div class="lg-z lg-z--lo"></div>
              <div class="lg-z lg-z--md"></div>
              <div class="lg-z lg-z--hi"></div>
            </div>

            <!-- Blue baseline dot (state 2 only) -->
            <div
              v-if="scoreState === 'projected'"
              class="lg-baseline-dot"
              :style="{ left: baselineScorePct }"
            ></div>

            <!-- Baseline label below track (close-score only) -->
            <div
              v-if="scoreState === 'projected' && isCloseScore"
              class="lg-baseline-label--below"
              :style="{ left: baselineScorePct }"
            >← {{ result.score }} baseline</div>
          </div>

          <!-- Scale ticks -->
          <div class="lg-scale" :class="{ 'lg-scale--extra-top': isCloseScore }">
            <div class="lg-tick" style="left:0%"><div class="lg-tick-line"></div><div class="lg-tick-num">0</div></div>
            <div class="lg-tick" style="left:30%"><div class="lg-tick-line"></div><div class="lg-tick-num">30</div></div>
            <div class="lg-tick" style="left:65%"><div class="lg-tick-line"></div><div class="lg-tick-num">65</div></div>
            <div class="lg-tick lg-tick--star" style="left:75%">
              <div class="lg-tick-line lg-tick-line--green"></div>
              <div class="lg-tick-num lg-tick-num--star">75 ★</div>
            </div>
            <div class="lg-tick" style="left:100%"><div class="lg-tick-line"></div><div class="lg-tick-num">100</div></div>
          </div>

          <!-- EUI annotations -->
          <div class="lg-ann-row">
            <div v-if="result.median_eui_kbtu_sf != null" class="lg-ann lg-ann--med" style="left:50%">
              <div class="lg-ann-line"></div>
              <span class="lg-ann-name">Median EUI</span>
              <span class="lg-ann-val">{{ formatNumber(result.median_eui_kbtu_sf) }} kBtu/sf</span>
            </div>
            <div v-if="result.target_eui_kbtu_sf != null" class="lg-ann lg-ann--tgt" style="left:75%">
              <div class="lg-ann-line"></div>
              <span class="lg-ann-name">Target EUI ★</span>
              <span class="lg-ann-val">{{ formatNumber(result.target_eui_kbtu_sf) }} kBtu/sf</span>
            </div>
          </div>

          <PTypography variant="body2" class="es-prop-type">
            ESPM property type: {{ result.espm_property_type }}
          </PTypography>
        </div><!-- /lg-panel -->

      </div><!-- /es-main -->

      <!-- RIGHT 1/4: action panel -->
      <div class="es-side">

        <!-- Loading: projected -->
        <template v-if="projectedLoading">
          <div class="es-loading-spinner es-loading-spinner--small">
            <svg viewBox="0 0 50 50">
              <circle cx="25" cy="25" r="20" fill="none" stroke-width="4" stroke="var(--partner-gray-2)" />
              <circle cx="25" cy="25" r="20" fill="none" stroke-width="4" stroke="var(--partner-blue-7)"
                      stroke-linecap="round" stroke-dasharray="80, 200" />
            </svg>
          </div>
          <div class="side-hint">Calculating projected score...</div>
        </template>

        <!-- Error: projected -->
        <template v-else-if="projectedError">
          <PTypography variant="body2" class="es-error-text">{{ projectedError }}</PTypography>
          <button class="es-retry-btn" @click="emit('calculate-projected')">Retry</button>
        </template>

        <!-- State 2: projected score available -->
        <template v-else-if="scoreState === 'projected'">
          <div class="side-stat">
            <div class="side-stat__val" :style="{ color: euiStatColor }">{{ euiStatValue }}</div>
            <div class="side-stat__lbl">{{ euiStatLabel }}</div>
          </div>
          <div class="side-div"></div>
          <div class="side-stat side-stat--secondary">
            <div class="side-stat__val">{{ props.projectedEui?.total_eui_kbtu_sf?.toFixed(1) }} kBtu/sf</div>
            <div class="side-stat__lbl">projected EUI</div>
          </div>
          <button class="es-btn es-btn--sm-outline" @click="emit('calculate-projected')">&#8635; Recalculate</button>
        </template>

        <!-- State 1 / no projected score: Calculate prompt -->
        <template v-else>
          <div class="side-icon">&#11088;</div>
          <div class="side-hint">Select upgrades below, then calculate your projected score</div>
          <button
            class="es-btn"
            :disabled="selectedCount === 0"
            @click="emit('calculate-projected')"
          >&#11088; Calculate</button>
        </template>

      </div><!-- /es-side -->

    </div><!-- /es-split -->
  </div>
</template>
```

---

- [ ] **Step 4: Replace the `<style scoped>` block**

Replace the entire `<style scoped>` section (lines 279–594) with:

```vue
<style scoped>
/* ---- Token fallbacks for tokens not yet in partner-components ---- */
/* Remove once --partner-yellow-8 and --partner-orange-1 are published */
:root {
  --partner-yellow-8: #C46F00;
  --partner-orange-1: #FFF1EE;
}

/* Root wrapper — no visual styles, structural hook only */
.es-section { display: block; }

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
  padding: 1.25rem 1.5rem;
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
.es-retry-btn:hover { background: var(--partner-gray-1); border-color: var(--partner-gray-3); }

/* ──────────────────────────
   SPLIT LAYOUT: 3/4 + 1/4
────────────────────────── */
.es-split {
  display: flex;
  overflow: hidden;
}

/* Left 3/4: donut pair + linear gauge in a single row */
.es-main {
  flex: 3;
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 1.25rem;
  padding: 1.125rem 1.25rem;
  transition: background 0.5s ease;
}
/* Green gradient — only when projected score ≥ 65 */
.es-main--improving {
  background: linear-gradient(130deg, var(--partner-white, #fff) 30%, #E9F7EA 100%);
}

/* Right 1/4: action panel */
.es-side {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 1rem 0.875rem;
  border-left: 1px solid var(--partner-gray-2);
  text-align: center;
}

/* ──────────────────────────
   DONUT COLUMN
────────────────────────── */
.donut-col {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex-shrink: 0;
}
/* Muted percentile headline above donuts */
.es-headline {
  font-size: 0.6875rem;
  font-weight: 500;
  color: var(--partner-gray-5);
  line-height: 1.3;
}
.es-headline--muted { color: var(--partner-gray-4); }

/* Donut pair: baseline — arrow — projected */
.donut-pair {
  display: flex;
  align-items: center;
  gap: 0;
}
.donut-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.donut-svg { display: block; }

.donut-caption {
  font-size: 0.5625rem;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--partner-gray-6);
  font-weight: 600;
  margin-top: 4px;
}
.donut-caption--muted { color: var(--partner-gray-4); }

/* Dashed placeholder circle for projected (state 1) */
.donut-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 110px;
  height: 110px;
  border-radius: 50%;
  border: 5px dashed var(--partner-gray-3);
  color: var(--partner-gray-4);
  font-size: 1.125rem;
}

/* Arrow between donuts */
.donut-arrow {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 0 10px;
  margin-top: -6px;
}
.arrow-svg { display: block; }
.donut-arrow__badge {
  border-radius: var(--partner-radius-sm);
  padding: 2px 6px;
  font-size: 0.5rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  white-space: nowrap;
}

/* ──────────────────────────
   LINEAR GAUGE
   Zones: Low 0–30 (30%) | Moderate 30–65 (35%) | High 65–100 (35%)
   ENERGY STAR band: score 75–100 = 71.4% of High zone
────────────────────────── */
.lg-panel {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

/* Above-track area: callout + optional baseline label */
.lg-above {
  position: relative;
  height: 46px;
}

/* Callout box */
.lg-callout {
  position: absolute;
  top: 0;
  transform: translateX(-50%);
  border-radius: var(--partner-radius-md);
  padding: 4px 10px 5px;
  text-align: center;
  white-space: nowrap;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.09);
  animation: lg-drop-in 0.3s ease-out both;
}
.lg-c-score { font-size: 1rem; font-weight: 700; display: block; line-height: 1.1; }
.lg-c-eui   { font-size: 0.5625rem; font-weight: 500; display: block; margin-top: 1px; opacity: 0.85; }

/* Callout color variants */
.lg-callout--blue   { background: var(--partner-blue-1);   border: 1px solid var(--partner-blue-7); }
.lg-callout--blue   .lg-c-score,
.lg-callout--blue   .lg-c-eui   { color: var(--partner-blue-7); }

.lg-callout--amber  { background: var(--partner-yellow-1); border: 1px solid var(--partner-yellow-7); }
.lg-callout--amber  .lg-c-score,
.lg-callout--amber  .lg-c-eui   { color: var(--partner-yellow-8, #C46F00); }

.lg-callout--green  { background: var(--partner-green-1);  border: 1px solid var(--partner-green-7); }
.lg-callout--green  .lg-c-score,
.lg-callout--green  .lg-c-eui   { color: var(--partner-green-7); }

.lg-callout--orange { background: var(--partner-orange-1, #FFF1EE); border: 1px solid var(--partner-orange-7); }
.lg-callout--orange .lg-c-score,
.lg-callout--orange .lg-c-eui   { color: var(--partner-orange-7); }

/* Connector line: callout → track */
.lg-connector {
  position: absolute;
  transform: translateX(-50%);
  bottom: 0;
  width: 1.5px;
  height: 7px;
}
.lg-connector--blue   { background: var(--partner-blue-7); }
.lg-connector--amber  { background: var(--partner-yellow-7); }
.lg-connector--green  { background: var(--partner-green-7); }
.lg-connector--orange { background: var(--partner-orange-7); }

/* Baseline label above track (non-close-score state 2) */
.lg-baseline-label {
  position: absolute;
  transform: translateX(-50%);
  top: 16px;
  white-space: nowrap;
  font-size: 0.625rem;
  font-weight: 600;
  color: var(--partner-gray-6);
}

/* Track area */
.lg-track-wrap { position: relative; }

/* Pointer triangle: sits above track, points down.
   top: -6px raises the triangle clear of the track surface so it reads
   as floating above the zone bar rather than flush with its top edge. */
.lg-ptr {
  position: absolute;
  transform: translateX(-50%);
  top: -6px;
  width: 0;
  height: 0;
  border-left: 5px solid transparent;
  border-right: 5px solid transparent;
  z-index: 6;
}
.lg-ptr--blue   { border-top: 6px solid var(--partner-blue-7); }
.lg-ptr--amber  { border-top: 6px solid var(--partner-yellow-7); }
.lg-ptr--green  { border-top: 6px solid var(--partner-green-7); }
.lg-ptr--orange { border-top: 6px solid var(--partner-orange-7); }

/* Zone track bar */
.lg-track {
  display: flex;
  height: 20px;
  border-radius: var(--partner-radius-sm);
  overflow: hidden;
}
.lg-z { flex-shrink: 0; }
.lg-z--lo { width: 30%; background: var(--partner-orange-3); }
.lg-z--md {
  width: 35%;
  background: var(--partner-yellow-2);
  border-left: 1px solid rgba(255, 255, 255, 0.5);
  border-right: 1px solid rgba(255, 255, 255, 0.5);
}
.lg-z--hi {
  width: 35%;
  background: var(--partner-green-2);
  position: relative;
  overflow: hidden;
}
/* ENERGY STAR band overlay: score 75–100 = 71.4% of the High zone width */
.lg-z--hi::after {
  content: '';
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  width: 71.4%;
  background: var(--partner-green-3);
  opacity: 0.5;
  border-left: 1.5px dashed rgba(31, 107, 35, 0.4);
}

/* Blue baseline dot (14×14px solid) — shown in post-retrofit state */
.lg-baseline-dot {
  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--partner-blue-7);
  z-index: 8;
}

/* Baseline label below track (close-score only — avoids overlap) */
.lg-baseline-label--below {
  position: absolute;
  top: 100%;
  transform: translateX(-50%);
  margin-top: 3px;
  white-space: nowrap;
  font-size: 0.625rem;
  font-weight: 600;
  color: var(--partner-gray-6);
}

/* Scale ticks */
.lg-scale {
  position: relative;
  height: 14px;
  margin-top: 1px;
}
/* Extra top margin when below-track label needs clearance */
.lg-scale--extra-top { margin-top: 12px; }

.lg-tick {
  position: absolute;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
}
.lg-tick-line { width: 1px; height: 4px; background: var(--partner-gray-4); }
.lg-tick-line--green { background: var(--partner-green-7); }
.lg-tick-num  { font-size: 0.5rem; color: var(--partner-gray-5); margin-top: 1px; white-space: nowrap; }
.lg-tick-num--star { color: var(--partner-green-7); font-weight: 600; }

/* EUI annotation row */
.lg-ann-row {
  position: relative;
  height: 30px;
  margin-top: 2px;
}
.lg-ann {
  position: absolute;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  white-space: nowrap;
}
.lg-ann-line { width: 1px; height: 5px; }
.lg-ann-name { font-size: 0.5rem; text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600; display: block; margin-top: 1px; }
.lg-ann-val  { font-size: 0.5625rem; font-weight: 700; display: block; line-height: 1.2; }

.lg-ann--med .lg-ann-line { background: var(--partner-gray-4); }
.lg-ann--med .lg-ann-name,
.lg-ann--med .lg-ann-val  { color: var(--partner-gray-6); }

.lg-ann--tgt .lg-ann-line { background: var(--partner-green-7); }
.lg-ann--tgt .lg-ann-name,
.lg-ann--tgt .lg-ann-val  { color: var(--partner-green-7); }

/* ESPM property type footer */
.es-prop-type {
  color: var(--partner-gray-5);
  margin-top: 4px;
}

/* ──────────────────────────
   RIGHT PANEL (es-side)
────────────────────────── */
.side-icon  { font-size: 1.125rem; opacity: 0.2; }
.side-hint  { font-size: 0.6875rem; font-weight: 500; color: var(--partner-gray-6); line-height: 1.45; max-width: 130px; }
.side-stat  { display: flex; flex-direction: column; align-items: center; gap: 1px; }
.side-stat__val { font-size: 1.25rem; font-weight: 700; line-height: 1; }
.side-stat__lbl { font-size: 0.5625rem; color: var(--partner-gray-5); text-transform: uppercase; letter-spacing: 0.05em; }
.side-stat--secondary .side-stat__val { font-size: 1rem; color: var(--partner-gray-7); }
.side-div   { width: 70%; height: 1px; background: var(--partner-gray-2); }

/* ---- Calculate / Recalculate buttons ---- */
/* border-radius uses --partner-radius-sm (2px) per design system spec */
.es-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  width: 100%;
  max-width: 150px;
  background: var(--partner-blue-7);
  color: var(--partner-white, #fff);
  border: none;
  border-radius: var(--partner-radius-sm);
  height: 32px;
  padding: 0 10px;
  font-size: 0.75rem;
  font-weight: 500;
  cursor: pointer;
}
.es-btn:hover:not(:disabled) { background: var(--partner-blue-8); }
.es-btn:disabled { opacity: 0.45; cursor: not-allowed; }

.es-btn--sm-outline {
  background: transparent;
  border: 1px solid var(--partner-blue-7);
  color: var(--partner-blue-7);
  height: 26px;
  font-size: 0.6875rem;
  max-width: 130px;
}
.es-btn--sm-outline:hover { background: var(--partner-blue-1); }

/* ---- Animations ---- */
@keyframes lg-drop-in {
  from { opacity: 0; transform: translateX(-50%) translateY(-4px); }
  to   { opacity: 1; transform: translateX(-50%) translateY(0); }
}
</style>
```

---

- [ ] **Step 5: Verify the file renders correctly in the dev server**

```bash
cd frontend && npm run dev
```

Open the app in a browser. Navigate to a building assessment with an ENERGY STAR score. Confirm:

**Baseline-only state:**
- [ ] 3/4 + 1/4 split is always visible
- [ ] Left: baseline donut (colored by zone) + dashed placeholder donut + faint gray arrow
- [ ] Left: linear gauge with blue callout and blue pointer triangle at baseline score
- [ ] Right: faint star icon + hint text + disabled Calculate button (if no measures selected)

**Measures-selected state:**
- [ ] Same as baseline-only but Calculate button is enabled

**Projected state (score ≥ 65):**
- [ ] Green gradient on left panel background
- [ ] Both donuts filled, arrow colored green, delta badge shows "▲ +N pts"
- [ ] Linear gauge: blue dot at baseline position, green callout + green pointer at projected position
- [ ] "N baseline" label above track
- [ ] Right panel: EUI stat in green, side-div, projected EUI, Recalculate button

**Projected state (score 30–64):**
- [ ] No green gradient on left panel
- [ ] Arrow and callout colored amber/yellow
- [ ] Right panel stat colored amber if reduction > 0, orange if EUI increased

**Close-score state (|projected - baseline| ≤ 5):**
- [ ] "← N baseline" label appears below the track (not above)
- [ ] Scale row has extra top margin
- [ ] Callout still appears above track at projected position

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/EnergyStarScore.vue
git commit -m "feat: replace KPI chips with linear gauge, fix button radius, rename 'Your EUI' to 'Calculated EUI'"
```

---

## Notes for implementer

- **SVG text in Vue:** The `<text>` elements use inline `font-size`, `font-weight`, and `fill` attributes. Do not use scoped CSS to style SVG text — scoped selectors don't reliably target SVG child elements.
- **`dominant-baseline`** may not render identically across all browsers. If the donut text appears off-center, adjust the `y` attribute (baseline score at y=45, "out of 100" at y=62 within the 100-unit viewBox has been validated in the mockup).
- **No automated tests** exist for `EnergyStarScore.vue` or `useMeasureSelections.js` at the app level (Vitest is configured only in `partner-components`). Verification is manual via the dev server checklist in Step 5.
