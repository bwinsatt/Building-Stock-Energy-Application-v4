import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { defineComponent, ref, onMounted, type PropType, computed } from 'vue'

/**
 * PowerBI Color Palette - Data visualization color scales for the Partner Design System
 * Colors are read dynamically from CSS custom properties defined in partner-colors.css
 */

const meta = {
  title: 'Design System/PowerBI Color Palette',
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component: 'PowerBI color palettes for data visualization, including 5-point and 3-point scales for various data point focuses.',
      },
    },
  },
} satisfies Meta

export default meta
type Story = StoryObj<typeof meta>

const getCssVar = (v: string) => 
  typeof document !== 'undefined' ? getComputedStyle(document.documentElement).getPropertyValue(v).trim() || 'Not defined' : 'Not defined'

interface Row { token: string; useCase: string; value: string }
interface Section { title: string; rows: Row[] }
interface Scale { name: string; description: string; sections: Section[] }

const scaleData: Scale[] = [
  {
    name: '5 Point Scale',
    description: 'Default 5-point scale based on positive or negative data point focus.',
    sections: [
      {
        title: 'Highlights-Positive Data Points',
        rows: [
          { token: 'partner-powerbi-datapoint-positive-poor', useCase: 'Poor', value: 'partner-gray-1' },
          { token: 'partner-powerbi-datapoint-positive-poorfair', useCase: 'Poor-Fair', value: 'partner-gray-3' },
          { token: 'partner-powerbi-datapoint-positive-fair', useCase: 'Fair', value: 'partner-gray-6' },
          { token: 'partner-powerbi-datapoint-positive-goodfair', useCase: 'Good-Fair', value: 'partner-gray-7' },
          { token: 'partner-powerbi-datapoint-positive-good', useCase: 'Good', value: 'partner-blue-7' },
        ],
      },
      {
        title: 'Highlights-Negative Data Points',
        rows: [
          { token: 'partner-powerbi-datapoint-negative-poor', useCase: 'Poor', value: 'partner-red-6' },
          { token: 'partner-powerbi-datapoint-negative-poorfair', useCase: 'Poor-Fair', value: 'partner-gray-7' },
          { token: 'partner-powerbi-datapoint-negative-fair', useCase: 'Fair', value: 'partner-gray-6' },
          { token: 'partner-powerbi-datapoint-negative-goodfair', useCase: 'Good-Fair', value: 'partner-gray-3' },
          { token: 'partner-powerbi-datapoint-negative-good', useCase: 'Good', value: 'partner-gray-1' },
        ],
      },
      {
        title: 'Zero-like Central Value Data Set',
        rows: [
          { token: 'partner-powerbi-datapoint-neutral-negative-100', useCase: '-100%', value: 'partner-red-6' },
          { token: 'partner-powerbi-datapoint-neutral-negative-50', useCase: '-50%', value: 'partner-red-4' },
          { token: 'partner-powerbi-datapoint-neutral-0', useCase: '0%', value: 'partner-gray-3' },
          { token: 'partner-powerbi-datapoint-neutral-positive-50', useCase: '50%', value: 'partner-blue-4' },
          { token: 'partner-powerbi-datapoint-neutral-positive-100', useCase: '100%', value: 'partner-blue-7' },
        ],
      },
      {
        title: 'Partner Branded Heatmap (use sparingly)',
        rows: [
          { token: 'partner-powerbi-heatmap-branded-poor', useCase: 'Poor', value: 'partner-red-6' },
          { token: 'partner-powerbi-heatmap-branded-poorfair', useCase: 'Poor-Fair', value: 'partner-gray-3' },
          { token: 'partner-powerbi-heatmap-branded-fair', useCase: 'Fair', value: 'partner-gray-7' },
          { token: 'partner-powerbi-heatmap-branded-goodfair', useCase: 'Good-Fair', value: 'partner-blue-2' },
          { token: 'partner-powerbi-heatmap-branded-good', useCase: 'Good', value: 'partner-blue-7' },
        ],
      },
      {
        title: 'Traditional Heatmap (use sparingly)',
        rows: [
          { token: 'partner-powerbi-heatmap-traditional-poor', useCase: 'Poor', value: 'partner-red-6' },
          { token: 'partner-powerbi-heatmap-traditional-poorfair', useCase: 'Poor-Fair', value: 'partner-red-4' },
          { token: 'partner-powerbi-heatmap-traditional-fair', useCase: 'Fair', value: 'partner-yellow-4' },
          { token: 'partner-powerbi-heatmap-traditional-goodfair', useCase: 'Good-Fair', value: 'partner-green-4' },
          { token: 'partner-powerbi-heatmap-traditional-good', useCase: 'Good', value: 'partner-green-7' },
        ],
      },
    ],
  },
  {
    name: '3 Point Scale',
    description: 'Default 3-point scale based on positive or negative data point focus.',
    sections: [
      {
        title: 'Highlights-Positive Data Points',
        rows: [
          { token: 'partner-tbd', useCase: 'Poor', value: 'partner-white' },
          { token: 'partner-tbd', useCase: 'Fair', value: 'partner-gray-3' },
          { token: 'partner-tbd', useCase: 'Good', value: 'partner-blue-7' },
        ],
      },
      {
        title: 'Highlights-Negative Data Points',
        rows: [
          { token: 'partner-tbd', useCase: 'Poor', value: 'partner-red-6' },
          { token: 'partner-tbd', useCase: 'Fair', value: 'partner-gray-3' },
          { token: 'partner-tbd', useCase: 'Good', value: 'partner-white' },
        ],
      },
      {
        title: 'Partner Branded Heatmap (use sparingly)',
        rows: [
          { token: 'partner-tbd', useCase: 'Poor', value: 'partner-red-6' },
          { token: 'partner-tbd', useCase: 'Fair', value: 'partner-yellow-4' },
          { token: 'partner-tbd', useCase: 'Good', value: 'partner-blue-7' },
        ],
      },
    ],
  },
]


