<script setup lang="ts">
import { computed } from 'vue'
import { PTypography, PBadge, PTooltip } from '@partnerdevops/partner-components'
import type { BaselineResult, FuelBreakdown } from '../types/assessment'

const KWH_TO_KBTU = 3.412
const THERM_TO_KBTU = 100

const props = defineProps<{
  baseline: BaselineResult
  sqft: number
}>()

interface FuelConfig {
  key: keyof FuelBreakdown
  label: string
  color: string
  badgeVariant: 'warning' | 'primary' | 'secondary' | 'error' | 'neutral'
  /** Convert total kBtu to display unit. If undefined, stays as kBtu. */
  displayUnit?: { label: string; abbr: string; convert: (kbtu: number) => number }
}

const fuelConfigs: FuelConfig[] = [
  {
    key: 'electricity', label: 'Electricity', color: '#eab308', badgeVariant: 'warning',
    displayUnit: { label: 'kWh', abbr: 'kWh', convert: (kbtu) => kbtu / KWH_TO_KBTU },
  },
  {
    key: 'natural_gas', label: 'Natural Gas', color: '#3b82f6', badgeVariant: 'primary',
    displayUnit: { label: 'therms', abbr: 'therms', convert: (kbtu) => kbtu / THERM_TO_KBTU },
  },
  { key: 'fuel_oil', label: 'Fuel Oil', color: '#f97316', badgeVariant: 'secondary' },
  { key: 'propane', label: 'Propane', color: '#ef4444', badgeVariant: 'error' },
  { key: 'district_heating', label: 'District Heating', color: '#8b5cf6', badgeVariant: 'neutral' },
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
function formatNumber(value: number): string {
  return Math.round(value).toLocaleString('en-US')
}

/** Percentage of total EUI for a given fuel */
function fuelPercent(key: keyof FuelBreakdown): number {
  if (props.baseline.total_eui_kbtu_sf === 0) return 0
  return (props.baseline.eui_by_fuel[key] / props.baseline.total_eui_kbtu_sf) * 100
}

/** Total kBtu for a given fuel */
function fuelTotalKbtu(key: keyof FuelBreakdown): number {
  return props.baseline.eui_by_fuel[key] * props.sqft
}

/** Get display value and unit for the right-side consumption list */
function fuelConsumption(fuel: FuelConfig): { value: string; unit: string } {
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
    actualPercent: rawPercents[i],
    visualWidth: (boosted[i] / boostedTotal) * 100,
  }))
})
</script>

<template>
  <div class="baseline-card">
    <!-- Header -->
    <PTypography variant="h4" class="baseline-card__title">
      Baseline Energy Use
    </PTypography>

    <!-- Two-column layout: left stats + bar, right consumption list -->
    <div class="baseline-layout">
      <!-- Left column -->
      <div class="baseline-layout__left">
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
        </div>

        <!-- Stacked horizontal bar -->
        <div class="fuel-bar">
          <PTypography variant="subhead" class="fuel-bar__heading">
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
                  :aria-label="`${seg.fuel.label}: ${seg.actualPercent.toFixed(1)}%`"
                ></div>
              </template>
              <template #tooltip-content>
                <div class="fuel-bar__tooltip">
                  <span class="fuel-bar__tooltip-label">{{ seg.fuel.label }}</span>
                  <span class="fuel-bar__tooltip-pct">{{ seg.actualPercent.toFixed(1) }}%</span>
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
      </div>

      <!-- Right column: consumption list -->
      <div class="baseline-layout__right">
        <PTypography variant="subhead" class="consumption-list__heading">
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
    </div>
  </div>
</template>

<style scoped>
/* ---- Card container ---- */
.baseline-card {
  background: var(--app-surface-raised);
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
}

.baseline-card__title {
  margin-bottom: 1.25rem;
  color: var(--partner-text-primary, #333e47);
}

/* ---- Two-column layout ---- */
.baseline-layout {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 2rem;
  align-items: start;
}

.baseline-layout__left {
  min-width: 0;
}

.baseline-layout__right {
  min-width: 200px;
  max-width: 260px;
}

/* ---- Hero section ---- */
.baseline-hero {
  display: flex;
  align-items: center;
  gap: 2rem;
  margin-bottom: 1.75rem;
  padding: 1.25rem 0;
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
  color: #64748b;
}

.baseline-hero__divider {
  width: 1px;
  height: 3.5rem;
  background: #e2e8f0;
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
  color: #64748b;
}

/* ---- Stacked fuel bar ---- */
.fuel-bar__heading {
  margin-bottom: 0.75rem;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-size: 0.75rem;
}

.fuel-bar__track {
  display: flex;
  width: 100%;
  height: 20px;
  border-radius: 5px;
  overflow: hidden;
  background: #e2e8f0;
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
  color: #64748b;
  font-size: 0.7rem;
}

/* ---- Consumption list (right column) ---- */
.consumption-list__heading {
  margin-bottom: 0.75rem;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-size: 0.75rem;
}

.consumption-list {
  display: flex;
  flex-direction: column;
  gap: 0.625rem;
}

.consumption-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 1rem;
  background: var(--app-surface);
  border: 1px solid #e2e8f0;
  border-radius: 0.375rem;
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
  color: var(--partner-text-primary, #333e47);
  font-size: 0.8rem;
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
  color: var(--partner-text-primary, #333e47);
}

.consumption-item__unit {
  font-size: 0.7rem;
  font-weight: 400;
  color: #94a3b8;
}

/* ---- Responsive ---- */
@media (max-width: 768px) {
  .baseline-layout {
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
