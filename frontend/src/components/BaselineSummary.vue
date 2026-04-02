<script setup>
import { computed } from 'vue'
import { PTypography, PTooltip } from '@partnerdevops/partner-components'
import EndUseDonut from './EndUseDonut.vue'

const KWH_TO_KBTU = 3.412
const THERM_TO_KBTU = 100

const props = defineProps({
  baseline: { type: Object, required: true },
  sqft: { type: Number, required: true },
  calibrated: { type: Boolean, default: false },
})

const fuelConfigs = [
  {
    key: 'electricity', label: 'Electricity', color: 'var(--partner-yellow-5)', badgeVariant: 'warning',
    displayUnit: { label: 'kWh', abbr: 'kWh', convert: (kbtu) => kbtu / KWH_TO_KBTU },
  },
  {
    key: 'natural_gas', label: 'Natural Gas', color: 'var(--partner-blue-5)', badgeVariant: 'primary',
    displayUnit: { label: 'therms', abbr: 'therms', convert: (kbtu) => kbtu / THERM_TO_KBTU },
  },
  { key: 'fuel_oil', label: 'Fuel Oil', color: 'var(--partner-orange-6)', badgeVariant: 'secondary' },
  { key: 'propane', label: 'Propane', color: 'var(--partner-red-5)', badgeVariant: 'error' },
  { key: 'district_heating', label: 'District Heating', color: 'var(--partner-blue-9)', badgeVariant: 'neutral' },
]

/** Only show fuels contributing more than 0.1 kBtu/sf */
const activeFuels = computed(() => {
  return fuelConfigs.filter(
    (fuel) => props.baseline.eui_by_fuel[fuel.key] > 0.1
  )
})

/** Total annual energy in kBtu */
const totalAnnualEnergy = computed(() => {
  return props.baseline.total_eui_kbtu_sf * props.sqft
})

/** Format large numbers with commas */
function formatNumber(value) {
  return Math.round(value).toLocaleString('en-US')
}

/** Percentage of total EUI for a given fuel */
function fuelPercent(key) {
  if (props.baseline.total_eui_kbtu_sf === 0) return 0
  return (props.baseline.eui_by_fuel[key] / props.baseline.total_eui_kbtu_sf) * 100
}

/** Total kBtu for a given fuel */
function fuelTotalKbtu(key) {
  return props.baseline.eui_by_fuel[key] * props.sqft
}

/** Get display value and unit for the right-side consumption list */
function fuelConsumption(fuel) {
  const totalKbtu = fuelTotalKbtu(fuel.key)
  if (fuel.displayUnit) {
    return {
      value: formatNumber(fuel.displayUnit.convert(totalKbtu)),
      unit: fuel.displayUnit.abbr,
    }
  }
  return { value: formatNumber(totalKbtu), unit: 'kBtu' }
}

/**
 * Visual width for stacked bar segments.
 * Enforce a minimum so tiny fuels remain hoverable.
 */
const MIN_BAR_PERCENT = 2.5

const barSegments = computed(() => {
  const fuels = activeFuels.value
  const rawPercents = fuels.map((f) => fuelPercent(f.key))

  // Count how many segments need boosting
  const boosted = rawPercents.map((p) => (p < MIN_BAR_PERCENT ? MIN_BAR_PERCENT : p))
  const boostedTotal = boosted.reduce((s, v) => s + v, 0)

  // Normalize so they sum to 100
  return fuels.map((fuel, i) => ({
    fuel,
    actualPercent: rawPercents[i] ?? 0,
    visualWidth: ((boosted[i] ?? 0) / boostedTotal) * 100,
  }))
})

/** End-use breakdown data from API (null if models not yet trained) */
const endUseBreakdown = computed(() => props.baseline.enduse_breakdown ?? null)

/* ---- Carbon Emissions ---- */

const DIRECT_FUELS = ['natural_gas', 'fuel_oil', 'propane']
const INDIRECT_FUELS = ['electricity', 'district_heating']

const emissionsData = computed(() => {
  const byFuel = props.baseline.emissions_by_fuel
  if (!byFuel) return null

  const direct = DIRECT_FUELS.reduce((sum, key) => sum + (byFuel[key] || 0), 0)
  const indirect = INDIRECT_FUELS.reduce((sum, key) => sum + (byFuel[key] || 0), 0)
  const total = direct + indirect

  if (total === 0) return null

  return { direct, indirect, total }
})

/** Total emissions in tCO2e (absolute) */
const totalEmissionsTco2e = computed(() => {
  if (!emissionsData.value) return null
  return (emissionsData.value.total * props.sqft) / 1000
})

