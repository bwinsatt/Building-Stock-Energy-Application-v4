<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  PTable,
  PTableHeader,
  PTableHead,
  PTableBody,
  PTableRow,
  PTableCell,
  PBadge,
  PButton,
  PTypography,
  PTooltip,
  PIcon,
} from '@partnerdevops/partner-components'
import type { MeasureResult } from '../types/assessment'

const props = defineProps<{
  measures: MeasureResult[]
  sqft: number
}>()

// ---- Sorting ----

type SortColumn = 'savings_pct' | 'annual_savings' | 'installed_cost' | 'payback'

const sortColumn = ref<SortColumn>('payback')
const sortDirection = ref<'asc' | 'desc'>('asc')

function handleSort(col: SortColumn, dir: 'asc' | 'desc' | undefined) {
  if (dir === undefined) {
    // PTableHead cycles through asc -> desc -> undefined; reset to asc for the column
    sortColumn.value = col
    sortDirection.value = 'asc'
  } else {
    sortColumn.value = col
    sortDirection.value = dir
  }
}

function getSortDirection(col: SortColumn): 'asc' | 'desc' | undefined {
  return sortColumn.value === col ? sortDirection.value : undefined
}

function clampedPayback(val?: number): number | undefined {
  if (val == null) return undefined
  return Math.max(0, val)
}

function getSortValue(m: MeasureResult, col: SortColumn): number | null {
  switch (col) {
    case 'savings_pct':
      return m.savings_pct ?? null
    case 'annual_savings':
      return m.utility_bill_savings_per_sf != null
        ? m.utility_bill_savings_per_sf * props.sqft
        : null
    case 'installed_cost':
      return m.cost?.installed_cost_total ?? null
    case 'payback':
      return clampedPayback(m.simple_payback_years) ?? null
  }
}

// ---- Applicable / Non-applicable split ----

const individualMeasures = computed(() => {
  return props.measures.filter((m) => m.applicable && m.category !== 'package')
})

const packageMeasures = computed(() => {
  return props.measures.filter((m) => m.applicable && m.category === 'package')
})

const nonApplicableMeasures = computed(() => {
  return props.measures.filter((m) => !m.applicable)
})

function sortMeasures(items: MeasureResult[]): MeasureResult[] {
  const sorted = [...items]
  const dir = sortDirection.value === 'asc' ? 1 : -1
  const col = sortColumn.value

  sorted.sort((a, b) => {
    const aVal = getSortValue(a, col)
    const bVal = getSortValue(b, col)
    if (aVal == null && bVal == null) return 0
    if (aVal == null) return 1
    if (bVal == null) return -1
    return (aVal - bVal) * dir
  })

  return sorted
}

const sortedIndividual = computed(() => sortMeasures(individualMeasures.value))
const sortedPackages = computed(() => sortMeasures(packageMeasures.value))

// ---- Collapse toggles ----

const showIndividual = ref(true)
const showPackages = ref(true)
const showNonApplicable = ref(false)

// ---- Summary stats ----

const summaryStats = computed(() => {
  const applicable = individualMeasures.value
  const count = applicable.length

  const paybacks = applicable
    .map((m) => clampedPayback(m.simple_payback_years))
    .filter((v): v is number => v != null)
  const bestPayback = paybacks.length > 0 ? Math.min(...paybacks) : null

  const savings = applicable
    .map((m) => m.savings_pct)
    .filter((v): v is number => v != null)
  const maxSavings = savings.length > 0 ? Math.max(...savings) : null

  return { count, bestPayback, maxSavings }
})

// ---- Category badge mapping ----

type BadgeVariant = 'primary' | 'secondary' | 'error' | 'warning' | 'success' | 'neutral'

interface CategoryConfig {
  variant: BadgeVariant
  label: string
}

