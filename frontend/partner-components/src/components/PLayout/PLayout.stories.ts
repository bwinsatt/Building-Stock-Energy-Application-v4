import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { ref, onMounted, onUnmounted } from 'vue'
import PLayout from './PLayout.vue'
import PLayoutGridItem from './PLayoutGridItem.vue'

const meta: Meta<typeof PLayout> = {
  component: PLayout,
  title: 'Components/PLayout',
  parameters: {
    layout: 'fullscreen',
  },
  argTypes: {
    header: {
      control: 'boolean',
      description: 'Show or hide the header',
    },
    leftPanel: {
      control: 'boolean',
      description: 'Show or hide the left panel',
    },
    rightPanel: {
      control: 'boolean',
      description: 'Show or hide the right panel',
    },
    footer: {
      control: 'boolean',
      description: 'Show or hide the footer',
    },
    gutterSm: {
      control: 'text',
      description: 'Custom gutter value for small breakpoint (e.g., "24px", "1.5rem")',
    },
    gutterMd: {
      control: 'text',
      description: 'Custom gutter value for medium breakpoint (e.g., "24px", "1.5rem")',
    },
    gutterLg: {
      control: 'text',
      description: 'Custom gutter value for large breakpoint (e.g., "32px", "2rem")',
    },
    gutterXl: {
      control: 'text',
      description: 'Custom gutter value for extra-large breakpoint (e.g., "32px", "2rem")',
    },
    // Event handlers for Actions panel
    'onLeft-panel-hidden': { action: 'left-panel-hidden', table: { disable: true } },
    'onLeft-panel-shown': { action: 'left-panel-shown', table: { disable: true } },
    'onRight-panel-hidden': { action: 'right-panel-hidden', table: { disable: true } },
    'onRight-panel-shown': { action: 'right-panel-shown', table: { disable: true } },
  },
}

export default meta
type Story = StoryObj<typeof meta>

const baseArgs = {
  header: true,
  leftPanel: true,
  rightPanel: true,
  footer: false,
}

const layoutContent = `
  <PLayout v-bind="args">
    <template #header>
      <p class="text-lg text-foreground">Header</p>
    </template>
    <template #left-panel>
      <p class="text-lg text-foreground">Left Panel</p>
    </template>
    <template #body>
      <PLayoutGridItem>
        <div class="bg-muted/30 p-4 rounded border border-charcoal-5">
          <h3 class="font-semibold mb-2 text-foreground">Grid Item 1</h3>
          <p class="text-sm text-muted-foreground">Default col-span-full - Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.</p>
        </div>
      </PLayoutGridItem>
      <PLayoutGridItem class="md:col-span-9">
        <div class="bg-muted/30 p-4 rounded border border-charcoal-5">
          <h3 class="font-semibold mb-2 text-foreground">Grid Item 3 (Override Example)</h3>
          <p class="text-sm text-muted-foreground">Override: Display full in small viewport, half column size otherwise.</p>
        </div>
      </PLayoutGridItem>
      <PLayoutGridItem class="md:col-span-3">
        <div class="bg-muted/30 p-4 rounded border border-charcoal-5">
          <h3 class="font-semibold mb-2 text-foreground">Grid Item 2</h3>
          <p class="text-sm text-muted-foreground">Override: Same thing.</p>
        </div>
      </PLayoutGridItem>
    </template>
    <template #right-panel>
      <p class="text-lg text-foreground">Right Panel</p>
    </template>
    <template #footer>
      <div class="border-t border-charcoal-5 p-4">
        <p class="text-sm text-muted-foreground text-center">Footer</p>
      </div>
    </template>
  </PLayout>
`