const emissionsConfigs = [
  { key: 'direct', label: 'Direct', color: 'var(--partner-gray-7)' },
  { key: 'indirect', label: 'Indirect', color: 'var(--partner-blue-6)' },
]

const emissionsBarSegments = computed(() => {
  const data = emissionsData.value
  if (!data) return []

  // Only include segments with meaningful emissions
  const entries = emissionsConfigs
    .map((cfg) => ({
      config: cfg,
      value: cfg.key === 'direct' ? data.direct : data.indirect,
    }))
    .filter((e) => (e.value * props.sqft) / 1000 >= 0.05)

  if (entries.length === 0) return []

  const totalActive = entries.reduce((s, e) => s + e.value, 0)
  const rawPercents = entries.map((e) => (e.value / totalActive) * 100)
  const boosted = rawPercents.map((p) => (p < MIN_BAR_PERCENT ? MIN_BAR_PERCENT : p))
  const boostedTotal = boosted.reduce((s, v) => s + v, 0)

  return entries.map((e, i) => ({
    config: e.config,
    actualPercent: (e.value / data.total) * 100,
    visualWidth: ((boosted[i] ?? 0) / boostedTotal) * 100,
    tco2e: (e.value * props.sqft) / 1000,
  }))
})
</script>

<template>
  <div class="baseline-card">
    <!-- Header -->
    <div class="baseline-card__header">
      <PTypography variant="h4" class="baseline-card__title">
        Baseline Usage
      </PTypography>
      <span v-if="calibrated" class="calibrated-badge">Calibrated</span>
    </div>

    <!-- Two-column layout: left stats + bar + consumption, right donut -->
    <div :class="['baseline-layout', endUseBreakdown ? 'baseline-layout--with-donut' : '']">
      <!-- Left column -->
      <div class="baseline-layout__left">
        <PTypography variant="headline2" class="baseline-layout__section-title">
          Energy &amp; Carbon Profile
        </PTypography>

        <!-- Hero section: Total EUI + Total Annual -->
        <div class="baseline-hero">
          <div class="baseline-hero__primary">
            <span class="baseline-hero__value">
              {{ baseline.total_eui_kbtu_sf.toFixed(1) }}
            </span>
            <PTypography variant="body2" class="baseline-hero__unit">
              kBtu/sf total site EUI
            </PTypography>
          </div>

          <div class="baseline-hero__divider" aria-hidden="true"></div>

          <div class="baseline-hero__secondary">
            <span class="baseline-hero__annual-value">
              {{ formatNumber(totalAnnualEnergy) }}
            </span>
            <PTypography variant="body2" class="baseline-hero__annual-unit">
              kBtu/yr total annual energy
            </PTypography>
          </div>

          <template v-if="totalEmissionsTco2e != null">
            <div class="baseline-hero__divider" aria-hidden="true"></div>

            <div class="baseline-hero__secondary">
              <span class="baseline-hero__annual-value">
                {{ totalEmissionsTco2e.toFixed(1) }}
              </span>
              <PTypography variant="body2" class="baseline-hero__annual-unit">
                tCO2e total emissions
              </PTypography>
            </div>
          </template>
        </div>

        <!-- Stacked horizontal bar -->
        <div class="fuel-bar">
          <PTypography variant="headline2" class="fuel-bar__heading">
            Fuel Breakdown
          </PTypography>

          <div class="fuel-bar__track">
            <PTooltip
              v-for="seg in barSegments"
              :key="seg.fuel.key"
              direction="top"
            >
              <template #tooltip-trigger>
                <div
                  class="fuel-bar__segment"
                  :style="{
                    width: seg.visualWidth + '%',
                    backgroundColor: seg.fuel.color,
                  }"
                  role="img"
                  :aria-label="`${seg.fuel.label}: ${(seg.actualPercent ?? 0).toFixed(1)}%`"
                ></div>
              </template>
              <template #tooltip-content>
                <div class="fuel-bar__tooltip">
                  <span class="fuel-bar__tooltip-label">{{ seg.fuel.label }}</span>
                  <span class="fuel-bar__tooltip-pct">{{ (seg.actualPercent ?? 0).toFixed(1) }}%</span>
                  <span class="fuel-bar__tooltip-val">
                    {{ baseline.eui_by_fuel[seg.fuel.key].toFixed(1) }} kBtu/sf
                  </span>
                </div>
              </template>
            </PTooltip>
          </div>

          <!-- Legend dots -->
          <div class="fuel-bar__legend">
            <div
              v-for="seg in barSegments"
              :key="seg.fuel.key"
              class="fuel-bar__legend-item"
            >
              <span
                class="fuel-bar__legend-dot"
                :style="{ backgroundColor: seg.fuel.color }"
              ></span>
              <PTypography variant="body2" class="fuel-bar__legend-text">
                {{ seg.fuel.label }}
              </PTypography>
            </div>
          </div>
        </div>

        <!-- Annual consumption (below fuel bar) -->
        <div class="consumption-section">
          <PTypography variant="headline2" class="consumption-list__heading">
            Annual Consumption
          </PTypography>

          <div class="consumption-list">
            <div
              v-for="fuel in activeFuels"
              :key="fuel.key"
              class="consumption-item"
            >
              <div class="consumption-item__left">
                <span
                  class="consumption-item__dot"
                  :style="{ backgroundColor: fuel.color }"
                ></span>
                <PTypography variant="body2" class="consumption-item__label">
                  {{ fuel.label }}
                </PTypography>
              </div>
              <div class="consumption-item__right">
                <span class="consumption-item__value">
                  {{ fuelConsumption(fuel).value }}
                </span>
                <span class="consumption-item__unit">
                  {{ fuelConsumption(fuel).unit }}
                </span>
              </div>
            </div>
          </div>
        </div>
        <!-- Carbon Emissions bar -->
        <div v-if="emissionsBarSegments.length" class="emissions-bar">
          <PTypography variant="headline2" class="emissions-bar__heading">
            Carbon Emissions
          </PTypography>

          <div class="emissions-bar__track">
            <PTooltip
              v-for="seg in emissionsBarSegments"
              :key="seg.config.key"
              direction="top"
            >
              <template #tooltip-trigger>
                <div
                  class="emissions-bar__segment"
                  :style="{
                    width: seg.visualWidth + '%',
                    backgroundColor: seg.config.color,
                  }"
                  role="img"
                  :aria-label="`${seg.config.label}: ${(seg.actualPercent ?? 0).toFixed(1)}%`"
                ></div>
              </template>
              <template #tooltip-content>
                <div class="emissions-bar__tooltip">
                  <span class="emissions-bar__tooltip-label">{{ seg.config.label }}</span>
                  <span class="emissions-bar__tooltip-pct">{{ (seg.actualPercent ?? 0).toFixed(1) }}%</span>
                  <span class="emissions-bar__tooltip-val">
                    {{ seg.tco2e.toFixed(1) }} tCO2e
                  </span>
                </div>
              </template>
            </PTooltip>
          </div>

          <!-- Legend dots -->
          <div class="emissions-bar__legend">
            <div
              v-for="seg in emissionsBarSegments"
              :key="seg.config.key"
              class="emissions-bar__legend-item"
            >
              <span
                class="emissions-bar__legend-dot"
                :style="{ backgroundColor: seg.config.color }"
              ></span>
              <PTypography variant="body2" class="emissions-bar__legend-text">
                {{ seg.config.label }}
              </PTypography>
            </div>
          </div>
        </div>
      </div>

      <!-- Right column: end-use donut (only when data available) -->
      <div v-if="endUseBreakdown" class="baseline-layout__right">
        <EndUseDonut
          :breakdown="endUseBreakdown"
          :total-eui="baseline.total_eui_kbtu_sf"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ---- Card container ---- */