const CATEGORY_DISPLAY_MAP: Record<string, { variant: BadgeVariant; label: string }> = {
  hvac: { variant: 'primary', label: 'HVAC' },
  envelope: { variant: 'success', label: 'Envelope' },
  lighting: { variant: 'warning', label: 'Lighting' },
  demand_flex: { variant: 'secondary', label: 'Demand Flex' },
  water_heater: { variant: 'neutral', label: 'Water Heating' },
  water_heating: { variant: 'neutral', label: 'Water Heating' },
  kitchen: { variant: 'neutral', label: 'Kitchen' },
  package: { variant: 'primary', label: 'Package' },
}

function getCategoryConfig(category: string): CategoryConfig {
  const lower = category.toLowerCase()
  for (const [key, config] of Object.entries(CATEGORY_DISPLAY_MAP)) {
    if (lower.includes(key)) return config
  }
  return { variant: 'neutral', label: category }
}

// ---- Formatting ----

const currencyFormatter = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
})

function formatCurrency(val?: number): string {
  return val != null ? currencyFormatter.format(val) : '\u2014'
}

function formatNumber(val?: number, decimals = 1): string {
  return val != null ? val.toFixed(decimals) : '\u2014'
}

// ---- Payback color ----

function paybackColor(val?: number): string {
  if (val == null) return '#94a3b8'
  if (val < 5) return '#22c55e'
  if (val <= 15) return '#eab308'
  return '#ef4444'
}

// ---- Description expand/collapse ----

const DESC_TRUNCATE_LENGTH = 90

const allDescExpanded = ref(false)
const expandedDescIds = ref(new Set<number>())

function isDescExpanded(upgradeId: number): boolean {
  return allDescExpanded.value || expandedDescIds.value.has(upgradeId)
}

function toggleDescRow(upgradeId: number) {
  const ids = new Set(expandedDescIds.value)
  if (ids.has(upgradeId)) {
    ids.delete(upgradeId)
    // If we were in expand-all mode and user collapses one, exit expand-all
    allDescExpanded.value = false
  } else {
    ids.add(upgradeId)
  }
  expandedDescIds.value = ids
}

function toggleDescAll() {
  allDescExpanded.value = !allDescExpanded.value
  // Clear individual overrides when toggling global
  expandedDescIds.value = new Set()
}

function truncateText(text: string | undefined | null, maxLength: number): string {
  if (!text) return '\u2014'
  if (text.length <= maxLength) return text
  return text.substring(0, maxLength) + '...'
}
</script>

