import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { PPopover } from './index'
import { PButton } from '@/components/PButton'
import { PTypography } from '@/components/PTypography'
import { PIcon } from '@/components/PIcon'
import { withZoomWarning } from '@/utils/stories'
import { PTextInput } from '@/components/PTextInput'

const popoverDirections = ['none', 'top', 'bottom', 'left', 'right']

const meta: Meta<typeof PPopover> = {
  component: PPopover,
  subcomponents: { PButton, PTypography, PIcon, PTextInput },
  title: 'Components/PPopover',
  argTypes: {
    defaultOpen: {
      control: 'boolean',
      description: 'Whether the popover is open by default',
    },
    open: {
      control: 'boolean',
      description: 'Whether the popover is open',
    },
    direction: {
      control: 'select',
      options: popoverDirections,
      description: 'The direction of the popover',
    },
    offset: {
      control: 'number',
      description: 'The offset of the popover',
    },
    showArrow: {
      control: 'boolean',
      description: 'Whether the popover should show an arrow',
    },
    showClose: {
      control: 'boolean',
      description: 'Whether the popover should show a close button',
    },
    openDuration: {
      control: 'number',
      description: 'The duration in milliseconds for the popover to open',
    },
    closeDuration: {
      control: 'number',
      description: 'The duration in milliseconds for the popover to close',
    },
    "onUpdate:open": {
      type: 'function',
      args: 'value: boolean',
      description: 'The function to call when the open state of the popover is updated',
    },
  },
  args: {
    defaultOpen: true,
    direction: 'bottom',
    offset: 6,
    showArrow: true,
    showClose: true,
  },
}

export default meta
export type Story = StoryObj<typeof PPopover>

export const Default: Story = {
  render: (args) => ({
    components: { PPopover, ...meta.subcomponents},
    setup() {
      return { args }
    },
    template: withZoomWarning(`
      <div class="flex flex-col items-center justify-center h-full w-full m-50">
        <PPopover v-bind="args">
          <template #trigger>
            <PButton variant="primary" appearance="contained">Open Popover</PButton>
          </template>
          <template #content>
            <div class="flex flex-col gap-2">
              <PTypography variant="h3">Popover Title</PTypography>
              <PTypography variant="body1">Popover Content</PTypography>
              <PTextInput
                label="Name"
                placeholder="Enter your name"
                id="name"
                required
                helperText="This will be used to identify you"
              />
              <PButton variant="primary" appearance="contained" class="w-full">Submit</PButton>
            </div>
          </template>
        </PPopover>
      </div>
    `, 'popover'),
  }),
}