.baseline-card {
  background: var(--app-surface-raised);
  border: 1px solid var(--partner-border-light);
  border-radius: var(--partner-radius-lg);
  padding: 1.5rem;
  margin-bottom: 1.5rem;
}

.baseline-card__header {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  margin-bottom: 1.25rem;
}

.baseline-card__title {
  color: var(--partner-text-primary);
}

/* ---- Calibrated badge ---- */
.calibrated-badge {
  display: inline-flex;
  align-items: center;
  background: var(--partner-green-1);
  color: var(--partner-green-8);
  font-size: 0.75rem;
  font-weight: 500;
  padding: 0.125rem 0.5rem;
  border-radius: var(--partner-radius-full);
  line-height: 1.4;
  white-space: nowrap;
  flex-shrink: 0;
}

/* ---- Grid layout (1-col default, 2-col with donut) ---- */
.baseline-layout {
  display: grid;
  grid-template-columns: 1fr;
  gap: 2rem;
  align-items: center;
}

.baseline-layout--with-donut {
  grid-template-columns: 1fr 1fr;
}

.baseline-layout__left {
  min-width: 0;
}

.baseline-layout__section-title {
  color: var(--partner-gray-6);
  text-transform: uppercase;
  margin-bottom: 0.25rem;
}

.baseline-layout__right {
  min-width: 0;
}

/* ---- Hero section ---- */
.baseline-hero {
  display: flex;
  align-items: center;
  gap: 2rem;
  margin-bottom: 1.25rem;
  padding: 0.75rem 0;
}

