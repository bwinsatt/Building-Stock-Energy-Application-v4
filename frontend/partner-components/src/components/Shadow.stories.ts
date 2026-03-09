import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { defineComponent, type PropType } from 'vue'

/**
 * Shadow Effects for the Partner Design System
 */

interface ShadowInfo {
  name: string
  offset: string
  blur: string
  color: string
  useCase: string
}

const shadows: ShadowInfo[] = [
  { name: 'None', offset: 'none', blur: 'none', color: 'none', useCase: 'Base elements, flat buttons' },
  { name: 'SM', offset: 'X:0, Y:1', blur: '4', color: '0,0,0,0.16', useCase: 'Tooltips' },
  { name: 'MD', offset: 'X:0, Y:2', blur: '8', color: '0,0,0,0.20', useCase: 'Cards, dropdowns, pop-ups' },
  { name: 'LG', offset: 'X:0, Y:4', blur: '12', color: '0,0,0,0.24', useCase: 'Large modals, side panels, etc' },
]

const getToken = (name: string) => `shadow-${name.toLowerCase()}`

const ShadowSwatch = defineComponent({
  props: {
    shadow: { type: Object as PropType<ShadowInfo>, required: true },
  },
  setup({ shadow }) {
    const token = getToken(shadow.name)
    const sizeClass = shadow.name === 'MD' ? 'w-40 h-40' 
      : shadow.name === 'LG' ? 'w-[260px] h-[383px]' 
      : 'w-8 h-8'
    return { token, sizeClass }
  },
  template: `
    <div 
      :class="[
        'bg-card border border-solid flex-shrink-0',
        sizeClass,
        token,
        shadow.name === 'None' && 'border-dashed',
        shadow.name === 'SM' && 'rounded-sm',
        shadow.name === 'MD' && 'rounded-md'
      ]"
      :title="token"
    />
  `,
})

const CELL_CLASS = 'py-4 px-4'
const HEADER_CLASS = 'text-left py-3 px-4 text-sm font-medium text-foreground'

const ShadowRow = defineComponent({
  components: { ShadowSwatch },
  props: {
    shadow: { type: Object as PropType<ShadowInfo>, required: true },
    showCssVar: Boolean,
  },
  setup({ shadow }) {
    const token = getToken(shadow.name)
    const nameLower = shadow.name.toLowerCase()
    return { token, nameLower }
  },
  template: `
    <tr class="border-b border-border hover:bg-muted/50 transition-colors">
      <td class="${CELL_CLASS} align-middle">
        <div class="flex items-center">
          <ShadowSwatch :shadow="shadow" />
        </div>
      </td>
      <td class="${CELL_CLASS}">
        <code class="text-xs bg-muted px-2 py-1 rounded">{{ token }}</code>
      </td>
      <td class="${CELL_CLASS}">
        <div class="text-sm text-foreground">{{ shadow.offset }}</div>
      </td>
      <td class="${CELL_CLASS}">
        <div class="text-sm text-foreground">{{ shadow.blur }}</div>
      </td>
      <td class="${CELL_CLASS}">
        <div class="text-sm text-foreground">{{ shadow.color }}</div>
      </td>
      <td class="${CELL_CLASS}">
        <div class="text-sm text-muted-foreground">{{ shadow.useCase }}</div>
      </td>
      <td v-if="showCssVar" class="${CELL_CLASS}">
        <div class="flex flex-col gap-1 items-start">
          <code class="text-xs bg-muted px-2 py-1 rounded w-fit">--shadow-{{ nameLower }}</code>
          <code class="text-xs bg-muted px-2 py-1 rounded w-fit">--partner-shadow-{{ nameLower }}</code>
        </div>
      </td>
    </tr>
  `,
})

const ShadowTable = defineComponent({
  components: { ShadowRow },
  props: {
    shadows: { type: Array as PropType<ShadowInfo[]>, required: true },
    showCssVar: Boolean,
  },
  template: `
    <div class="border border-border rounded-lg overflow-hidden bg-card">
      <table class="w-full">
        <thead class="bg-muted/50">
          <tr class="border-b border-border">
            <th :class="\`${HEADER_CLASS} w-32\`">Example</th>
            <th :class="\`${HEADER_CLASS} w-40\`">Token</th>
            <th :class="\`${HEADER_CLASS} w-40\`">Offset(px)</th>
            <th :class="\`${HEADER_CLASS} w-32\`">Blur(px)</th>
            <th :class="\`${HEADER_CLASS} w-40\`">Color(rgba)</th>
            <th :class="HEADER_CLASS">Use Case Examples</th>
            <th v-if="showCssVar" :class="\`${HEADER_CLASS} w-64\`">CSS Variable</th>
          </tr>
        </thead>
        <tbody>
          <ShadowRow 
            v-for="shadow in shadows" 
            :key="shadow.name" 
            :shadow="shadow"
            :show-css-var="showCssVar"
          />
        </tbody>
      </table>
    </div>
  `,
})

export default {
  title: 'Design System/Shadow Effects',
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component: 'The shadow scale defines consistent elevation and depth throughout the Partner design system. Each shadow value is designed for specific use cases, from flat elements to elevated modals and panels.'
      },
    },
  },
} as Meta

type Story = StoryObj

export const ShadowEffects: Story = {
  render: () => ({
    components: { ShadowTable },
    setup: () => ({ shadows }),
    template: `
      <div class="min-h-screen font-sans p-8 transition-colors duration-300">
        <div class="border-b border-border pb-8 mb-8">
          <p class="text-base text-partner-blue-7 mb-2">Partner Design System</p>
          <h1 class="text-6xl font-light leading-tight tracking-tight mb-4">Shadow Effects</h1>
          <p class="text-sm text-muted-foreground leading-5">
            The shadow scale defines consistent elevation and depth throughout the Partner design system. 
            Each shadow value is designed for specific use cases, from flat elements to elevated modals and panels.
          </p>
        </div>
        <div>
          <ShadowTable :shadows="shadows" :show-css-var="true" />
        </div>
      </div>
    `,
  }),
}