const gridOverlay = `
  <div class="absolute inset-0 pointer-events-none z-(--partner-z-overlay)">
    <div class="h-full flex flex-col">
      <!-- Header spacer -->
      <div v-if="args.header" class="h-[53px] shrink-0"></div>
      
      <!-- Main content area with panels -->
      <div class="flex flex-1 min-h-0">
        <div v-if="args.leftPanel" class="hidden md:block w-[250px]"></div>
        <div class="flex-1 flex flex-col min-h-0 min-w-0 py-[var(--breakpoint-sm-padding-tb)] md:py-[var(--breakpoint-md-padding-tb)] lg:py-[var(--breakpoint-lg-padding-tb)] xl:py-[var(--breakpoint-xl-padding-tb)]">
          <div class="flex-1 min-h-0 min-w-0 relative mx-[var(--breakpoint-sm-margin-lr)] md:mx-[var(--breakpoint-md-margin-lr)] lg:mx-[var(--breakpoint-lg-margin-lr)] xl:mx-[var(--breakpoint-xl-margin-lr)]">
            <div class="absolute inset-0 bg-primary-400/5"></div>
            <div class="absolute inset-0 grid w-full gap-[var(--breakpoint-sm-gutters)] md:gap-[var(--breakpoint-md-gutters)] lg:gap-[var(--breakpoint-lg-gutters)] xl:gap-[var(--breakpoint-xl-gutters)]"
                 :class="[
                   '[grid-template-columns:var(--grid-cols-sm)]',
                   'md:[grid-template-columns:var(--grid-cols-md)]',
                   'lg:[grid-template-columns:var(--grid-cols-lg)]',
                   'xl:[grid-template-columns:var(--grid-cols-xl)]',
                 ]">
              <template v-for="i in 12" :key="i">
                <div class="border-l-2 border-dotted border-primary-400/50" :class="i > 8 ? 'hidden md:block' : ''"></div>
              </template>
            </div>
          </div>
          <div class="absolute bottom-2 left-2 bg-white/95 dark:bg-gray-900/95 backdrop-blur-sm px-3 py-2 rounded border-2 border-primary-400 shadow-sm">
            <div class="text-xs font-mono">
              <div class="flex items-center gap-2 mb-1">
                <div class="w-2 h-2 rounded-full bg-primary-400 border border-primary-500"></div>
                <div class="text-primary-500 font-semibold">Grid Overlay</div>
              </div>
              <div class="text-[10px] text-gray-600 dark:text-gray-400 space-y-0.5">
                <div class="font-semibold text-gray-900 dark:text-gray-100 mb-1">Viewport: {{ viewportWidth }} × {{ viewportHeight }}px</div>
                <div>SM: <span class="font-semibold text-gray-900 dark:text-gray-100">8 cols</span>, Gutter: <span class="font-semibold text-gray-900 dark:text-gray-100">24px</span></div>
                <div class="md:block hidden">MD+: <span class="font-semibold text-gray-900 dark:text-gray-100">12 cols</span>, Gutter: <span class="font-semibold text-gray-900 dark:text-gray-100">24px</span> (md) / <span class="font-semibold text-gray-900 dark:text-gray-100">32px</span> (lg/xl)</div>
              </div>
              <div class="text-[9px] text-gray-500 dark:text-gray-500 mt-1 pt-1 border-t border-gray-200 dark:border-gray-700">
                <div>Gray borders = actual page borders</div>
              </div>
            </div>
          </div>
        </div>
        <div v-if="args.rightPanel" class="hidden md:block w-[250px]"></div>
      </div>
      
      <!-- Footer spacer to stop grid lines before footer -->
      <div v-if="args.footer" class="shrink-0 h-12"></div>
    </div>
  </div>
`

const createRender = (showGrid = false) => (args: typeof baseArgs) => ({
  components: { PLayout, PLayoutGridItem },
  setup() {
    const viewportWidth = ref(0)
    const viewportHeight = ref(0)

    const updateViewportSize = () => {
      viewportWidth.value = window.innerWidth
      viewportHeight.value = window.innerHeight
    }

    onMounted(() => {
      updateViewportSize()
      window.addEventListener('resize', updateViewportSize)
    })

    onUnmounted(() => {
      window.removeEventListener('resize', updateViewportSize)
    })

    return { args, viewportWidth, viewportHeight }
  },
  template: `<div class="h-screen w-screen relative">${layoutContent}${showGrid ? gridOverlay : ''}</div>`,
})

const defaultExportableCode = `<PLayout :header="true" :left-panel="true" :right-panel="true">
  <template #header>
    <div class="p-4">Header</div>
  </template>

  <template #left-panel>
    <div class="p-4">Filters</div>
  </template>

  <template #body>
    <PLayoutGridItem>
      <div class="rounded border p-4">Main content</div>
    </PLayoutGridItem>
    <PLayoutGridItem class="md:col-span-4">
      <div class="rounded border p-4">Secondary content</div>
    </PLayoutGridItem>
  </template>

  <template #right-panel>
    <div class="p-4">Details</div>
  </template>
</PLayout>`

export const Default: Story = {
  args: baseArgs,
  parameters: {
    exportableCode: defaultExportableCode,
  },
  render: createRender(false),
}

export const WithGridVisualization: Story = {
  args: baseArgs,
  render: createRender(true),
}