.baseline-hero__primary,
.baseline-hero__secondary {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.baseline-hero__value {
  font-family: var(--font-display);
  font-size: 3rem;
  font-weight: 700;
  line-height: 1;
  color: var(--app-accent);
}

.baseline-hero__unit {
  margin-top: 0.25rem;
  color: var(--partner-gray-6);
}

.baseline-hero__divider {
  width: 1px;
  height: 3.5rem;
  background: var(--partner-border-light);
  flex-shrink: 0;
}

.baseline-hero__annual-value {
  font-family: var(--font-mono);
  font-size: 1.5rem;
  font-weight: 600;
  line-height: 1;
  color: var(--app-accent-muted);
}

.baseline-hero__annual-unit {
  margin-top: 0.25rem;
  color: var(--partner-gray-6);
}

/* ---- Stacked fuel bar ---- */
.fuel-bar__heading {
  margin-bottom: 0.75rem;
  color: var(--partner-gray-6);
  text-transform: uppercase;
}

.fuel-bar__track {
  display: flex;
  width: 100%;
  height: 20px;
  border-radius: 5px;
  overflow: hidden;
  background: var(--partner-gray-2);
}

.fuel-bar__segment {
  height: 100%;
  cursor: pointer;
  transition: opacity 0.15s ease, filter 0.15s ease;
  border-right: 1px solid rgba(255, 255, 255, 0.3);
}

.fuel-bar__segment:last-child {
  border-right: none;
}

.fuel-bar__segment:hover {
  opacity: 0.85;
  filter: brightness(1.1);
}

/* ---- Bar tooltip ---- */
.fuel-bar__tooltip {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 0.75rem;
  white-space: nowrap;
}

.fuel-bar__tooltip-label {
  font-weight: 600;
}

.fuel-bar__tooltip-pct {
  font-family: var(--font-mono);
}

.fuel-bar__tooltip-val {
  font-family: var(--font-mono);
  opacity: 0.85;
}

/* ---- Legend ---- */
.fuel-bar__legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 0.5rem;
}

.fuel-bar__legend-item {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.fuel-bar__legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.fuel-bar__legend-text {
  color: var(--partner-gray-6);
}

/* ---- Consumption section (below fuel bar) ---- */
.consumption-section {
  margin-top: 1.5rem;
}

.consumption-list__heading {
  margin-bottom: 0.75rem;
  color: var(--partner-gray-6);
  text-transform: uppercase;
}

.consumption-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.625rem;
}

.consumption-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 1rem;
  background: var(--app-surface);
  border: 1px solid var(--partner-border-light);
  border-radius: var(--partner-radius-md);
  gap: 1rem;
}

.consumption-item__left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.consumption-item__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.consumption-item__label {
  color: var(--partner-text-primary);
}

.consumption-item__right {
  display: flex;
  align-items: baseline;
  gap: 0.35rem;
  margin-left: auto;
  white-space: nowrap;
}

.consumption-item__value {
  font-family: var(--font-mono);
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--partner-text-primary);
}

.consumption-item__unit {
  font-weight: 400;
  color: var(--partner-gray-5);
}

/* ---- Emissions bar ---- */
.emissions-bar {
  margin-top: 1.5rem;
}

.emissions-bar__heading {
  margin-bottom: 0.75rem;
  color: var(--partner-gray-6);
  text-transform: uppercase;
}

.emissions-bar__track {
  display: flex;
  width: 100%;
  height: 20px;
  border-radius: 5px;
  overflow: hidden;
  background: var(--partner-gray-2);
}

.emissions-bar__segment {
  height: 100%;
  cursor: pointer;
  transition: opacity 0.15s ease, filter 0.15s ease;
  border-right: 1px solid rgba(255, 255, 255, 0.3);
}

.emissions-bar__segment:last-child {
  border-right: none;
}

.emissions-bar__segment:hover {
  opacity: 0.85;
  filter: brightness(1.1);
}

.emissions-bar__tooltip {
  display: flex;
  flex-direction: column;
  gap: 2px;
  white-space: nowrap;
}

.emissions-bar__tooltip-label {
  font-weight: 600;
}

.emissions-bar__tooltip-val {
  opacity: 0.85;
}

.emissions-bar__legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 0.5rem;
}

.emissions-bar__legend-item {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.emissions-bar__legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.emissions-bar__legend-text {
  color: var(--partner-gray-6);
}

/* ---- Responsive ---- */
@media (max-width: 768px) {
  .baseline-layout,
  .baseline-layout--with-donut {
    grid-template-columns: 1fr;
  }

  .baseline-layout__right {
    max-width: none;
  }
}

@media (max-width: 640px) {
  .baseline-hero {
    flex-direction: column;
    gap: 1rem;
  }

  .baseline-hero__divider {
    width: 4rem;
    height: 1px;
  }
}
</style>
