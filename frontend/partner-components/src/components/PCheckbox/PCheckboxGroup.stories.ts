import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { sizeOptions } from '@/types/size'
import { PCheckboxGroup } from '.'

const meta: Meta<typeof PCheckboxGroup> = {
  component: PCheckboxGroup,
  title: 'Components/PCheckboxGroup',
}

export default meta

type Story = StoryObj<typeof meta>

const defaultExportableCode = `<PCheckboxGroup
  label="Notification preferences"
  helperText="Choose the updates you want to receive"
  :checkboxes="[
    { label: 'Product updates', checked: true },
    { label: 'Security alerts', checked: true },
    { label: 'Marketing emails', checked: false },
  ]"
/>`

export const Default: Story = {
  args: {
    label: 'Checkbox group label',
    orientation: 'vertical',
    disabled: false,
    required: false,
    size: 'medium',
    helperText: 'Helper text',
    errorText: 'Error text',
    error: false,
    checkboxes: [
      {
        label: 'Checkbox 1',
        checked: false,
      },
      {
        label: 'Checkbox 2',
        checked: true,
      },
      {
        label: 'Checkbox 3',
        checked: true,
      },
    ],
  },
  argTypes: {
    orientation: {
      control: 'select',
      options: ['vertical', 'horizontal'],
    },
    disabled: {
      control: 'boolean',
      description: 'Whether the checkbox group is disabled',
    },
    required: {
      control: 'boolean',
      description: 'Whether the checkbox group is required',
    },
    size: {
      control: 'select',
      options: sizeOptions,
    },
    checkboxes: {
      control: 'object',
      description: 'The checkboxes to display',
      items: {
        type: 'object',
        properties: {
          label: { type: 'string' },
          checked: { type: 'boolean' },
          indeterminate: { type: 'boolean' },
        },
      },
    },
    helperText: {
      control: 'text',
      description: 'The helper text to display',
    },
    error: {
      control: 'boolean',
      description: 'Whether the checkbox group is in an error state',
    },
    onChanged: {
      type: 'function',
      args: 'checkboxes: PCheckboxGroupItemProps[]',
      description: 'The function to call when the checkbox group is changed',
    },
  },
  parameters: {
    exportableCode: defaultExportableCode,
  },
}

export const SingleDisabledCheckbox: Story = {
  args: {
    label: 'Checkbox group label',
    orientation: 'vertical',
    disabled: false,
    required: false,
    size: 'medium',
    helperText: 'Helper text',
    errorText: 'Error text',
    error: false,
    checkboxes: [
      {
        label: 'Checkbox 1',
        checked: false,
        disabled: false,
      },
      {
        label: 'Checkbox 2',
        checked: false,
        disabled: true,
      },
      {
        label: 'Checkbox 3',
        checked: false,
        disabled: false,
      },
    ],
  },
  render: (args) => ({
    components: { PCheckboxGroup },
    setup() {
      return { args }
    },
    template: `
      <PCheckboxGroup v-bind="args" />
    `,
  }),
}