<template>
  <div class="measures-card">
    <!-- Header -->
    <div class="measures-header">
      <PTypography variant="h4" class="measures-header__title">
        Upgrade Measures
      </PTypography>

      <!-- Summary stats -->
      <div class="measures-summary">
        <span class="measures-summary__item">
          <strong>{{ summaryStats.count }}</strong> applicable measures
        </span>
        <span v-if="summaryStats.bestPayback != null" class="measures-summary__divider">|</span>
        <span v-if="summaryStats.bestPayback != null" class="measures-summary__item">
          Best payback: <strong class="measures-summary__highlight">{{ formatNumber(summaryStats.bestPayback) }} yrs</strong>
        </span>
        <span v-if="summaryStats.maxSavings != null" class="measures-summary__divider">|</span>
        <span v-if="summaryStats.maxSavings != null" class="measures-summary__item">
          Max savings: <strong class="measures-summary__highlight">{{ formatNumber(summaryStats.maxSavings) }}%</strong>
        </span>
      </div>
    </div>

    <!-- Individual measures collapsible (expanded by default) -->
    <div class="measures-section">
      <PButton
        variant="neutral"
        appearance="text"
        size="small"
        :icon="showIndividual ? 'chevron-down' : 'chevron-right'"
        @click="showIndividual = !showIndividual"
      >
        {{ individualMeasures.length }} Individual Measures
      </PButton>
    </div>

    <div v-if="showIndividual" class="measures-table-wrapper">
      <PTable class="measures-table">
        <PTableHeader variant="gray-fill" size="small" :single-sort="true">
          <PTableRow>
            <PTableHead class="measures-th measures-th--name">
              Measure
            </PTableHead>
            <PTableHead class="measures-th measures-th--category">
              Category
            </PTableHead>
            <PTableHead
              class="measures-th measures-th--numeric"
              :sortable="true"
              :sort-direction="getSortDirection('savings_pct')"
              @sort-changed="(dir: 'asc' | 'desc' | undefined) => handleSort('savings_pct', dir)"
            >
              Savings %
            </PTableHead>
            <PTableHead
              class="measures-th measures-th--numeric"
              :sortable="true"
              :sort-direction="getSortDirection('annual_savings')"
              @sort-changed="(dir: 'asc' | 'desc' | undefined) => handleSort('annual_savings', dir)"
            >
              Annual Bill Savings ($)
            </PTableHead>
            <PTableHead
              class="measures-th measures-th--numeric"
              :sortable="true"
              :sort-direction="getSortDirection('installed_cost')"
              @sort-changed="(dir: 'asc' | 'desc' | undefined) => handleSort('installed_cost', dir)"
            >
              Installed Cost
            </PTableHead>
            <PTableHead
              class="measures-th measures-th--numeric"
              :sortable="true"
              :sort-direction="getSortDirection('payback')"
              @sort-changed="(dir: 'asc' | 'desc' | undefined) => handleSort('payback', dir)"
            >
              Payback (yrs)
            </PTableHead>
            <PTableHead class="measures-th measures-th--numeric">
              Electricity Savings (kWh)
            </PTableHead>
            <PTableHead class="measures-th measures-th--numeric">
              Gas Savings (therms)
            </PTableHead>
            <PTableHead class="measures-th measures-th--numeric">
              Other Fuel Savings (kBtu)
            </PTableHead>
            <PTableHead class="measures-th measures-th--numeric">
              Emissions Reduction (%)
            </PTableHead>
            <PTableHead class="measures-th measures-th--numeric">
              Useful Life (yrs)
            </PTableHead>
            <PTableHead class="measures-th measures-th--desc">
              <span class="measures-desc-toggle" @click="toggleDescAll">
                <PIcon
                  :name="allDescExpanded ? 'chevron-down' : 'chevron-right'"
                  size="small"
                  class="measures-desc-toggle__icon"
                />
                Description
              </span>
            </PTableHead>
          </PTableRow>
        </PTableHeader>

        <PTableBody>
          <PTableRow
            v-for="m in sortedIndividual"
            :key="m.upgrade_id"
          >
            <PTableCell class="measures-cell measures-cell--name">
              <PTypography variant="body2">{{ m.name }}</PTypography>
            </PTableCell>
            <PTableCell class="measures-cell measures-cell--category">
              <PBadge :variant="getCategoryConfig(m.category).variant" appearance="standard">
                {{ getCategoryConfig(m.category).label }}
              </PBadge>
            </PTableCell>
            <PTableCell class="measures-cell measures-cell--mono measures-cell--right">
              <PTypography variant="body2" component="span">{{ m.savings_pct != null ? formatNumber(m.savings_pct) + '%' : '\u2014' }}</PTypography>
            </PTableCell>
            <PTableCell class="measures-cell measures-cell--mono measures-cell--right">
              <PTypography variant="body2" component="span">{{
                m.utility_bill_savings_per_sf != null
                  ? formatCurrency(m.utility_bill_savings_per_sf * sqft)
                  : '\u2014'
              }}</PTypography>
            </PTableCell>
            <PTableCell class="measures-cell measures-cell--mono measures-cell--right">
              <PTooltip v-if="m.cost?.cost_range" direction="top">
                <template #tooltip-trigger>
                  <PTypography variant="body2" component="span" class="measures-cost-trigger">
                    {{ formatCurrency(m.cost?.installed_cost_total) }}
                  </PTypography>
                </template>
                <template #tooltip-content>
                  <span class="measures-cost-tooltip">
                    Range: {{ formatCurrency(m.cost.cost_range.low) }} – {{ formatCurrency(m.cost.cost_range.high) }}
                  </span>
                </template>
              </PTooltip>
              <PTypography v-else variant="body2" component="span">
                {{ formatCurrency(m.cost?.installed_cost_total) }}
              </PTypography>
            </PTableCell>
            <PTableCell class="measures-cell measures-cell--mono measures-cell--right">
              <PTypography variant="body2" component="span" :style="{ color: paybackColor(clampedPayback(m.simple_payback_years)), fontWeight: 600 }">
                {{ formatNumber(clampedPayback(m.simple_payback_years)) }}
              </PTypography>
            </PTableCell>
            <!-- Electricity Savings -->
            <PTableCell class="measures-cell measures-cell--mono measures-cell--right">
              <PTypography variant="body2" component="span">
                {{ m.electricity_savings_kwh != null ? Math.round(m.electricity_savings_kwh * sqft).toLocaleString() : '\u2014' }}
              </PTypography>
            </PTableCell>
            <!-- Gas Savings -->
            <PTableCell class="measures-cell measures-cell--mono measures-cell--right">
              <PTypography variant="body2" component="span">
                {{ m.gas_savings_therms != null ? Math.round(m.gas_savings_therms * sqft).toLocaleString() : '\u2014' }}
              </PTypography>
            </PTableCell>
            <!-- Other Fuel Savings -->
            <PTableCell class="measures-cell measures-cell--mono measures-cell--right">
              <PTypography variant="body2" component="span">
                {{ m.other_fuel_savings_kbtu != null ? Math.round(m.other_fuel_savings_kbtu * sqft).toLocaleString() : '\u2014' }}
              </PTypography>
            </PTableCell>
            <!-- Emissions Reduction -->
            <PTableCell class="measures-cell measures-cell--mono measures-cell--right">
              <PTypography variant="body2" component="span">
                {{ m.emissions_reduction_pct != null ? formatNumber(m.emissions_reduction_pct) + '%' : '\u2014' }}
              </PTypography>
            </PTableCell>
            <!-- Useful Life -->
            <PTableCell class="measures-cell measures-cell--mono measures-cell--right">
              <PTypography variant="body2" component="span">
                {{ m.cost?.useful_life_years != null ? m.cost.useful_life_years : '\u2014' }}
              </PTypography>
            </PTableCell>
            <!-- Description -->
            <PTableCell class="measures-cell measures-cell--desc">
              <div class="measures-desc-content" v-if="m.description">
                <PIcon
                  :name="isDescExpanded(m.upgrade_id) ? 'chevron-down' : 'chevron-right'"
                  size="small"
                  class="measures-desc-row-icon"
                  @click="toggleDescRow(m.upgrade_id)"
                />
                <PTypography variant="body2" component="span">
                  {{ isDescExpanded(m.upgrade_id) ? m.description : truncateText(m.description, DESC_TRUNCATE_LENGTH) }}
                </PTypography>
              </div>
              <PTypography v-else variant="body2" component="span">&#8212;</PTypography>
            </PTableCell>
          </PTableRow>
        </PTableBody>
      </PTable>
    </div>

    <!-- Measure Packages collapsible (expanded by default) -->
    <div v-if="packageMeasures.length > 0" class="measures-section">
      <PButton
        variant="neutral"
        appearance="text"
        size="small"
        :icon="showPackages ? 'chevron-down' : 'chevron-right'"
        @click="showPackages = !showPackages"
      >
        {{ packageMeasures.length }} Measure Packages
      </PButton>
    </div>

    <div v-if="packageMeasures.length > 0 && showPackages" class="measures-table-wrapper measures-packages__table">
        <PTable class="measures-table">
          <PTableHeader variant="gray-fill" size="small" :single-sort="true">
            <PTableRow>
              <PTableHead class="measures-th measures-th--name">Measure</PTableHead>
              <PTableHead class="measures-th measures-th--category">Category</PTableHead>
              <PTableHead
                class="measures-th measures-th--numeric"
                :sortable="true"
                :sort-direction="getSortDirection('savings_pct')"
                @sort-changed="(dir: 'asc' | 'desc' | undefined) => handleSort('savings_pct', dir)"
              >Savings %</PTableHead>
              <PTableHead
                class="measures-th measures-th--numeric"
                :sortable="true"
                :sort-direction="getSortDirection('annual_savings')"
                @sort-changed="(dir: 'asc' | 'desc' | undefined) => handleSort('annual_savings', dir)"
              >Annual Bill Savings ($)</PTableHead>
              <PTableHead
                class="measures-th measures-th--numeric"
                :sortable="true"
                :sort-direction="getSortDirection('installed_cost')"
                @sort-changed="(dir: 'asc' | 'desc' | undefined) => handleSort('installed_cost', dir)"
              >Installed Cost</PTableHead>
              <PTableHead
                class="measures-th measures-th--numeric"
                :sortable="true"
                :sort-direction="getSortDirection('payback')"
                @sort-changed="(dir: 'asc' | 'desc' | undefined) => handleSort('payback', dir)"
              >Payback (yrs)</PTableHead>
              <PTableHead class="measures-th measures-th--numeric">Electricity Savings (kWh)</PTableHead>
              <PTableHead class="measures-th measures-th--numeric">Gas Savings (therms)</PTableHead>
              <PTableHead class="measures-th measures-th--numeric">Other Fuel Savings (kBtu)</PTableHead>
              <PTableHead class="measures-th measures-th--numeric">Emissions Reduction (%)</PTableHead>
              <PTableHead class="measures-th measures-th--numeric">Useful Life (yrs)</PTableHead>
              <PTableHead class="measures-th measures-th--desc">
                <span class="measures-desc-toggle" @click="toggleDescAll">
                  <PIcon
                    :name="allDescExpanded ? 'chevron-down' : 'chevron-right'"
                    size="small"
                    class="measures-desc-toggle__icon"
                  />
                  Description
                </span>
              </PTableHead>
            </PTableRow>
          </PTableHeader>

          <PTableBody>
            <PTableRow
              v-for="m in sortedPackages"
              :key="m.upgrade_id"
            >
              <PTableCell class="measures-cell measures-cell--name">
                <PTypography variant="body2">{{ m.name }}</PTypography>
              </PTableCell>
              <PTableCell class="measures-cell measures-cell--category">
                <PBadge :variant="getCategoryConfig(m.category).variant" appearance="standard">
                  {{ getCategoryConfig(m.category).label }}
                </PBadge>
              </PTableCell>
              <PTableCell class="measures-cell measures-cell--mono measures-cell--right">
                <PTypography variant="body2" component="span">{{ m.savings_pct != null ? formatNumber(m.savings_pct) + '%' : '\u2014' }}</PTypography>
              </PTableCell>
              <PTableCell class="measures-cell measures-cell--mono measures-cell--right">
                <PTypography variant="body2" component="span">{{
                  m.utility_bill_savings_per_sf != null
                    ? formatCurrency(m.utility_bill_savings_per_sf * sqft)
                    : '\u2014'
                }}</PTypography>
              </PTableCell>
              <PTableCell class="measures-cell measures-cell--mono measures-cell--right">
                <PTooltip v-if="m.cost?.cost_range" direction="top">
                  <template #tooltip-trigger>
                    <PTypography variant="body2" component="span" class="measures-cost-trigger">
                      {{ formatCurrency(m.cost?.installed_cost_total) }}
                    </PTypography>
                  </template>
                  <template #tooltip-content>
                    <span class="measures-cost-tooltip">
                      Range: {{ formatCurrency(m.cost.cost_range.low) }} – {{ formatCurrency(m.cost.cost_range.high) }}
                    </span>
                  </template>
                </PTooltip>
                <PTypography v-else variant="body2" component="span">
                  {{ formatCurrency(m.cost?.installed_cost_total) }}
                </PTypography>
              </PTableCell>
              <PTableCell class="measures-cell measures-cell--mono measures-cell--right">
                <PTypography variant="body2" component="span" :style="{ color: paybackColor(clampedPayback(m.simple_payback_years)), fontWeight: 600 }">
                  {{ formatNumber(clampedPayback(m.simple_payback_years)) }}
                </PTypography>
              </PTableCell>
              <PTableCell class="measures-cell measures-cell--mono measures-cell--right">
                <PTypography variant="body2" component="span">
                  {{ m.electricity_savings_kwh != null ? Math.round(m.electricity_savings_kwh * sqft).toLocaleString() : '\u2014' }}
                </PTypography>
              </PTableCell>
              <PTableCell class="measures-cell measures-cell--mono measures-cell--right">
                <PTypography variant="body2" component="span">
                  {{ m.gas_savings_therms != null ? Math.round(m.gas_savings_therms * sqft).toLocaleString() : '\u2014' }}
                </PTypography>
              </PTableCell>
              <PTableCell class="measures-cell measures-cell--mono measures-cell--right">
                <PTypography variant="body2" component="span">
                  {{ m.other_fuel_savings_kbtu != null ? Math.round(m.other_fuel_savings_kbtu * sqft).toLocaleString() : '\u2014' }}
                </PTypography>
              </PTableCell>
              <PTableCell class="measures-cell measures-cell--mono measures-cell--right">
                <PTypography variant="body2" component="span">
                  {{ m.emissions_reduction_pct != null ? formatNumber(m.emissions_reduction_pct) + '%' : '\u2014' }}
                </PTypography>
              </PTableCell>
              <PTableCell class="measures-cell measures-cell--mono measures-cell--right">
                <PTypography variant="body2" component="span">
                  {{ m.cost?.useful_life_years != null ? m.cost.useful_life_years : '\u2014' }}
                </PTypography>
              </PTableCell>
              <PTableCell class="measures-cell measures-cell--desc">
                <div class="measures-desc-content" v-if="m.description">
                  <PIcon
                    :name="isDescExpanded(m.upgrade_id) ? 'chevron-down' : 'chevron-right'"
                    size="small"
                    class="measures-desc-row-icon"
                    @click="toggleDescRow(m.upgrade_id)"
                  />
                  <PTypography variant="body2" component="span">
                    {{ isDescExpanded(m.upgrade_id) ? m.description : truncateText(m.description, DESC_TRUNCATE_LENGTH) }}
                  </PTypography>
                </div>
                <PTypography v-else variant="body2" component="span">&#8212;</PTypography>
              </PTableCell>
            </PTableRow>
          </PTableBody>
        </PTable>
      </div>

    <!-- Non-applicable measures collapsible -->
    <div v-if="nonApplicableMeasures.length > 0" class="measures-section">
      <PButton
        variant="neutral"
        appearance="text"
        size="small"
        :icon="showNonApplicable ? 'chevron-down' : 'chevron-right'"
        @click="showNonApplicable = !showNonApplicable"
      >
        {{ nonApplicableMeasures.length }} Non-Applicable Measures
      </PButton>
    </div>

    <div v-if="nonApplicableMeasures.length > 0 && showNonApplicable" class="measures-table-wrapper measures-nonapplicable__table measures-table-wrapper--secondary">
        <PTable class="measures-table">
          <PTableBody>
            <PTableRow
              v-for="m in nonApplicableMeasures"
              :key="m.upgrade_id"
              class="measures-row--dimmed"
            >
              <PTableCell class="measures-cell measures-cell--name">
                <PTypography variant="body2">{{ m.name }}</PTypography>
              </PTableCell>
              <PTableCell class="measures-cell measures-cell--category">
                <PBadge :variant="getCategoryConfig(m.category).variant" appearance="standard">
                  {{ getCategoryConfig(m.category).label }}
                </PBadge>
              </PTableCell>
              <PTableCell class="measures-cell measures-cell--mono measures-cell--right" />
              <PTableCell class="measures-cell measures-cell--mono measures-cell--right" />
              <PTableCell class="measures-cell measures-cell--mono measures-cell--right" />
              <PTableCell class="measures-cell measures-cell--mono measures-cell--right" />
              <PTableCell class="measures-cell measures-cell--mono measures-cell--right" />
              <PTableCell class="measures-cell measures-cell--mono measures-cell--right" />
              <PTableCell class="measures-cell measures-cell--mono measures-cell--right" />
              <PTableCell class="measures-cell measures-cell--mono measures-cell--right" />
              <PTableCell class="measures-cell measures-cell--mono measures-cell--right" />
              <PTableCell class="measures-cell measures-cell--desc">
                <div class="measures-desc-content" v-if="m.description">
                  <PIcon
                    :name="isDescExpanded(m.upgrade_id) ? 'chevron-down' : 'chevron-right'"
                    size="small"
                    class="measures-desc-row-icon"
                    @click="toggleDescRow(m.upgrade_id)"
                  />
                  <PTypography variant="body2" component="span">
                    {{ isDescExpanded(m.upgrade_id) ? m.description : truncateText(m.description, DESC_TRUNCATE_LENGTH) }}
                  </PTypography>
                </div>
                <PTypography v-else variant="body2" component="span">&#8212;</PTypography>
              </PTableCell>
            </PTableRow>
          </PTableBody>
        </PTable>
      </div>
  </div>
