import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { action } from 'storybook/actions'
import { PMenu, PMenuItem, PSelectMenu, type PMenuItemProps } from './index'
import { PButton } from '@/components/PButton'
import { ref } from 'vue'
import { sizeOptions } from '@/types/size'

const meta: Meta<typeof PSelectMenu> = {
  component: PSelectMenu,
  title: 'Components/PSelectMenu',
  subcomponents: { PButton, PMenuItem, PMenu },
  argTypes: {
    items: {
      control: 'object',
      description: 'The items for the multiselect menu',
    },
    searchable: {
      control: 'boolean',
      description: 'Whether the menu is searchable',
    },
    disableSearchFilter: {
      control: 'boolean',
      description: 'Whether the menu disables search filtering',
    },
    searchDebounce: {
      control: 'number',
      description: 'The delay for debouncing the search bar input value',
    },
    selectedCountOverride: {
      control: 'number',
      description: 'Optional number of selected objects to override data',
    },
    type: {
      control: 'select',
      options: ['multi', 'single'],
      description: 'The type of menu',
    },
    hideFooter: {
      control: 'boolean',
      description: 'Whether the menu has a footer',
    },
    hideSelectAll: {
      control: 'boolean',
      description: 'Whether the menu has a select all option',
    },
    size: {
      control: 'select',
      options: sizeOptions,
      description: 'The size of the menu',
    },
    clearable: {
      control: 'boolean',
      description: 'Whether the menu is clearable',
    },
    closeOnApply: {
      control: 'boolean',
      description: 'Whether the menu should close when the apply button is clicked',
    },
    defaultOpen: {
      control: 'boolean',
      description: 'Whether the menu is open by default',
    },
    open: {
      control: 'boolean',
      description: 'Whether the menu is open',
    },
    modal: {
      control: 'boolean',
      description: 'Whether the menu is modal',
    },
    label: {
      control: 'text',
      description: 'The label for the menu',
    },
    disabled: {
      control: 'boolean',
      description: 'Whether the menu is disabled',
    },
    scrollIntoView: {
      control: 'boolean',
      description: 'Whether the menu should scroll into view when an item is selected',
    },
    scrollIntoViewOptions: {
      control: 'object',
      description: 'The options for the scroll into view',
    },
  },
}

export default meta

type Story = StoryObj<typeof PSelectMenu>

const defaultSetup = () => {
  const items = ref<PMenuItemProps[]>([
    { id: 'item-1', label: 'Item 1', modelValue: true, description: 'Item 1 description that is longer than the item label' },
    { id: 'item-2', label: 'Item 2' },
    { id: 'item-3', label: 'Item 3', disabled: true},
    { id: 'item-4', label: 'Item 4', modelValue: true, disabled: true },
    { id: 'item-5', label: 'Item 5' },
    { id: 'item-6', label: 'Item 6' },
    { id: 'item-7', label: 'Item 7' },
    { id: 'item-8', label: 'Item 8' },
    { id: 'item-9', label: 'Item 9' },
    { id: 'item-10', label: 'Item 10' },
  ])
  const apply = action('apply')
  const clear = action('clear')
  const select = action('select')
  const updateDebouncedSearch = action('update:debouncedSearch')
  const search = action('search')
  return { items, apply, clear, select, updateDebouncedSearch, search }
}

const defaultCode = `
  <PSelectMenu v-bind="args" default-open :items="items" @apply="apply" @clear="clear" @select="select" @update:debouncedSearch="updateDebouncedSearch" @search="search" :class="args.class">
    <template #trigger>
      <PButton variant="primary" appearance="contained">Open {{args.type}}-select menu</PButton>
    </template>
  </PSelectMenu>
`

export const MultiSelect: Story = {
  parameters: {
    docs: {
      source: {
        code: `setup${defaultSetup.toString()}\n\n<template>${defaultCode}\n</template>`,
      },
    },
  },
  args: {
    type: 'multi',
    class: 'w-60',
  },
  render: (args) => ({
    components: { PSelectMenu, ...meta.subcomponents },
    setup() {
      return { args, ...defaultSetup() }
    },
    template: defaultCode,
  }),
}

export const SingleSelect: Story = {
  parameters: {
    docs: {
      source: {
        code: `setup${defaultSetup.toString()}\n\n<template>${defaultCode}\n</template>`,
      },
    },
  },
  args: {
    type: 'single',
    class: 'w-60',
  },
  render: (args) => ({
    components: { PSelectMenu, ...meta.subcomponents },
    setup() {
      return { args, ...defaultSetup() }
    },
    template: defaultCode,
  }),
}

export const SingleSelectNoFooter: Story = {
  args: {
    type: 'single',
    hideFooter: true,
    class: 'w-60',
  },
  render: (args) => ({
    components: { PSelectMenu, ...meta.subcomponents },
    setup() {
      return { args, ...defaultSetup() }
    },
    template: defaultCode,
  }),
}

export const DynamicItems: Story = {
  args: {
    type: 'multi',
    class: 'w-60',
  },
  render: (args) => ({
    components: { PSelectMenu, ...meta.subcomponents },
    setup() {
      const { items, ...rest } = defaultSetup()
      const open = ref(true)
      const altItems: PMenuItemProps[] = [
        { id: 'alt-1', label: 'Alpha' },
        { id: 'alt-2', label: 'Beta' },
        { id: 'alt-3', label: 'Gamma' },
      ]
      const swapItems = () => {
        items.value = items.value[0]?.id === 'item-1' ? altItems : defaultSetup().items.value
      }
      return { args, items, open, ...rest, swapItems }
    },
    template: `
      <div class="flex gap-2">
        <PSelectMenu v-bind="args" :open="open" @update:open="open = $event" :items="items" @apply="apply" @clear="clear" @select="select">
          <template #trigger>
            <PButton variant="primary" appearance="contained">Open menu</PButton>
          </template>
          <template #content-prepend>
            <PButton variant="primary" appearance="outlined" @click="swapItems">Swap Items</PButton>
          </template>
        </PSelectMenu>
      </div>
    `,
  }),
}

export const SelectedCountOverride: Story = {
  args: {
    type: 'multi',
    selectedCountOverride: 7,
    class: 'w-60',
  },
  render: (args) => ({
    components: { PSelectMenu, ...meta.subcomponents },
    setup() {
      return { args, ...defaultSetup() }
    },
    template: defaultCode,
  }),
}