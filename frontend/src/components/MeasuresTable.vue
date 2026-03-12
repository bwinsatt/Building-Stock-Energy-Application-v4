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

const applicableMeasures = computed(() => {
  return props.measures.filter((m) => m.applicable)
})

const nonApplicableMeasures = computed(() => {
  return props.measures.filter((m) => !m.applicable)
})

const sortedApplicable = computed(() => {
  const items = [...applicableMeasures.value]
  const dir = sortDirection.value === 'asc' ? 1 : -1
  const col = sortColumn.value

  items.sort((a, b) => {
    const aVal = getSortValue(a, col)
    const bVal = getSortValue(b, col)
    if (aVal == null && bVal == null) return 0
    if (aVal == null) return 1
    if (bVal == null) return -1
    return (aVal - bVal) * dir
  })

  return items
})

// ---- Non-applicable collapse ----

const showNonApplicable = ref(false)

// ---- Summary stats ----

const summaryStats = computed(() => {
  const applicable = applicableMeasures.value
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

    <!-- Table -->
    <div class="measures-table-wrapper">
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
          </PTableRow>
        </PTableHeader>

        <PTableBody>
          <PTableRow
            v-for="(m, idx) in sortedApplicable"
            :key="m.upgrade_id"
            :class="idx % 2 === 1 ? 'measures-row--striped' : ''"
          >
            <PTableCell class="measures-cell measures-cell--name">
              <PTypography variant="body2">{{ m.name }}</PTypography>
            </PTableCell>
            <PTableCell class="measures-cell">
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
          </PTableRow>
        </PTableBody>
      </PTable>
    </div>

    <!-- Non-applicable measures collapsible -->
    <div v-if="nonApplicableMeasures.length > 0" class="measures-nonapplicable">
      <PButton
        variant="neutral"
        appearance="text"
        size="small"
        :icon="showNonApplicable ? 'chevron-down' : 'chevron-right'"
        @click="showNonApplicable = !showNonApplicable"
      >
        {{ nonApplicableMeasures.length }} non-applicable measures
      </PButton>

      <div v-if="showNonApplicable" class="measures-table-wrapper measures-nonapplicable__table">
        <PTable class="measures-table">
          <PTableBody>
            <PTableRow
              v-for="(m, idx) in nonApplicableMeasures"
              :key="m.upgrade_id"
              :class="[
                'measures-row--dimmed',
                idx % 2 === 1 ? 'measures-row--striped' : '',
              ]"
            >
              <PTableCell class="measures-cell measures-cell--name">
                <PTypography variant="body2">{{ m.name }}</PTypography>
              </PTableCell>
              <PTableCell class="measures-cell">
                <PBadge :variant="getCategoryConfig(m.category).variant" appearance="standard">
                  {{ getCategoryConfig(m.category).label }}
                </PBadge>
              </PTableCell>
              <PTableCell class="measures-cell measures-cell--mono measures-cell--right">
                <PTypography variant="body2" component="span">&#8212;</PTypography>
              </PTableCell>
              <PTableCell class="measures-cell measures-cell--mono measures-cell--right">
                <PTypography variant="body2" component="span">&#8212;</PTypography>
              </PTableCell>
              <PTableCell class="measures-cell measures-cell--mono measures-cell--right">
                <PTypography variant="body2" component="span">&#8212;</PTypography>
              </PTableCell>
              <PTableCell class="measures-cell measures-cell--mono measures-cell--right">
                <PTypography variant="body2" component="span">&#8212;</PTypography>
              </PTableCell>
            </PTableRow>
          </PTableBody>
        </PTable>
      </div>
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
.measures-table-wrapper {
  overflow-x: auto;
}

.measures-table {
  width: 100%;
}

/* ---- Header cells ---- */
.measures-th {
  white-space: nowrap;
}

.measures-th--name {
  min-width: 220px;
}

.measures-th--category {
  min-width: 120px;
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
}

.measures-cell--mono {
  font-family: var(--font-mono);
}

.measures-cell--right {
  text-align: right;
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

/* ---- Striped rows ---- */
.measures-row--striped {
  background: var(--app-surface);
}

/* ---- Dimmed (non-applicable) rows ---- */
.measures-row--dimmed {
  opacity: 0.45;
}

/* ---- Non-applicable section ---- */
.measures-nonapplicable {
  padding: 0.75rem 1.5rem;
  border-top: 1px solid #e2e8f0;
}

.measures-nonapplicable__table {
  margin-top: 0.5rem;
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
