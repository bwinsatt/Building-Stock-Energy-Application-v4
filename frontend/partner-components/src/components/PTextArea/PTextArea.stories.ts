import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { PTextArea } from './index'
import { sizeOptions } from '@/types/size'

const meta: Meta<typeof PTextArea> = {
  component: PTextArea,
  title: 'Components/PTextArea',
  argTypes: {
    defaultValue: {
      control: 'text',
      description: 'The default value for the text area',
    },
    modelValue: {
      control: 'text',
      description: 'The model value for the text area',
    },
    maxLength: {
      control: 'number',
      description: 'The maximum length for the text area',
    },
    minLines: {
      control: 'number',
      description: 'The minimum number of visible lines/rows for the text area',
    },
    placeholder: {
      control: 'text',
      description: 'The placeholder for the text area',
    },
    label: {
      control: 'text',
      description: 'The label for the text area',
    },
    id: {
      control: 'text',
      description: 'The id for the text area',
    },
    required: {
      control: 'boolean',
      description: 'Whether the text area is required',
    },
    disabled: {
      control: 'boolean',
      description: 'Whether the text area is disabled',
    },
    error: {
      control: 'boolean',
      description: 'Whether the text area has an error',
    },
    resize: {
      control: 'boolean',
      description: 'Whether the text area is resizable',
    },
    size: {
      control: 'select',
      options: sizeOptions,
      description: 'The size of the text area',
    },
    helperText: {
      control: 'text',
      description: 'The helper text for the text area',
    },
    errorText: {
      control: 'text',
      description: 'The error text for the text area',
    },
    'onUpdate:modelValue': {
      type: 'function',
      args: 'value: string | number',
      description: 'The function to call when the model value is updated',
    },
  },
}

export default meta
type Story = StoryObj<typeof PTextArea>

const defaultExportableCode = `<PTextArea
  id="notes"
  label="Notes"
  placeholder="Add any extra details"
  helperText="You can include up to 100 characters"
  :max-length="100"
/>`

export const Default: Story = {
  args: {
    defaultValue: 'Hello, world!',
    placeholder: 'Enter your name',
    label: 'Text area label',
    id: 'text-area',
    required: false,
    disabled: false,
    error: false,
    size: 'medium',
    maxLength: 100,
    helperText: 'Helper text',
    errorText: 'Error text',
  },
  parameters: {
    exportableCode: defaultExportableCode,
  },
}
