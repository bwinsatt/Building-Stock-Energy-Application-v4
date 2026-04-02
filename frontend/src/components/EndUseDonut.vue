<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { PTypography } from '@partnerdevops/partner-components'
import Highcharts from 'highcharts'
import 'highcharts/modules/accessibility'

const props = defineProps({
  /** End-use breakdown: { category_name: kBtu_sf_value } */
  breakdown: { type: Object, required: true },
  /** Total EUI for center label */
  totalEui: { type: Number, default: 0 },
})

/* Map end-use categories to partner design token colors */
const tokenColorMap = {
  'Heating': '--partner-blue-7',
  'Cooling': '--partner-blue-4',
  'Water Heating': '--partner-orange-8',
  'Lighting': '--partner-gray-6',
  'Equipment & Appliances': '--partner-green-6',
  'Other': '--partner-blue-3',
}

const FALLBACK_TOKENS = [
  '--partner-yellow-7', '--partner-blue-6', '--partner-orange-4', '--partner-blue-9',
  '--partner-green-3', '--partner-orange-6', '--partner-yellow-9', '--partner-blue-5', '--partner-orange-7',
]

function resolveTokenColor(token) {
  return getComputedStyle(document.documentElement).getPropertyValue(token).trim() || token
}

function getColor(category, index) {
  const token = tokenColorMap[category] || FALLBACK_TOKENS[index % FALLBACK_TOKENS.length]
  return resolveTokenColor(token)
}

const chartData = computed(() => {
  const entries = Object.entries(props.breakdown)
    .filter(([, val]) => val > 0.05)
    .sort((a, b) => b[1] - a[1])

  const total = entries.reduce((sum, [, val]) => sum + val, 0)

  return entries.map(([name, value], i) => ({
    name,
    y: total > 0 ? (value / total) * 100 : 0,
    kbtuSf: value,
    color: getColor(name, i),
  }))
})

const chartContainer = ref(null)
let chartInstance = null

function buildOptions() {
  return {
    chart: {
      type: 'pie',
      height: 320,
      backgroundColor: 'transparent',
      style: { fontFamily: 'inherit' },
    },
    title: null,
    credits: { enabled: false },
    tooltip: {
      pointFormat: '<b>{point.percentage:.1f}%</b><br/>{point.kbtuSf:.1f} kBtu/sf',
      style: { fontSize: '12px' },
    },
    plotOptions: {
      pie: {
        innerSize: '0%',
        borderWidth: 0,
        borderRadius: 0,
        dataLabels: {
          enabled: true,
          format: '{point.name} {point.percentage:.0f}%',
          distance: 15,
          connectorWidth: 1,
          connectorColor: '#aaa',
          style: { fontSize: '12px', fontWeight: '600', fontFamily: 'Roboto, sans-serif', color: 'var(--partner-gray-7)', textOutline: 'none' },
          filter: { property: 'percentage', operator: '>', value: 5 },
        },
        showInLegend: false,
        cursor: 'pointer',
        states: { hover: { brightness: 0.1 } },
      },
    },
    series: [{ name: 'End Use', data: chartData.value }],
  }
}

function renderChart() {
  if (chartInstance) {
    chartInstance.destroy()
    chartInstance = null
  }
  if (chartContainer.value) {
    chartInstance = Highcharts.chart(chartContainer.value, buildOptions())
  }
}

onMounted(() => renderChart())

watch(() => props.breakdown, () => renderChart(), { deep: true })

onBeforeUnmount(() => {
  if (chartInstance) {
    chartInstance.destroy()
    chartInstance = null
  }
})
</script>

<template>
  <div class="enduse-donut">
    <PTypography variant="headline2" class="enduse-donut__heading">End-Use Breakdown</PTypography>
    <div class="enduse-donut__chart-wrap" ref="chartContainer"></div>
  </div>
</template>

<style scoped>
.enduse-donut__heading {
  margin-bottom: 0.5rem;
  color: var(--partner-gray-6);
  text-transform: uppercase;
}

.enduse-donut__chart-wrap {
  width: 100%;
}

.enduse-donut__legend {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  margin-top: 0.5rem;
}

.enduse-donut__legend-item {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.7rem;
}

.enduse-donut__legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.enduse-donut__legend-label {
  color: var(--partner-gray-6);
  flex: 1;
}

.enduse-donut__legend-pct {
  font-family: var(--font-mono);
  color: var(--partner-gray-7);
  font-weight: 500;
}
</style>
