import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { action } from 'storybook/actions'
import { PMenu, PMenuItem } from './index'
import { PButton } from '@/components/PButton'
import { ref } from 'vue'
import { sizeOptions } from '@/types/size'

const meta: Meta<typeof PMenu> = {
  component: PMenu,
  title: 'Components/PMenu',
  subcomponents: { PButton, PMenuItem },
  argTypes: {
    size: {
      control: 'select',
      options: sizeOptions,
      description: 'The size of the menu',
    },
    class: {
      control: 'text',
      description: 'The class for the menu',
    },
    label: {
      control: 'text',
      description: 'The label for the menu',
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
    disabled: {
      control: 'boolean',
      description: 'Whether the menu is disabled',
    },
    searchable: {
      control: 'boolean',
      description: 'Whether the menu has a search bar and search functionality',
    },
    disableSearchFilter: {
      control: 'boolean',
      description: 'Whether the menu disables search filtering',
    },
    searchDebounce: {
      control: 'number',
      description: 'The delay for debouncing the search bar input value',
    },
  },
}

export default meta

type Story = StoryObj<typeof PMenu>

const defaultSetup = () => {
  const toggleState = ref(false)
  const checkboxOneState = ref(true)
  const checkboxTwoState = ref('indeterminate')
  const buttonClick = action('buttonClick')
  const updateOpen = action('update:open')
  const onSelect = action('select')
  const onValueChange = action('update:modelValue')
  const updateDebouncedSearch = action('update:debouncedSearch')
  const search = action('search')
  return { toggleState, checkboxOneState, checkboxTwoState, buttonClick, updateOpen, onSelect, onValueChange, updateDebouncedSearch, search }
}
const defaultCode = `
    <PMenu v-bind="args" v-model:open="toggleState" @update:open="updateOpen" @update:debouncedSearch="updateDebouncedSearch" @search="search" class="h-60">
      <template #trigger>
        <PButton variant="primary" appearance="contained">Open menu</PButton>
      </template>
      <template #content>
        <PMenuItem type="item" label="Item 1" icon="badge" @select="onSelect" />
        <PMenuItem type="separator" />
        <PMenuItem type="item" label="Item 2" icon="car" @select="onSelect" />
        <PMenuItem type="item" label="Item 3" @select="onSelect" />
        <PMenuItem type="group" label="Group 1">
          <PMenuItem type="item" label="Prevent Close (Event) Item 1" icon="bat" @select.prevent="onSelect" />
          <PMenuItem type="item" label="Prevent Close (Prop) Item 2" @select="onSelect" preventClose />
          <PMenuItem type="item" label="Prevent Close (Prop) Item 3" @select="onSelect" preventClose />
        </PMenuItem>
        <PMenuItem type="sub" label="Submenu 1">
          <PMenuItem type="item" label="Item 1" @select="onSelect" />
          <PMenuItem type="item" label="Item 2" @select="onSelect" />
          <PMenuItem type="item" label="Item 3" @select="onSelect" />
          <PMenuItem type="sub" label="Submenu 1">
            <PMenuItem type="item" label="Submenu 1 label">
              <PButton variant="primary" appearance="contained" icon="face-cool" iconPosition="left" class="w-full" @click="buttonClick">A button?!</PButton>
            </PMenuItem>
          </PMenuItem>
        </PMenuItem>
        <PMenuItem type="checkbox" label="Checkbox 1" v-model="checkboxOneState" @update:modelValue="onValueChange" />
        <PMenuItem type="checkbox" label="Checkbox 2" v-model="checkboxTwoState" @update:modelValue="onValueChange" />
      </template>
      <template #footer>
      <PButton variant="primary" appearance="text">Footer</PButton>
      </template>
    </PMenu>`

const defaultExportableCode = `<PMenu searchable>
  <template #trigger>
    <PButton variant="primary" appearance="contained">
      Open menu
    </PButton>
  </template>

  <template #content>
    <PMenuItem type="item" label="Edit profile" />
    <PMenuItem type="item" label="Account settings" />
    <PMenuItem type="separator" />
    <PMenuItem type="item" label="Sign out" />
  </template>

  <template #footer>
    <PButton variant="primary" appearance="text">
      Manage account
    </PButton>
  </template>
</PMenu>`
export const Default: Story = {
  parameters: {
    exportableCode: defaultExportableCode,
    docs: {
      source: {
        code: `setup${defaultSetup.toString()}\n\n<template>${defaultCode}\n</template>`,
      },
    },
  },
  args: {
    // label: 'Menu label',
    searchable: true,
    defaultOpen: true,
  },
  render: (args) => ({
    components: { PMenu, ...meta.subcomponents },
    setup() {
      return { args, ...defaultSetup() }
    },
    template: defaultCode,
  }),
}