</template>

<style scoped>
/* ---- Card container ---- */
.measures-card {
  background: var(--app-surface-raised);
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  overflow: hidden;
}

/* ---- Header ---- */
.measures-header {
  padding: 1.25rem 1.5rem 1rem;
  border-bottom: 1px solid #e2e8f0;
}

.measures-header__title {
  margin-bottom: 0.5rem;
  color: var(--partner-text-primary, #333e47);
}

/* ---- Summary stats ---- */
.measures-summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  color: #64748b;
}

.measures-summary__divider {
  color: #cbd5e1;
}

.measures-summary__highlight {
  color: var(--app-accent-muted);
  font-weight: 600;
}

/* ---- Table wrapper ---- */
/*
 * NOTE: Sticky columns and sticky header are implemented via scoped CSS here
 * because the partner-components PTable does not yet support sticky/pinned columns.
 * When integrating into the main application (SL Heaven), these overrides should
 * be migrated to the partner-components library as proper PTable props/features.
 * Reference: SL Heaven AssetPlanner table pattern.
 */
.measures-table-wrapper {
  max-height: 586px;
  overflow-y: auto;
  overflow-x: scroll;
  position: relative;
}

.measures-table {
  width: 100%;
}

/*
 * The shadcn Table component wraps <table> in <div class="overflow-auto">.
 * That intermediate div intercepts position:sticky as the scroll container
 * (even without a height constraint, overflow:auto creates a scroll container
 * in CSS terms). Override to visible so .measures-table-wrapper is the
 * effective scroll container for sticky headers and columns.
 */
