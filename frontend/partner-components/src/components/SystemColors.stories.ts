import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { ref, onMounted, defineComponent, type PropType } from 'vue'

/**
 * System Colors - Semantic color tokens for the Partner Design System
 * Colors are read dynamically from CSS custom properties defined in partner-colors.css
 */

const getCssVar = (v: string) => typeof document !== 'undefined' ? getComputedStyle(document.documentElement).getPropertyValue(v).trim() : ''

interface SystemColorRow {
  token: string
  description: string
  value: string
}

const systemColorGroups = [
  {
    name: 'Primary',
    colors: [
      { token: 'partner-primary-main', description: 'Core brand color used in primary components such as buttons, links, and highlights.', value: '--partner-blue-7' },
      { token: 'partner-primary-dark', description: 'Darker shade, typically used for pressed or active states.', value: '--partner-blue-8' },
      { token: 'partner-primary-light', description: 'Lighter shade, commonly used for hover states or subtle emphasis.', value: '--partner-blue-6' },
      { token: 'partner-primary-contrast', description: 'Foreground color that maintains AA contrast when primary-main is used as a background.', value: '--partner-white' },
      { token: 'partner-primary-outlined-border', description: 'Border color for outlined & text variant components (Button, etc)', value: '--partner-blue-5' },
      { token: 'partner-primary-outlined-hovered', description: 'Background color for outlined and text button variants when hovered.', value: '--partner-blue-1' },
      { token: 'partner-primary-outlined-hover-pressed', description: 'Background color for outlined and text button variants when pressed.', value: '--partner-blue-2' },
      { token: 'partner-primary-content', description: 'Text/icon color used within components like buttons and tags.', value: '--partner-blue-7' },
    ]
  },
  {
    name: 'Secondary',
    colors: [
      { token: 'partner-secondary-main', description: 'Core secondary brand color used in secondary buttons, highlights, and accents.', value: '--partner-orange-7' },
      { token: 'partner-secondary-dark', description: 'Darker shade, typically used for pressed or active states.', value: '--partner-orange-8' },
      { token: 'partner-secondary-light', description: 'Lighter shade, commonly used for hover states or subtle emphasis.', value: '--partner-orange-6' },
      { token: 'partner-secondary-contrast', description: 'Foreground color that maintains AA contrast when secondary-main is used as a background.', value: '--partner-white' },
      { token: 'partner-secondary-outlined-border', description: 'Border color for outlined & text variant components (Button, etc)', value: '--partner-orange-5' },
      { token: 'partner-secondary-outlined-hovered', description: 'Fill background color for outlined & text variant components in hover state (Button, etc)', value: '--partner-orange-1' },
      { token: 'partner-secondary-outlined-hover-pressed', description: 'Fill background color for outlined & text variant components in pressed state (Button, etc)', value: '--partner-orange-2' },
      { token: 'partner-secondary-content', description: 'Text/icon color used within components like buttons and tags.', value: '--partner-orange-9' },
    ]
  },
  {
    name: 'Success',
    colors: [
      { token: 'partner-success-main', description: 'Used for alert components, including icons, button text, etc', value: '--partner-green-7' },
      { token: 'partner-success-dark', description: 'Darker shade, typically used for pressed or active states.', value: '--partner-green-8' },
      { token: 'partner-success-light', description: 'Lighter shade, commonly used for hover states or subtle emphasis.', value: '--partner-green-6' },
      { token: 'partner-success-contrast', description: 'Foreground color that maintains AA contrast when success-main is used as a background.', value: '--partner-white' },
      { token: 'partner-success-outlined-border', description: 'Border color for outlined & text variant components (Button, etc)', value: '--partner-green-5' },
      { token: 'partner-success-outlined-hovered', description: 'Fill background color for outlined & text variant components in hover state (Button, etc)', value: '--partner-green-1' },
      { token: 'partner-success-outlined-hover-pressed', description: 'Fill background color for outlined & text variant components in pressed state (Button, etc)', value: '--partner-green-2' },
      { token: 'partner-success-content', description: 'Text/icon color used within components like buttons and tags.', value: '--partner-green-9' },
    ]
  },
  {
    name: 'Warning',
    colors: [
      { token: 'partner-warning-main', description: 'Used for alert components, including icons, button text, etc', value: '--partner-yellow-7' },
      { token: 'partner-warning-dark', description: 'Darker shade, typically used for pressed or active states.', value: '--partner-yellow-8' },
      { token: 'partner-warning-light', description: 'Lighter shade, commonly used for hover states or subtle emphasis.', value: '--partner-yellow-6' },
      { token: 'partner-warning-contrast', description: 'Foreground color that maintains AA contrast when warning-main is used as a background.', value: '--partner-black' },
      { token: 'partner-warning-outlined-bordered', description: 'Border color for outlined & text variant components (Button, etc)', value: '--partner-yellow-5' },
      { token: 'partner-warning-outlined-hover', description: 'Fill background color for outlined & text variant components in hover state (Button, etc)', value: '--partner-yellow-1' },
      { token: 'partner-warning-outlined-hover-pressed', description: 'Fill background color for outlined & text variant components in pressed state (Button, etc)', value: '--partner-yellow-2' },
      { token: 'partner-warning-content', description: 'Text/icon color used within components like buttons and tags.', value: '--partner-yellow-10' },
    ]
  },
  {
    name: 'Error',
    colors: [
      { token: 'partner-error-main', description: 'Used for alert components, including icons, button text, etc', value: '--partner-red-7' },
      { token: 'partner-error-dark', description: 'Darker shade, typically used for pressed or active states.', value: '--partner-red-8' },
      { token: 'partner-error-light', description: 'Lighter shade, commonly used for hover states or subtle emphasis.', value: '--partner-red-6' },
      { token: 'partner-error-contrast', description: 'Foreground color that maintains AA contrast when error-main is used as a background.', value: '--partner-white' },
      { token: 'partner-error-outlined-border', description: 'Border color for outlined & text variant components (Button, etc)', value: '--partner-red-5' },
      { token: 'partner-error-outlined-hovered', description: 'Fill background color for outlined & text variant components in hover state (Button, etc)', value: '--partner-red-1' },
      { token: 'partner-error-outlined-hover-pressed', description: 'Fill background color for outlined & text variant components in pressed state (Button, etc)', value: '--partner-red-2' },
      { token: 'partner-error-content', description: 'Text/icon color used within components like buttons and tags.', value: '--partner-red-9' },
    ]
  },
  {
    name: 'Inherit - Black',
    colors: [
      { token: 'partner-inherit-black-main', description: 'Used for alert components, including icons, button text, etc', value: '--partner-black' },
      { token: 'partner-inherit-black-border', description: 'Border color for outlined & text variant components (Button, etc)', value: '--partner-black @50%' },
      { token: 'partner-inherit-black-hovered', description: 'Fill background color for outlined & text variant components in hover state (Button, etc)', value: '--partner-black @5%' },
      { token: 'partner-inherit-black-pressed', description: 'Foreground color that maintains AA contrast when inherit-black-main is used as a background.', value: '--partner-black @10%' },
      { token: 'partner-inherit-black-disabled', description: 'Fill background color for outlined & text variant components in disabled state (Button, etc)', value: '--partner-black @25%' },
    ]
  },
  {
    name: 'Inherit - White',
    colors: [
      { token: 'partner-inherit-white-main', description: 'Used for alert components, including icons, button text, etc', value: '--partner-white' },
      { token: 'partner-inherit-white-border', description: 'Border color for outlined & text variant components (Button, etc)', value: '--partner-white @50%' },
      { token: 'partner-inherit-white-hovered', description: 'Fill background color for outlined & text variant components in hover state (Button, etc)', value: '--partner-white @5%' },
      { token: 'partner-inherit-white-pressed', description: 'Foreground color that maintains AA contrast when inherit-white-main is used as a background.', value: '--partner-white @15%' },
      { token: 'partner-inherit-white-disabled', description: 'Fill background color for outlined & text variant components in disabled state (Button, etc)', value: '--partner-white @25%' },
    ]
  },
  {
    name: 'Text',
    colors: [
      { token: 'partner-text-primary', description: 'Primary text color used for high-emphasis content such as body text, titles, and headings.', value: '--partner-gray-7' },
      { token: 'partner-text-secondary', description: 'Used for secondary or supporting text such as input labels, subheadings, and unselected tabs.', value: '--partner-gray-6' },
      { token: 'partner-text-disabled', description: 'Text color used for disabled elements, including buttons, inputs, and form field labels.', value: '--partner-gray-5' },
      { token: 'partner-text-placeholder', description: 'Text color used specifically for placeholder text within input fields and form elements.', value: '--partner-gray-5' },
      { token: 'partner-text-white', description: 'High-contrast text color used on dark or colored backgrounds (e.g., buttons, banners).', value: '--partner-white' },
    ]
  },
  {
    name: 'Action',
    colors: [
      { token: 'partner-action-enabled', description: 'Default color for interactive elements in their enabled state — used in icons, list items, tables, and menus.', value: '--partner-gray-7' },
      { token: 'partner-action-active', description: 'Default color for interactive elements in their active state.', value: '--partner-blue-7' },
      { token: 'partner-action-disabled', description: 'Color used for interactive elements in a disabled state.', value: '--partner-gray-5' },
    ]
  },
  {
    name: 'Border',
    colors: [
      { token: 'partner-border-default', description: 'Default border color for components in a neutral or resting state. Commonly used for inputs, containers, and cards.', value: '--partner-gray-5' },
      { token: 'partner-border-light', description: 'Lightest border used for subtle separators, low-emphasis containers, or light surfaces like tables.', value: '--partner-gray-2' },
      { token: 'partner-border-hovered', description: 'Default border color for components in a hover state. Commonly used for inputs, containers, and cards.', value: '--partner-gray-7' },
      { token: 'partner-border-active', description: 'High-contrast border used for interactive elements in focused, active, or selected states.', value: '--partner-blue-7' },
      { token: 'partner-border-disabled', description: 'Border color for components in a disabled or non-interactive state. Visually indicates inaccessibility.', value: '--partner-gray-3' },
      { token: 'partner-border-divider', description: 'Used for visual dividers between sections or elements, such as lists, sidebars, or page layouts.', value: '--partner-gray-5' },
    ]
  },
  {
    name: 'Fill',
    colors: [
      { token: 'partner-fill-hover', description: 'Background color applied to interactive elements on hover to indicate affordance (e.g., list items, icon buttons).', value: '--partner-gray-7 @5%' },
      { token: 'partner-fill-pressed', description: 'Background fill used for components in pressed state.', value: '--partner-gray-7 @15%' },
      { token: 'partner-fill-selected', description: 'Background fill used for components in selected state.', value: '--partner-blue-1' },
      { token: 'partner-fill-disabled', description: 'Background fill used for disabled components to indicate inactivity or unavailability.', value: '--partner-gray-7 @5%' },
      { token: 'partner-fill-tooltip', description: 'Background fill used for tooltip components.', value: '--partner-gray-7 @90%' },
    ]
  },
  {
    name: 'Background',
    colors: [
      { token: 'partner-background-white', description: 'Primary background color for the UI surface, typically used for pages, shells, and containers.', value: '--partner-white' },
      { token: 'partner-background-gray', description: 'Secondary background color used for subtle layering, such as cards, inputs, or secondary containers.', value: '--partner-gray-1' },
      { token: 'partner-background-overlay', description: 'Semi-transparent overlay color used behind modals, dialogs, or drawers to dim the background content.', value: '--partner-gray-7 @45%' },
    ]
  },
]

