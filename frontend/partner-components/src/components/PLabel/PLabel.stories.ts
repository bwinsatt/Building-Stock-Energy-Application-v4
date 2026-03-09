import type { Meta, StoryObj } from '@storybook/vue3-vite'
import PLabel from './PLabel.vue'
import { typographyVariants } from '../PTypography/types'

const meta: Meta<typeof PLabel> = {
  component: PLabel,
  title: 'Components/PLabel',
  args: {
    for: 'label',
    class: '',
    variant: 'inputLabel',
  },
  argTypes: {
    for: {
      control: 'text',
      description: 'The for attribute for the label',
    },
    class: {
      control: 'text',
      description: 'The class attribute for the label',
    },
    variant: {
      control: 'select',
      options: typographyVariants,
    },
    disabled: {
      control: 'boolean',
      description: 'Whether the label is disabled',
    },
    required: {
      control: 'boolean',
      description: 'Whether the label is required',
    },
    error: {
      control: 'boolean',
      description: 'Whether the label has an error',
    },
  },
}

export default meta

export const Default: StoryObj<typeof PLabel> = {
  render: (args) => ({
    components: { PLabel },
    setup: () => ({ args }),
    template: `<PLabel v-bind="args">Label</PLabel>`,
  }),
}