<script setup lang="ts">
import { computed } from 'vue'
import { PTypography, PBadge } from '@partnerdevops/partner-components'
import type { BaselineResult, FuelBreakdown } from '../types/assessment'

const props = defineProps<{
  baseline: BaselineResult
  sqft: number
}>()

interface FuelConfig {
  key: keyof FuelBreakdown
  label: string
  color: string
  badgeVariant: 'warning' | 'primary' | 'secondary' | 'error' | 'neutral'
}

const fuelConfigs: FuelConfig[] = [
  { key: 'electricity', label: 'Electricity', color: '#eab308', badgeVariant: 'warning' },
  { key: 'natural_gas', label: 'Natural Gas', color: '#3b82f6', badgeVariant: 'primary' },
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
</script>

<template>
  <div class="baseline-card">
    <!-- Header -->
    <PTypography variant="h4" class="baseline-card__title">
      Baseline Energy Use
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
    </div>

    <!-- Fuel breakdown -->
    <div class="baseline-fuels">
      <PTypography variant="subhead" class="baseline-fuels__heading">
        Fuel Breakdown
      </PTypography>

      <div class="baseline-fuels__grid">
        <div
          v-for="fuel in activeFuels"
          :key="fuel.key"
          class="fuel-card"
          :style="{ borderLeftColor: fuel.color }"
        >
          <div class="fuel-card__header">
            <PBadge :variant="fuel.badgeVariant" appearance="standard">
              {{ fuel.label }}
            </PBadge>
            <span class="fuel-card__percent">
              {{ fuelPercent(fuel.key).toFixed(0) }}%
            </span>
          </div>

          <div class="fuel-card__value">
            {{ baseline.eui_by_fuel[fuel.key].toFixed(1) }}
            <span class="fuel-card__value-unit">kBtu/sf</span>
          </div>

          <!-- Proportion bar -->
          <div class="fuel-card__bar-track" aria-hidden="true">
            <div
              class="fuel-card__bar-fill"
              :style="{
                width: fuelPercent(fuel.key) + '%',
                backgroundColor: fuel.color,
              }"
            ></div>
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

/* ---- Fuel breakdown ---- */
.baseline-fuels__heading {
  margin-bottom: 0.75rem;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-size: 0.75rem;
}

.baseline-fuels__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 0.75rem;
}

/* ---- Individual fuel card ---- */
.fuel-card {
  background: var(--app-surface);
  border: 1px solid #e2e8f0;
  border-left: 3px solid;
  border-radius: 0.375rem;
  padding: 0.75rem 1rem;
}

.fuel-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.fuel-card__percent {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 600;
  color: #64748b;
}

.fuel-card__value {
  font-family: var(--font-mono);
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--partner-text-primary, #333e47);
  margin-bottom: 0.5rem;
}

.fuel-card__value-unit {
  font-size: 0.75rem;
  font-weight: 400;
  color: #94a3b8;
  margin-left: 0.25rem;
}

/* ---- Proportion bar ---- */
.fuel-card__bar-track {
  width: 100%;
  height: 4px;
  background: #e2e8f0;
  border-radius: 2px;
  overflow: hidden;
}

.fuel-card__bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.4s ease;
  min-width: 2px;
}

/* ---- Responsive ---- */
@media (max-width: 640px) {
  .baseline-hero {
    flex-direction: column;
    gap: 1rem;
  }

  .baseline-hero__divider {
    width: 4rem;
    height: 1px;
  }

  .baseline-fuels__grid {
    grid-template-columns: 1fr;
  }
}
</style>
