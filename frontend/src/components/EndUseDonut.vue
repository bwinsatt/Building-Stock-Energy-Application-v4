<script setup>
import { computed } from 'vue'
import { Chart } from 'highcharts-vue'
import Highcharts from 'highcharts'
import Accessibility from 'highcharts/modules/accessibility'

Accessibility(Highcharts)

const props = defineProps({
  /** End-use breakdown: { category_name: kBtu_sf_value } */
  breakdown: { type: Object, required: true },
  /** Total EUI for center label */
  totalEui: { type: Number, default: 0 },
})

// Partner design system data viz colors (1-6)
const CATEGORY_COLORS = {
  'Heating': '#005199',
  'Cooling': '#2FB7C4',
  'Water Heating': '#A04A7A',
  'Lighting': '#6B778C',
  'Equipment & Appliances': '#8A9A3A',
  'Other': '#8FB9E5',
}

// Fallback colors from partner palette (7-15) for unexpected categories
const FALLBACK_COLORS = [
  '#C9A227', '#1C6ED5', '#E0C9A6', '#003660',
  '#7FCFC3', '#7A5EA8', '#B58B2E', '#3F4E9E', '#D07328',
]

function getColor(category, index) {
  return CATEGORY_COLORS[category] || FALLBACK_COLORS[index % FALLBACK_COLORS.length]
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

const chartOptions = computed(() => ({
  chart: {
    type: 'pie',
    height: 220,
    backgroundColor: 'transparent',
    style: { fontFamily: 'inherit' },
  },
  title: null,
  credits: { enabled: false },
  tooltip: {
    pointFormat:
      '<b>{point.percentage:.1f}%</b><br/>{point.kbtuSf:.1f} kBtu/sf',
    style: { fontSize: '12px' },
  },
  plotOptions: {
    pie: {
      innerSize: '55%',
      borderWidth: 2,
      borderColor: null,
      dataLabels: { enabled: false },
      showInLegend: false,
      cursor: 'pointer',
      states: {
        hover: { brightness: 0.1 },
      },
    },
  },
  series: [
    {
      name: 'End Use',
      data: chartData.value,
    },
  ],
}))
</script>

<template>
  <div class="enduse-donut">
    <div class="enduse-donut__heading">End-Use Breakdown</div>

    <div class="enduse-donut__chart-wrap">
      <Chart
        :key="JSON.stringify(breakdown)"
        constructor-type="chart"
        :options="chartOptions"
      />
    </div>

    <!-- Legend -->
    <div class="enduse-donut__legend">
      <div
        v-for="item in chartData"
        :key="item.name"
        class="enduse-donut__legend-item"
      >
        <span
          class="enduse-donut__legend-dot"
          :style="{ backgroundColor: item.color }"
        ></span>
        <span class="enduse-donut__legend-label">{{ item.name }}</span>
        <span class="enduse-donut__legend-pct">{{ item.y.toFixed(0) }}%</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.enduse-donut__heading {
  margin-bottom: 0.5rem;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-size: 0.75rem;
  font-weight: 600;
}

.enduse-donut__chart-wrap {
  width: 100%;
  max-width: 240px;
  margin: 0 auto;
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
  color: #64748b;
  flex: 1;
}

.enduse-donut__legend-pct {
  font-family: var(--font-mono);
  color: #475569;
  font-weight: 500;
}
</style>
