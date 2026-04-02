import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { PBadge, badgeOptions } from './index'

const meta: Meta<typeof PBadge> = {
  title: 'Components/PBadge',
  component: PBadge,
  argTypes: {
    variant: {
      control: 'select',
      options: badgeOptions.variants,
    },
    appearance: {
      control: 'select',
      options: badgeOptions.appearances,
    },
  },
}

export default meta
type Story = StoryObj<typeof PBadge>

const defaultExportableCode = `<PBadge variant="primary" appearance="standard">
  1
</PBadge>`

export const Default: Story = {
  args: {
    default: '1',
    variant: 'primary',
    appearance: 'standard',
  },
  parameters: {
    exportableCode: defaultExportableCode,
  },
}

export const AllVariants: Story = {
  render: () => ({
    components: { PBadge },
    setup() {
      return { badgeOptions }
    },
    template: `
      <div v-for="variant in badgeOptions.variants" :key="variant" class="flex flex-wrap gap-2">
        <h2 class="text-lg font-semibold capitalize">{{ variant }}</h2>
        <div class="flex flex-wrap gap-2">
          <h3 class="text-md font-semibold capitalize">{{ appearance }}</h3>
          <PBadge v-for="appearance in badgeOptions.appearances" :key="appearance" :variant="variant" :appearance="appearance">
            1
          </PBadge>
        </div>
      </div>
    `,
  }),
}
