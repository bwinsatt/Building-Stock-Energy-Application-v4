import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { ref, onMounted, defineComponent, computed, type PropType } from 'vue'

/**
 * Border Radius for the Partner Design System
 * Radius values are read dynamically from CSS custom properties defined in partner-radius.css
 */

// Constants
const NOT_SPECIFIED = 'Not specified in design system'

// Helper functions
const getCssVar = (v: string) => typeof document !== 'undefined' ? getComputedStyle(document.documentElement).getPropertyValue(v).trim() : ''

const convertToPixels = (value: string): string => {
  if (value.includes('px')) return value === '9999px' ? '9999px (full)' : value
  if (value.includes('rem')) return `${parseFloat(value) * 16}px`
  return value
}

const getCssVarString = (name: string): string => {
  const nameLower = name.toLowerCase()
  return `--radius-${nameLower}, --partner-radius-${nameLower}`
}

// Types
interface RadiusInfo {
  name: string
  value: string
  cssVar: string
  pixelValue: string
  isDefined: boolean
  useCase: string | null
}

interface RadiusDef {
  name: string
  useCase: string | null
}

// Data
const radiusDefs: RadiusDef[] = [
  { name: 'None', useCase: 'Tables, grids, bare inputs' },
  { name: 'XS', useCase: null },
  { name: 'SM', useCase: 'Buttons, inputs, tooltips etc' },
  { name: 'MD', useCase: 'Cards, small pop ups, modals' },
  { name: 'LG', useCase: 'Larger modals, containers' },
  { name: 'XL', useCase: null },
  { name: '2XL', useCase: null },
  { name: '3XL', useCase: null },
  { name: 'Full', useCase: 'Chips, avatars' },
]

const buildRadius = ({ name, useCase }: RadiusDef): RadiusInfo => {
  const cssVar = getCssVarString(name)
  const firstVar = cssVar.split(',')[0].trim()
  const value = getCssVar(firstVar)
  const isDefined = value.length > 0
  
  return {
    name,
    value: isDefined ? value : 'Not defined',
    cssVar,
    pixelValue: isDefined ? convertToPixels(value) : 'N/A',
    isDefined,
    useCase: useCase || NOT_SPECIFIED,
  }
}

const buildRadiusList = (): RadiusInfo[] => radiusDefs.map(buildRadius)

const getSizeClass = (name: string): string => {
  if (name === 'MD') return 'w-[100px] h-[100px]'
  if (name === 'LG' || name.includes('XL')) return 'w-[500px] h-[100px]'
  return 'w-8 h-8' // 32px for None, SM, Full, and others
}

const RadiusSwatch = defineComponent({
  props: {
    radius: { type: Object as PropType<RadiusInfo>, required: true },
  },
  setup({ radius }) {
    const style = computed(() => ({
      borderRadius: radius.isDefined ? radius.value : '0',
    }))
    
    const containerClass = computed(() => [
      'border border-solid flex-shrink-0',
      getSizeClass(radius.name),
      radius.isDefined ? 'border-charcoal-5' : 'border-dashed border-destructive opacity-50'
    ])
    
    return { style, containerClass }
  },
  template: `
    <div :style="style" :class="containerClass" :title="\`\${radius.name} - \${radius.pixelValue}\`" />
  `,
})

const CELL_CLASS = 'py-4 px-4'
const HEADER_CLASS = 'text-left py-3 px-4 text-sm font-medium text-foreground'

const RadiusRow = defineComponent({
  components: { RadiusSwatch },
  props: {
    radius: { type: Object as PropType<RadiusInfo>, required: true },
    showCssVar: Boolean,
  },
  setup({ radius }) {
    const useCaseClass = computed(() => 
      radius.useCase && radius.useCase !== NOT_SPECIFIED 
        ? 'text-muted-foreground' 
        : 'text-muted-foreground/60 italic'
    )
    const cssVars = computed(() => radius.cssVar.split(',').map(v => v.trim()))
    return { useCaseClass, cssVars }
  },
  template: `
    <tr class="border-b border-border hover:bg-muted/50 transition-colors">
      <td :class="\`${CELL_CLASS} align-middle\`">
        <div class="flex items-center">
          <RadiusSwatch :radius="radius" />
        </div>
      </td>
      <td :class="CELL_CLASS">
        <div class="font-medium text-foreground">{{ radius.name }}</div>
      </td>
      <td :class="CELL_CLASS">
        <div class="text-sm text-foreground">{{ radius.pixelValue }}</div>
      </td>
      <td :class="CELL_CLASS">
        <div class="text-sm" :class="useCaseClass">{{ radius.useCase || '${NOT_SPECIFIED}' }}</div>
      </td>
      <td v-if="showCssVar" :class="CELL_CLASS">
        <div class="flex flex-col gap-1 items-start">
          <code v-for="(varName, index) in cssVars" :key="index" class="text-xs bg-muted px-2 py-1 rounded w-fit">
            {{ varName }}
          </code>
        </div>
      </td>
    </tr>
  `,
})

const RadiusTable = defineComponent({
  components: { RadiusRow },
  props: {
    radii: { type: Array as PropType<RadiusInfo[]>, required: true },
    showCssVar: Boolean,
  },
  template: `
    <div class="border border-border rounded-lg overflow-hidden bg-card">
      <table class="w-full">
        <thead class="bg-muted/50">
          <tr class="border-b border-border">
            <th :class="\`${HEADER_CLASS} w-32\`">Preview</th>
            <th :class="\`${HEADER_CLASS} w-32\`">Name</th>
            <th :class="\`${HEADER_CLASS} w-32\`">Value</th>
            <th :class="HEADER_CLASS">Use Case</th>
            <th v-if="showCssVar" :class="\`${HEADER_CLASS} w-64\`">CSS Variable</th>
          </tr>
        </thead>
        <tbody>
          <RadiusRow 
            v-for="radius in radii" 
            :key="radius.name" 
            :radius="radius"
            :show-css-var="showCssVar"
          />
        </tbody>
      </table>
    </div>
  `,
})

export default {
  title: 'Design System/Radius',
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component: 'The border radius scale defines consistent rounded corners throughout the Partner design system. Each radius value is designed for specific use cases, from subtle rounding to fully rounded pill shapes.'
      },
    },
  },
} as Meta

type Story = StoryObj

export const Radius: Story = {
  render: () => ({
    components: { RadiusTable },
    setup() {
      const radii = ref<RadiusInfo[]>([])
      onMounted(() => {
        radii.value = buildRadiusList()
      })
      return { radii }
    },
    template: `
      <div class="min-h-screen font-sans p-8 transition-colors duration-300">
        <div class="border-b border-border pb-8 mb-8">
          <p class="text-base text-partner-blue-7 mb-2">Partner Design System</p>
          <h1 class="text-6xl font-light leading-tight tracking-tight mb-4">Radius</h1>
          <p class="text-sm text-muted-foreground leading-5">
            The border radius scale defines consistent rounded corners throughout the Partner design system. 
            Each radius value is designed for specific use cases, from subtle rounding to fully rounded pill shapes.
          </p>
        </div>
        <div>
          <RadiusTable :radii="radii" :show-css-var="true" />
        </div>
      </div>
    `,
  }),
}

