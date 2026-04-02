import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { PTextInput, textInputTypeOptions } from './index'
import { sizeOptions } from '@/types/size'

const meta: Meta<typeof PTextInput> = {
  component: PTextInput,
  title: 'Components/PTextInput',
  argTypes: {
    defaultValue: {
      control: 'text',
      description: 'The default value for the input',
    },
    modelValue: {
      control: 'text',
      description: 'The model value for the input',
    },
    class: {
      control: 'text',
      description: 'The class for the input',
    },
    placeholder: {
      control: 'text',
      description: 'The placeholder text for the input',
    },
    label: {
      control: 'text',
      description: 'The label for the input',
    },
    id: {
      control: 'text',
      description: 'The id for the input',
    },
    required: {
      control: 'boolean',
      description: 'Whether the input is required',
    },
    disabled: {
      control: 'boolean',
      description: 'Whether the input is disabled',
    },
    error: {
      control: 'boolean',
      description: 'Whether the input has an error',
    },
    size: {
      control: 'select',
      options: sizeOptions,
      description: 'The size of the input',
    },
    type: {
      control: 'select',
      options: textInputTypeOptions,
      description: 'The type of the input',
    },
    helperText: {
      control: 'text',
      description: 'The helper text for the input',
    },
    errorText: {
      control: 'text',
      description: 'The error text for the input',
    },
    iconLeft: {
      control: 'object',
      description: 'The icon for the left of the input',
    },
    iconRight: {
      control: 'object',
      description: 'The icon for the right of the input',
    },
    clearable: {
      control: 'boolean',
      description: 'Whether the input is clearable',
    },
    'onUpdate:modelValue': {
      type: 'function',
      args: 'value: string | number',
      description: 'The function to call when the model value is updated',
    },
  },
}

export default meta
type Story = StoryObj<typeof PTextInput>

const defaultExportableCode = `<PTextInput
  id="name"
  label="Full name"
  placeholder="Enter your name"
  helperText="Use your legal name"
/>`

export const Default: Story = {
  args: {
    defaultValue: 'Hello, world!',
    placeholder: 'Enter your name',
    label: 'Input label',
    id: 'input',
    required: false,
    disabled: false,
    error: false,
    size: 'medium',
    helperText: 'Helper text',
    errorText: 'Error text',
  },
  parameters: {
    exportableCode: defaultExportableCode,
  },
}

export const WithIconLeft: Story = {
  args: {
    ...Default.args,
    iconLeft: { name: 'star-filled' },
  },
}

export const WithIconRight: Story = {
  args: {
    ...Default.args,
    iconRight: { name: 'star-filled' },
  },
}
