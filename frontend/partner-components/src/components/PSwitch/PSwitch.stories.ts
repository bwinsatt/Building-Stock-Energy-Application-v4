import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { action } from 'storybook/actions'
import { PSwitch } from './index'

const meta: Meta<typeof PSwitch> = {
  component: PSwitch,
  title: 'Components/PSwitch',
  argTypes: {
    modelValue: {
      control: 'boolean',
      description: 'The model value for the switch',
    },
    defaultValue: {
      control: 'boolean',
      description: 'The default value for the switch',
    },
    disabled: {
      control: 'boolean',
      description: 'Whether the switch is disabled',
    },
    label: {
      control: 'text',
      description: 'The label for the switch',
    },
    id: {
      control: 'text',
      description: 'The id for the switch',
    },
    size: {
      control: 'select',
      options: ['small', 'medium'],
      description: 'The size of the switch',
    },
  },
}

export default meta

type Story = StoryObj<typeof PSwitch>

const defaultExportableCode = `<PSwitch
  id="notifications"
  label="Enable notifications"
/>`

export const Default: Story = {
  args: {
    label: 'Switch label',
    id: 'switch',
  },
  parameters: {
    exportableCode: defaultExportableCode,
  },
  render: (args) => ({
    components: { PSwitch },
    setup() {
      const onUpdateModelValue = action('update:modelValue')
      return { args, onUpdateModelValue }
    },
    template: `<PSwitch v-bind="args" @update:modelValue="onUpdateModelValue" />`,
  }),
}
