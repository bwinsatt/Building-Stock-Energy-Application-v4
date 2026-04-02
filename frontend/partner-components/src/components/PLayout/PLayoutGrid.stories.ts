import type { Meta, StoryObj } from '@storybook/vue3-vite'
import PLayoutGrid from './PLayoutGrid.vue'
import PLayoutGridItem from './PLayoutGridItem.vue'

const meta: Meta<typeof PLayoutGrid> = {
  component: PLayoutGrid,
  title: 'Components/PLayoutGrid',
  parameters: {
    layout: 'fullscreen',
  },
  argTypes: {
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
  },
}

export default meta
type Story = StoryObj<typeof meta>

const defaultExportableCode = `<PLayoutGrid>
  <PLayoutGridItem>
    <div class="rounded border p-4">Primary content</div>
  </PLayoutGridItem>

  <PLayoutGridItem class="md:col-span-6">
    <div class="rounded border p-4">Left column</div>
  </PLayoutGridItem>

  <PLayoutGridItem class="md:col-span-6">
    <div class="rounded border p-4">Right column</div>
  </PLayoutGridItem>
</PLayoutGrid>`

export const Default: Story = {
  parameters: {
    exportableCode: defaultExportableCode,
  },
  render: (args) => ({
    components: { PLayoutGrid, PLayoutGridItem },
    setup() {
      return { args }
    },
    template: `
      <div class="h-[600px] bg-background flex flex-col">
        <PLayoutGrid v-bind="args">
          <PLayoutGridItem>
            <div class="bg-muted/30 p-4 rounded border border-charcoal-5">
              <h3 class="font-semibold mb-2 text-foreground">Grid Item 1</h3>
              <p class="text-sm text-muted-foreground">
                Basic grid item spanning full width at small breakpoint.
              </p>
            </div>
          </PLayoutGridItem>

          <PLayoutGridItem class="md:col-span-6">
            <div class="bg-muted/30 p-4 rounded border border-charcoal-5">
              <h3 class="font-semibold mb-2 text-foreground">Grid Item 2</h3>
              <p class="text-sm text-muted-foreground">
                Example item spanning 6 columns on medium screens.
              </p>
            </div>
          </PLayoutGridItem>

          <PLayoutGridItem class="md:col-span-6">
            <div class="bg-muted/30 p-4 rounded border border-charcoal-5">
              <h3 class="font-semibold mb-2 text-foreground">Grid Item 3</h3>
              <p class="text-sm text-muted-foreground">
                Another 6-column item to demonstrate the responsive grid.
              </p>
            </div>
          </PLayoutGridItem>
        </PLayoutGrid>
      </div>
    `,
  }),
}