const ColorRow = defineComponent({
  props: {
    color: { type: Object as PropType<SystemColorRow>, required: true },
  },
  setup({ color }) {
    const hex = ref(getCssVar(color.value))
    const strokeColor = ref(getCssVar('--partner-gray-5'))
    
    // Extract opacity from value if it has @XX% format (e.g., "charcoalgray-7 @5%")
    const opacity = ref(1)
    
    onMounted(() => {
      const rawValue = color.value
      hex.value = getCssVar(color.value.replace(/ @\d+%/, '')) // Remove opacity from CSS var name
      strokeColor.value = getCssVar('--partner-gray-5')
      
      // Parse opacity if present (e.g., "@5%" -> 0.05, "@87%" -> 0.87)
      const opacityMatch = rawValue.match(/@(\d+)%/)
      if (opacityMatch) {
        opacity.value = parseInt(opacityMatch[1]) / 100
      }
    })
    
    return { hex, strokeColor, opacity }
  },
  template: `
    <tr class="border-b border-border hover:bg-muted/50 transition-colors">
      <td class="py-4 px-4">
        <code class="text-xs bg-muted px-2 py-1 rounded">{{ color.token }}</code>
      </td>
      <td class="py-4 px-4 text-sm text-muted-foreground">{{ color.description }}</td>
      <td class="py-4 px-4">
        <code class="text-xs text-muted-foreground">{{ color.value }}</code>
      </td>
      <td class="py-4 px-4">
        <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48" fill="none" :title="hex">
          <circle cx="24" cy="24" r="23.5" :fill="hex" :fill-opacity="opacity" :stroke="strokeColor" />
        </svg>
      </td>
    </tr>
  `,
})

