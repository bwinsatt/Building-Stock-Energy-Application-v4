import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { PChip } from './index'
import { PIcon } from '@/components/PIcon'
import { allVariantsTemplate, chipVariants, chipAppearances, chipSizes } from './storyCommon'

const meta: Meta<typeof PChip> = {
  title: 'Components/PChip',
  component: PChip,
}

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    variant: 'primary',
    appearance: 'contained',
    size: 'medium',
    disabled: false,
  },
  argTypes: {
    variant: {
      control: 'select',
      options: chipVariants,
    },
    appearance: {
      control: 'select',
      options: chipAppearances,
    },
    size: {
      control: 'select',
      options: chipSizes,
    },
    disabled: {
      control: 'boolean',
    },
    removable: {
      control: 'boolean',
    },
    removed: {
      control: 'boolean',
    },
    selectable: {
      control: 'boolean',
    },
    selected: {
      control: 'boolean',
    },
    onRemove: {
      type: 'function',
      description: 'Fired when the remove icon is clicked'
    },
    onSelect: {
      type: 'function',
      args: 'value: boolean',
      description: 'Fired when the chip is clicked'
    }
  },
  render: (args) => ({
    components: { PChip },
    setup() {
      return { args }
    },
    template: `
      <div class="flex flex-col items-center gap-1">
        <div class="flex w-full flex-wrap gap-1">
          <PChip v-bind="args">
            Chip
          </PChip>
        </div>
      </div>
    `,
  }),
}

export const ReadOnly: Story = {
  render: () => ({
    components: { PChip },
    setup() {
      return {
        chipVariants,
        chipAppearances,
        chipSizes,
      }
    },
    template: allVariantsTemplate,
  }),
}

export const Removable: Story = {
  args: {
    removable: true,
  },
  argTypes: {
    removable: {
      control: 'boolean',
    },
    removed: {
      control: 'boolean',
    },
    onRemove: {
      type: 'function',
      description: 'Fired when the remove icon is clicked'
    }
  },
  render: (args) => ({
    components: { PChip },
    setup() {
      return {
        args,
        chipVariants,
        chipAppearances,
        chipSizes,
      }
    },
    template: allVariantsTemplate,
  }),
}

export const Selectable: Story = {
  args: {
    selectable: true,
  },
  argTypes: {
    selectable: {
      control: 'boolean',
    },
    selected: {
      control: 'boolean',
    },
    onSelect: {
      type: 'function',
      args: 'value: boolean',
      description: 'Fired when the chip is clicked'
    }
  },
  render: (args) => ({
    components: { PChip },
    setup() {
      return {
        args,
        chipVariants,
        chipAppearances,
        chipSizes,
      }
    },
    template: allVariantsTemplate,
  }),
}

export const CustomizedSlots: Story = {
  args: {
    selectable: true,
    removable: true,
  },
  argTypes: {
    removable: {
      control: 'boolean',
    },
    removed: {
      control: 'boolean',
    },
    onRemove: {
      type: 'function',
      description: 'Fired when the remove icon is clicked'
    },
    selectable: {
      control: 'boolean',
    },
    selected: {
      control: 'boolean',
    },
    onSelect: {
      type: 'function',
      description: 'Fired when the chip is clicked'
    }
  },
  render: (args) => ({
    components: { PChip, PIcon },
    setup() {
      return {
        args,
        chipVariants,
        chipAppearances,
        chipSizes,
      }
    },
    template: `
      <div class="flex flex-col items-center gap-1">
        <div class="flex w-full flex-wrap gap-1">
          <PChip v-bind="args">
            <template #left>
              <PIcon name="globe" size="small" />
            </template>
            Chip
            <template #right>
              <PIcon name="go-to" size="small" />
            </template>
          </PChip>
        </div>
      </div>
    `,
  }),
}