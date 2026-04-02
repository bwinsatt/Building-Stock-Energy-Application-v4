import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { action } from 'storybook/actions'
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
    maxLength: {
      control: 'number',
      description: 'The maximum length for the search bar input',
    },
    debounce: {
      control: 'number',
      description: 'The delay for debouncing the search bar input value',
    },
  },
}

export default meta

type Story = StoryObj<typeof PSearchBar>

const defaultExportableCode = `<script setup lang="ts">
import { ref } from 'vue'

const query = ref('')
</script>

<template>
  <PSearchBar
    v-model="query"
    placeholder="Search users"
    size="medium"
  />
</template>`

export const Default: Story = {
  args: {
    defaultValue: '',
    placeholder: 'Search...',
    disabled: false,
    size: 'medium',
  },
  parameters: {
    exportableCode: defaultExportableCode,
  },
  render: (args) => ({
    components: { PSearchBar },
    setup() {
      const onClear = action('clear')
      const onUpdateModelValue = action('update:modelValue')
      const onUpdateDebouncedValue = action('update:debouncedValue')
      const onSearch = action('search')
      return { args, onClear, onUpdateModelValue, onUpdateDebouncedValue, onSearch }
    },
    template: `<PSearchBar v-bind="args" @clear="onClear" @update:modelValue="onUpdateModelValue" @update:debouncedValue="onUpdateDebouncedValue" @search="onSearch" />`,
  }),
}
