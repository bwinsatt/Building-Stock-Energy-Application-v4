import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { defineComponent, type PropType } from 'vue'
import { PLogo } from '@/components/PLogo'

/**
 * Logo Showcase for the Partner Design System
 * Displays all Partner brand logos and variations
 */

interface LogoData {
  name: string
  width?: string
  height?: string
}

// Main logos (left column)
const mainLogos: LogoData[] = [
  { name: 'SiteLynx', width: '134px', height: '32px' },
  { name: 'BlueLynx', width: '170px', height: '32px' },
  { name: 'PLINK', width: '72px', height: '32px' },
  { name: 'PLINK Training', width: '128px', height: '32px' },
  { name: 'PLINK Testing', width: '112px', height: '32px' },
  { name: 'Partner', width: '171px', height: '32px' },
]

// Favicon logos (middle column)
const faviconLogos: LogoData[] = [
  { name: 'Favicon SiteLynx', width: '72px', height: '72px' },
  { name: 'Favicon BlueLynx', width: '72px', height: '72px' },
  { name: 'Favicon PLINK', width: '72px', height: '72px' },
  { name: 'Favicon Partner', width: '72px', height: '72px' },
]

// Company logos (right column)
const companyLogos: LogoData[] = [
  { name: 'Partner Engineering and Science, Inc.', width: '126px', height: '35px' },
  { name: 'Partner', width: '186px', height: '35px' },
  { name: 'Partner Energy', width: '115px', height: '35px' },
  { name: 'Partner Valuation Advisors', width: '122px', height: '35px' },
  { name: 'Partner Property Consultants', width: '117px', height: '35px' },
  { name: 'NCS Partner', width: '119px', height: '35px' },
]

const LogoItem = defineComponent({
  components: { PLogo },
  props: {
    logo: { type: Object as PropType<LogoData>, required: true },
  },
  template: `
    <div class="flex items-center gap-4 py-3">
      <PLogo 
        :logo-name="logo.name"
        :width="logo.width || 'auto'"
        :height="logo.height || 'auto'"
        :alt="logo.name"
        class="object-contain"
      />
      <span class="text-sm text-muted-foreground">{{ logo.name }}</span>
    </div>
  `,
})

const LogoColumn = defineComponent({
  components: { LogoItem },
  props: {
    title: { type: String, required: false, default: undefined },
    logos: { type: Array as PropType<LogoData[]>, required: true },
    showBorder: Boolean,
  },
  template: `
    <div :class="['flex flex-col', showBorder && 'border border-dashed border-purple-500 rounded-lg p-6']">
      <h3 v-if="title" class="text-lg font-semibold mb-4 text-foreground">{{ title }}</h3>
      <div class="flex flex-col gap-2">
        <LogoItem v-for="logo in logos" :key="logo.name" :logo="logo" />
      </div>
    </div>
  `,
})

export default {
  title: 'Design System/Logo',
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component: 'Partner Design System logo variations and brand guidelines. All logos maintain consistent styling and proportions across different applications.'
      },
    },
  },
} as Meta

type Story = StoryObj

export const Logo: Story = {
  render: () => ({
    components: { LogoColumn },
    setup: () => ({ mainLogos, faviconLogos, companyLogos }),
    template: `
      <div class="min-h-screen font-sans p-8 transition-colors duration-300">
        <div class="border-b border-border pb-8 mb-8">
          <p class="text-base text-partner-blue-7 mb-2">Partner Design System</p>
          <h1 class="text-6xl font-light leading-tight tracking-tight mb-4">Logo</h1>
          <p class="text-sm text-muted-foreground leading-5">
            Partner Design System logo variations and brand guidelines. 
            All logos maintain consistent styling and proportions across different applications.
          </p>
        </div>
        <div class="grid grid-cols-3 gap-8">
          <LogoColumn :logos="mainLogos" :show-border="true" />
          <LogoColumn title="Favicon" :logos="faviconLogos" :show-border="true" />
          <LogoColumn title="Company Logos" :logos="companyLogos" />
        </div>
      </div>
    `,
  }),
}