const ColorTable = defineComponent({
  components: { ColorRow },
  props: {
    name: String,
    colors: { type: Array as PropType<SystemColorRow[]>, required: true },
  },
  template: `
    <div class="mb-12">
      <h2 class="text-2xl font-light text-foreground mb-6">{{ name }}</h2>
      <div class="border border-border rounded-lg overflow-hidden bg-card">
        <table class="w-full">
          <thead class="bg-muted/50">
            <tr class="border-b border-border">
              <th class="text-left py-3 px-4 text-sm font-medium text-foreground w-96">Token</th>
              <th class="text-left py-3 px-4 text-sm font-medium text-foreground">Description</th>
              <th class="text-left py-3 px-4 text-sm font-medium text-foreground w-48">Value</th>
              <th class="text-left py-3 px-4 text-sm font-medium text-foreground w-24">Sample</th>
            </tr>
          </thead>
          <tbody>
            <ColorRow v-for="color in colors" :key="color.token" :color="color" />
          </tbody>
        </table>
      </div>
    </div>
  `,
})

export default {
  title: 'Design System/System Colors',
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component: 'System colors are semantic color tokens that map to specific use cases in the Partner Design System. They reference the base color palette and provide consistent, meaningful color names for UI components.'
      },
    },
  },
} as Meta

