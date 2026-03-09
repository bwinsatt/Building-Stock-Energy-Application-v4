import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { PSearchBar } from './index'
import { sizeOptions } from '@/types/size'

const meta: Meta<typeof PSearchBar> = {
  component: PSearchBar,
  title: 'Components/PSearchBar',
  argTypes: {
    modelValue: {
      control: 'text',
      description: 'The model value for the search bar',
    },
    defaultValue: {
      control: 'text',
      description: 'The default value for the search bar',
    },
    placeholder: {
      control: 'text',
      description: 'The placeholder for the search bar',
    },
    disabled: {
      control: 'boolean',
      description: 'Whether the search bar is disabled',
    },
    size: {
      control: 'select',
      options: sizeOptions,
      description: 'The size of the search bar',
    },
    'onSearch': {
      type: 'function',
      args: 'payload: string | number',
      description: 'The function to call when the search is performed',
    },
    'onUpdate:modelValue': {
      type: 'function',
      args: 'payload: string | number',
      description: 'The function to call when the model value is updated',
    },
  },
}

export default meta

type Story = StoryObj<typeof PSearchBar>

export const Default: Story = {
  args: {
    defaultValue: '',
    placeholder: 'Search...',
    disabled: false,
    size: 'medium',
  },
}