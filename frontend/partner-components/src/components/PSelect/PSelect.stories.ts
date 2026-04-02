import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { action } from 'storybook/actions'
import { PSelect } from './index'
import { sizeOptions } from '@/types/size'
import { PTypography } from '@/components/PTypography'
import { chipVariants, chipAppearances } from '@/components/PChip/storyCommon'

const meta: Meta<typeof PSelect> = {
  component: PSelect,
  title: 'Components/PSelect',
  subcomponents: { PTypography },
  argTypes: {
    items: {
      control: 'object',
      description: 'The items to display in the Select',
    },
    id: {
      control: 'text',
      description: 'The id for the Select',
    },
    type: {
      control: 'select',
      options: ['single', 'multi'],
      description: 'The type of the Select',
    },
    variant: {
      control: 'select',
      options: ['text', 'chip'],
      description: 'The variant of the Select',
    },
    chipVariant: {
      control: 'select',
      options: chipVariants,
      description: 'The variant of the Chip',
    },
    chipAppearance: {
      control: 'select',
      options: chipAppearances,
      description: 'The appearance of the Chip',
    },
    modelValue: {
      control: 'object',
      description: 'The model value for the Select',
    },
    placeholder: {
      control: 'text',
      description: 'The placeholder for the Select',
    },
    disabled: {
      control: 'boolean',
      description: 'Whether the Select is disabled',
    },
    required: {
      control: 'boolean',
      description: 'Whether the Select is required',
    },
    size: {
      control: 'select',
      options: sizeOptions,
      description: 'The size of the Select',
    },
    searchable: {
      control: 'boolean',
      description: 'Whether the Select is searchable',
    },
    clearable: {
      control: 'boolean',
      description: 'Whether the Select is clearable',
    },
    clearableMenu: {
      control: 'boolean',
      description: 'Whether the Select menu is clearable',
    },
    label: {
      control: 'text',
      description: 'The label for the Select',
    },
    menuLabel: {
      control: 'text',
      description: 'The label for the Select menu',
    },
    helperText: {
      control: 'text',
      description: 'The helper text for the Select',
    },
    errorText: {
      control: 'text',
      description: 'The error text for the Select',
    },
    error: {
      control: 'boolean',
      description: 'Whether the Select is in an error state',
    },
  },
}

export default meta

type Story = StoryObj<typeof meta>

const items = [
  { id: '1', label: 'Item 1' },
  { id: '2', label: 'Item 2' },
  { id: '3', label: 'Item 3' },
  { id: '4', label: 'Item 4' },
  { id: '5', label: 'Item 5' },
  { id: '6', label: 'Item 6' },
  { id: '7', label: 'Item 7' },
  { id: '8', label: 'Item 8' },
  { id: '9', label: 'Item 9' },
  { id: '10', label: 'Item 10' },
]

function defaultSetup(args: typeof Default.args) {
  const apply = action('apply')
  const clear = action('clear')
  const updateOpen = action('update:open')
  const updateModelValue = action('update:modelValue')
  return { args, apply, clear, updateOpen, updateModelValue }
}

const defaultTemplate = `
  <PSelect v-bind="args" @apply="apply" @clear="clear" @update:open="updateOpen" @update:modelValue="updateModelValue" />
`

const defaultExportableCode = `<script setup lang="ts">
const items = [
  { id: '1', label: 'Item 1' },
  { id: '2', label: 'Item 2' },
  { id: '3', label: 'Item 3' },
]
</script>

<template>
  <PSelect
    id="status"
    label="Status"
    placeholder="Select a status"
    helperText="Choose one option"
    :items="items"
    type="single"
    variant="text"
    size="medium"
  />
</template>`

export const Default: Story = {
  args: {
    items,
    placeholder: 'Select an item',
    label: 'Select label',
    id: 'select',
    type: 'single',
    variant: 'text',
    chipVariant: 'neutral',
    chipAppearance: 'contained',
    helperText: 'Helper text',
    errorText: 'Error text',
    error: false,
    disabled: false,
    required: false,
    size: 'medium',
    searchable: false,
    clearable: false,
    clearableMenu: false,
  },
  parameters: {
    exportableCode: defaultExportableCode,
  },
  render: (args) => ({
    components: { PSelect, ...meta.subcomponents },
    setup() {
      return defaultSetup(args)
    },
    template: defaultTemplate,
  }),
}

export const Multi: Story = {
  args: {
    ...Default.args,
    type: 'multi',
  },
}

export const MultiWithOverflow: Story = {
  args: {
    ...Default.args,
    type: 'multi',
    items: items.map(item => ({
      ...item,
      modelValue: item.label,
    })),
  },
  render: (args) => ({
    components: { PSelect },
    setup() {
      return defaultSetup(args)
    },
    template: `
      <div class="resize-x overflow-auto border border-dashed border-gray-300 p-2 w-72">
        ${defaultTemplate}
      </div>
    `,
  }),
}
