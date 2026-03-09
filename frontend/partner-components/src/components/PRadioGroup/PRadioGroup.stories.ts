import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { action } from 'storybook/actions'
import PRadioGroup from './PRadioGroup.vue'
import PRadioGroupItem from './PRadioGroupItem.vue'
import { sizeOptions } from '@/types/size'

const meta: Meta<typeof PRadioGroup> = {
  component: PRadioGroup,
  title: 'Components/PRadioGroup',
  args: {
    options: [
      { id: 'default', value: 'default', label: 'Default' },
      { id: 'comfortable', value: 'comfortable', label: 'Comfortable', orientation: 'vertical' },
      { id: 'compact', value: 'compact', label: 'Compact' },
    ],
    selected: 'comfortable',
    size: 'medium',
    label: 'Radio group label',
    helperText: 'Helper text',
    errorText: 'Error text',
    error: false,
    required: false,
    disabled: false,
    orientation: 'horizontal',
    labelOrientation: 'horizontal',
  },
  argTypes: {
    defaultValue: {
      control: 'text',
      description: 'The default value for the radio group',
    },
    modelValue: {
      control: 'text',
      description: 'The model value for the radio group',
    },
    size: {
      control: 'select',
      options: sizeOptions,
    },
    orientation: {
      control: 'select',
      options: ['horizontal', 'vertical'],
    },
    labelOrientation: {
      control: 'select',
      options: ['horizontal', 'vertical'],
    },
    required: {
      control: 'boolean',
      description: 'Whether the radio group is required',
    },
    disabled: {
      control: 'boolean',
      description: 'Whether the radio group is disabled',
    },
    error: {
      control: 'boolean',
      description: 'Whether the radio group is in an error state',
    },
    helperText: {
      control: 'text',
      description: 'The helper text for the radio group',
    },
    errorText: {
      control: 'text',
      description: 'The error text for the radio group',
    },
    label: {
      control: 'text',
      description: 'The label for the radio group',
    },
  },
}

export default meta

export const Default: StoryObj<typeof PRadioGroup> = {
  render: (args) => ({
    components: { PRadioGroup, PRadioGroupItem },
    setup() {
      const updateModelValue = action('update:modelValue')
      return { args, updateModelValue }
    },
    template: `
      <PRadioGroup v-bind="args" @update:modelValue="updateModelValue">
    `,
  }),
}