type Story = StoryObj

export const SystemColors: Story = {
  render: () => ({
    components: { ColorTable },
    setup() {
      return { groups: systemColorGroups }
    },
    template: `
      <div class="min-h-screen font-sans p-8 transition-colors duration-300">
        <div class="border-b border-border pb-8 mb-8">
          <p class="text-base text-partner-blue-7 mb-2">Partner Design System</p>
          <h1 class="text-6xl font-light leading-tight tracking-tight mb-4">System Colors</h1>
          <p class="text-sm text-muted-foreground leading-5">
            Semantic color tokens mapped to specific use cases. These colors reference the base palette and ensure consistent, accessible color application across all components.
          </p>
        </div>
        <ColorTable v-for="group in groups" :key="group.name" :name="group.name" :colors="group.colors" />
      </div>
    `,
  }),
}

// Individual category stories
const createCategoryStory = (groupName: string): Story => ({
  render: () => ({
    components: { ColorTable },
    setup() {
      const group = systemColorGroups.find(g => g.name === groupName)
      return { group }
    },
    template: `
      <div class="p-8 bg-background text-foreground font-sans transition-colors duration-300">
        <ColorTable v-if="group" :name="group.name" :colors="group.colors" />
      </div>
    `,
  }),
})

export const Primary = createCategoryStory('Primary')
export const Secondary = createCategoryStory('Secondary')
export const Success = createCategoryStory('Success')
export const Warning = createCategoryStory('Warning')
export const Error = createCategoryStory('Error')
export const InheritBlack = createCategoryStory('Inherit - Black')
export const InheritWhite = createCategoryStory('Inherit - White')
export const Text = createCategoryStory('Text')
export const Action = createCategoryStory('Action')
export const Border = createCategoryStory('Border')
export const Fill = createCategoryStory('Fill')
export const Background = createCategoryStory('Background')