const ColorRow = defineComponent({
  props: { row: { type: Object as PropType<Row>, required: true } },
  setup({ row }) {
    const hex = ref(''), stroke = ref('')
    onMounted(() => { 
      hex.value = getCssVar(`--${row.value}`)
      stroke.value = getCssVar('--partner-gray-5')
    })
    return { hex, stroke }
  },
  template: `
    <tr class="border-b border-border hover:bg-muted/50 transition-colors">
      <td class="py-4 px-4">
        <code class="text-xs bg-muted px-2 py-1 rounded">{{ row.token }}</code>
      </td>
      <td class="py-4 px-4 text-sm text-muted-foreground">{{ row.useCase }}</td>
      <td class="py-4 px-4">
        <code class="text-xs text-muted-foreground">{{ row.value }}</code>
      </td>
      <td class="py-4 px-4">
        <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
          <circle cx="24" cy="24" r="23.5" :fill="hex" :stroke="stroke" />
        </svg>
      </td>
    </tr>
  `,
})

const ColorSection = defineComponent({
  components: { ColorRow },
  props: { section: { type: Object as PropType<Section>, required: true } },
  template: `
    <div class="mb-12">
      <h2 class="text-2xl font-light text-foreground mb-6">{{ section.title }}</h2>
      <div class="border border-border rounded-lg overflow-hidden bg-card">
        <table class="w-full">
          <thead class="bg-muted/50">
            <tr class="border-b border-border">
              <th class="text-left py-3 px-4 text-sm font-medium text-foreground w-96">Token</th>
              <th class="text-left py-3 px-4 text-sm font-medium text-foreground">Use Case</th>
              <th class="text-left py-3 px-4 text-sm font-medium text-foreground w-48">Value</th>
              <th class="text-left py-3 px-4 text-sm font-medium text-foreground w-24">Sample</th>
            </tr>
          </thead>
          <tbody>
            <ColorRow v-for="row in section.rows" :key="row.token" :row="row" />
          </tbody>
        </table>
      </div>
    </div>
  `,
})

// Reusable Scale Display component
const ScaleDisplay = defineComponent({
  components: { ColorSection },
  props: { scale: { type: Object as PropType<Scale>, required: true } },
  template: `
    <div>
      <h2 class="text-5xl font-light text-foreground mb-6">{{ scale.name }}</h2>
      <p class="text-sm text-muted-foreground mb-8">{{ scale.description }}</p>
      <ColorSection v-for="section in scale.sections" :key="section.title" :section="section" />
    </div>
  `,
})

// Create story factory function
const createScaleStory = (scaleName: string) => {
  return defineComponent({
    components: { ScaleDisplay },
    setup() {
      const scale = computed(() => scaleData.find(s => s.name === scaleName))
      return { scale }
    },
    template: `
      <div class="p-8 bg-background text-foreground font-sans transition-colors duration-300">
        <ScaleDisplay v-if="scale" :scale="scale" />
      </div>
    `,
  })
}

// Main story showing all scales
const AllScales = defineComponent({
  components: { ScaleDisplay },
  setup() {
    const scales = ref(scaleData)
    return { scales }
  },
  template: `
    <div class="min-h-screen font-sans p-8 transition-colors duration-300">
      <div class="border-b border-border pb-8 mb-12">
        <p class="text-base text-partner-blue-7 mb-2">Partner Design System</p>
        <h1 class="text-6xl font-light leading-tight tracking-tight mb-4">PowerBI Color Palette</h1>
        <p class="text-sm text-muted-foreground leading-5">
          PowerBI color palette for data visualization, including 5-point and 3-point scales for various data point focuses.
        </p>
      </div>
      <template v-for="(scale, index) in scales" :key="scale.name">
        <div :class="index > 0 ? 'pt-20 border-t-2 border-border' : ''">
          <ScaleDisplay :scale="scale" />
        </div>
      </template>
    </div>
  `,
})

export const AllPalettes: Story = {
  render: () => AllScales,
}

export const FivePointScale: Story = {
  render: () => createScaleStory('5 Point Scale'),
}

export const ThreePointScale: Story = {
  render: () => createScaleStory('3 Point Scale'),
}