.measures-table-wrapper > :deep(div) {
  overflow: visible;
}

/*
 * Switch to border-collapse: separate so that border-bottom on sticky <th>
 * cells renders correctly. With collapse, sticky cell borders are swallowed
 * when the cell overlaps other content. border-spacing: 0 keeps cells flush.
 * Row separators must move to <td> since <tr> borders don't render in
 * separate mode.
 */
.measures-table-wrapper :deep(table) {
  border-collapse: separate;
  border-spacing: 0;
}

/* ---- Sticky header ---- */
.measures-table-wrapper :deep(tbody tr) {
  background-color: var(--app-surface-raised, white);
}

.measures-table-wrapper :deep(tbody tr:hover) {
  background-color: var(--partner-fill-hover);
}

/* Row separators on <td> (tr borders don't render with border-collapse: separate) */
.measures-table-wrapper :deep(tbody td) {
  border-bottom: 1px solid var(--partner-border-divider, #e2e8f0);
}

/* ---- Header cells ---- */
.measures-th {
  white-space: nowrap;
  position: sticky;
  top: 0;
  z-index: 2;
  background-color: var(--partner-background-gray);
  border-bottom: 1px solid var(--partner-border-disabled, #e2e8f0);
}

.measures-th--name {
  min-width: 220px;
  left: 0;
  z-index: 11;
}

.measures-th--category {
  min-width: 120px;
  left: 220px;
  z-index: 11;
}

.measures-th--numeric {
  text-align: right;
  min-width: 130px;
}

/* ---- Body cells ---- */
.measures-cell {
  vertical-align: middle;
}

.measures-cell--name {
  font-weight: 500;
  color: var(--partner-text-primary, #333e47);
  min-width: 220px;
  position: sticky;
  left: 0;
  z-index: 3;
  background-color: inherit;
}

.measures-cell--category {
  min-width: 120px;
  position: sticky;
  left: 220px;
  z-index: 3;
  background-color: inherit;
}

.measures-cell--mono {
  font-family: var(--font-mono);
}

.measures-cell--right {
  text-align: right;
}

.measures-th--desc {
  min-width: 280px;
}

.measures-cell--desc {
  min-width: 280px;
  max-width: 400px;
  white-space: normal;
  line-height: 1.4;
}

/* ---- Sticky column dividing line ----
 * Uses ::after instead of border-right because border-collapse swallows cell
 * borders on sticky elements when they overlap scrolled content. The ::after is
 * positioned relative to the sticky cell's own stacking context so it always
 * stays visible. On the header cell we override PTableHead's partner-th-divider
 * ::after (height: 50%, centered) with our full-height version.
 */
.measures-th--category::after,
.measures-cell--category::after {
  content: '' !important;
  position: absolute !important;
  right: 0 !important;
  top: 0 !important;
  height: 100% !important;
  width: 1px !important;
  background-color: var(--partner-border-divider, #e2e8f0) !important;
  transform: none !important;
  pointer-events: none;
}

/* ---- Description expand toggle ---- */
.measures-desc-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  cursor: pointer;
  user-select: none;
}

.measures-desc-toggle:hover {
  color: var(--partner-text-primary, #333e47);
}

.measures-desc-toggle__icon {
  transition: transform 0.2s ease;
  flex-shrink: 0;
}

.measures-desc-content {
  display: flex;
  align-items: flex-start;
  gap: 0.25rem;
}

.measures-desc-row-icon {
  flex-shrink: 0;
  cursor: pointer;
  margin-top: 0.125rem;
  transition: transform 0.2s ease;
}

.measures-desc-row-icon:hover {
  color: var(--partner-text-primary, #333e47);
}

/* ---- Cost tooltip trigger ---- */
.measures-cost-trigger {
  cursor: default;
}

.measures-cost-tooltip {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  white-space: nowrap;
}

/* ---- Dimmed (non-applicable) rows ---- */
.measures-row--dimmed {
  opacity: 0.45;
}


/* ---- Collapsible section toggle ---- */
.measures-section {
  padding: 0.75rem 1.5rem;
  border-top: 1px solid #e2e8f0;
}

.measures-packages__table {
  max-height: 50vh;
}

/* ---- Non-applicable section ---- */
.measures-nonapplicable {
  padding: 0.75rem 1.5rem;
  border-top: 1px solid #e2e8f0;
}

.measures-nonapplicable__table {
  margin-top: 0.5rem;
}

.measures-table-wrapper--secondary {
  max-height: 40vh;
}

/* ---- Responsive ---- */
@media (max-width: 768px) {
  .measures-header {
    padding: 1rem;
  }

  .measures-summary {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.25rem;
  }

  .measures-summary__divider {
    display: none;
  }
}
</style>
