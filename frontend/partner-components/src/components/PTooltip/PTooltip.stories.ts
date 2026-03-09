import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { PTooltip, tooltipDirections } from './index'
import { PButton } from '@/components/PButton'
import { PIcon } from '@/components/PIcon'
import { PTypography } from '@/components/PTypography'
import { withZoomWarning } from '@/utils/stories'

const meta: Meta<typeof PTooltip> = {
  component: PTooltip,
  subcomponents: { PTypography, PIcon, PButton },
  title: 'Components/PTooltip',
  argTypes: {
    direction: {
      control: 'select',
      options: tooltipDirections,
    },
    open: {
      control: 'boolean',
      description: 'Whether the tooltip is open',
    },
    disabled: {
      control: 'boolean',
      description: 'Whether the tooltip is disabled',
    },
    disableClosingTrigger: {
      control: 'boolean',
      description: 'Whether the tooltip should not be closed when the trigger is clicked',
    },
    delayDuration: {
      control: 'number',
      description: 'The delay duration in milliseconds before the tooltip is opened',
    },
    skipDelayDuration: {
      control: 'number',
      description: 'How much time a user has to enter another trigger without incurring a delay again.',
    },
    closeDuration: {
      control: 'number',
      description: 'The duration in milliseconds for the tooltip to close',
    },
    'onUpdate:open': {
      type: 'function',
      args: 'value: boolean',
      description: 'The function to call when the open state of the tooltip is updated',
    },
  },
}

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    open: true,
    direction: 'none',
    disabled: true,
    disableClosingTrigger: true,
  },
  render: (args) => ({
    components: { PTooltip, ...meta.subcomponents},
    setup() {
      return { args }
    },
    template: 
      withZoomWarning(`
      <PTooltip v-bind="args" class="pointer-events-none">
        <template #tooltip-trigger>
          <p class="hidden">Hover me</p>
        </template>
        <template #tooltip-content>
          <div class="flex items-center gap-1"><PIcon name="information-filled" size="small" /> <p>Tooltip</p></div>
        </template>
      </PTooltip>
    `, 'tooltip'),
  }),
}

export const Examples: Story = {
  render: (args) => ({
    components: { PTooltip, ...meta.subcomponents},
    setup() {
      return { args, tooltipDirections }
    },
    template: withZoomWarning(`
      <div class="flex flex-col items-center gap-10 m-10">
        <div v-for="direction in tooltipDirections" :key="direction" class="relative inline-flex flex-col items-center">
          <PTooltip v-bind="args" :direction="direction">
            <template #tooltip-trigger>
              <PButton icon="information-filled" iconPosition="right">{{ direction }}</PButton>
            </template>
            <template #tooltip-content>
              <p>Hovered over me!</p>
            </template>
          </PTooltip>
        </div>
      </div>
    `, 'tooltip'),
  }),
}