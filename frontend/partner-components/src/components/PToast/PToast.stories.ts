// PToast.stories.ts
import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { computed } from 'vue'
import { action } from 'storybook/actions'
import { PToast, toastPositions, type PToastProps } from './index'
import { showToast, type ShowToastOptions } from './index'
import { PButton } from '@/components/PButton'
import { alertVariantOptions, alertAppearanceOptions, type PAlertProps } from '@/components/PAlert'

type StoryArgs = PToastProps & ShowToastOptions

const meta: Meta<StoryArgs> = {
  component: PToast,
  title: 'Components/PToast',
  args: {
    position: 'bottom-center',
    expand: false,
    visibleToasts: 3,
    dismissible: false,
  },
  argTypes: {
    position: {
      control: 'select',
      options: toastPositions,
      description: 'The position of the toast',
      table: {
        category: 'PToastProps',
      }
    },
    expand: {
      control: 'boolean',
      description: 'Whether the toast should expand to fill the container',
      table: {
        category: 'PToastProps',
      }
    },
    visibleToasts: {
      control: 'number',
      description: 'The number of toasts to display',
      table: {
        category: 'PToastProps',
      }
    },
    title: {
      control: 'text',
      description: 'The title of the toast',
      table: {
        category: 'ShowToastOptions',
      }
    },
    description: {
      control: 'text',
      description: 'The description of the toast',
      table: {
        category: 'ShowToastOptions',
      }
    },
    variant: {
      control: 'select',
      options: alertVariantOptions,
      description: 'The variant of the toast',
      table: {
        category: 'ShowToastOptions',
      }
    },
    appearance: {
      control: 'select',
      options: alertAppearanceOptions,
      description: 'The appearance of the toast',
      table: {
        category: 'ShowToastOptions',
      }
    },
    dismissible: {
      control: 'boolean',
      description: 'Whether the toast should be dismissible',
      table: {
        category: 'ShowToastOptions',
      }
    },
    hideIcon: {
      control: 'boolean',
      description: 'Whether the icon should be hidden',
      table: {
        category: 'ShowToastOptions',
      }
    },
  },
}

export default meta
type Story = StoryObj<StoryArgs>

const defaultExportableCode = `<script setup lang="ts">
function triggerToast() {
  showToast({
    title: 'Toast title',
    description: 'Toast description',
    variant: 'info',
    appearance: 'contained',
    hideIcon: false,
    dismissible: false,
  })
}
</script>

<template>
  <PButton @click="triggerToast">Show toast</PButton>
  <PToast position="bottom-center" :expand="false" :visible-toasts="3" />
</template>`

export const Default: Story = {
  parameters: {
    exportableCode: defaultExportableCode,
    docs: {
      source: {
        code: `const triggerToast = () => showToast(
          { 
            title="Toast Title", 
            description="Toast Description", 
            variant="info", 
            appearance="contained", 
            hideIcon="false", 
            dismissible="false" 
          } 
        )
        <template>
          <PButton @click="triggerToast">Show Toast</PButton>
          <PToast position="bottom-center" expand="false" visibleToasts="3"/>
        </template>`,
      },
    },
  },
  args: {
    title: 'Toast Title',
    description: 'Toast Description',
    variant: 'info',
    appearance: 'contained',
    hideIcon: false,
  },
  render: (args) => ({
    components: { PToast, PButton },
    setup() {
      return { args }
    },
    methods: {
      triggerToast() {
        showToast({ ...args })
      },
    },
    template: `
      <div class="flex h-[calc(100vh-2rem)] items-center justify-center">
        <PButton @click="triggerToast">Show Toast</PButton>
      </div>
      <PToast v-bind="args" />
    `,
  }),
}

const getPositionClass = (position: string) => {
  const vertical = position.startsWith('bottom') ? 'items-start' : 'items-end'
  const horizontal = position.endsWith('left') ? 'justify-end'
                   : position.endsWith('right') ? 'justify-start'
                   : 'justify-center'
  return `${vertical} ${horizontal}`
}

const allVariantsSetup = (args: StoryArgs, alertProps?: PAlertProps) => {
  const onClose = action('close')
  const onAction = action('action')
  const positionClass = computed(() => getPositionClass(args.position ?? 'top-center'))
  const dismissible = computed(() => args.dismissible ?? false)
  const triggerSuccess = () => showToast({ ...alertProps, title: 'Saved', description: 'Changes saved successfully', variant: 'success', onClose, onAction, dismissible: dismissible.value })
  const triggerError = () => showToast({ ...alertProps, title: 'Error', description: 'Something went wrong', variant: 'error', onClose, onAction, dismissible: dismissible.value })
  const triggerInfo = () => showToast({ ...alertProps, title: 'Info', description: 'New update available', variant: 'info', onClose, onAction, dismissible: dismissible.value })
  const triggerWarning = () => showToast({ ...alertProps, title: 'Warning', description: 'This is a warning', variant: 'warning', onClose, onAction, dismissible: dismissible.value })
  const triggerNeutral = () => showToast({ ...alertProps, title: 'Neutral', description: 'This is a neutral toast', variant: 'neutral', onClose, onAction, dismissible: dismissible.value })
  return { args, positionClass, triggerSuccess, triggerError, triggerInfo, triggerWarning, triggerNeutral}
}

const allVariantsTemplate = `
  <div class="flex h-[calc(100vh-2rem)]" :class="positionClass">
    <div class="flex gap-2">
      <PButton @click="triggerSuccess" variant="success">Success Toast</PButton>
      <PButton @click="triggerError" variant="error">Error Toast</PButton>
      <PButton @click="triggerInfo" variant="primary">Info Toast</PButton>
      <PButton @click="triggerWarning" variant="warning">Warning Toast</PButton>
      <PButton @click="triggerNeutral" variant="neutral">Neutral Toast</PButton>
    </div>
  </div>
  <PToast v-bind="args" />
`

const allVariantsCode = (alertProps?: PAlertProps) => {
  return `<script lang="ts" setup>${alertProps ? `\nconst alertProps = ${JSON.stringify(alertProps)}` : ''}\n${allVariantsSetup.toString()}\n</script>\n\n<template>${allVariantsTemplate}\n</template>`
}


export const AllVariants: Story = {
  parameters: {
    docs: {
      source: {
        code: allVariantsCode(),
      },
    },
  },
  render: (args) => ({
    components: { PToast, PButton },
    setup() {
      return {...allVariantsSetup(args)}
    },
    template: allVariantsTemplate,
  }),
}

const withActionButton_alertProps = { actionButtonText: 'Undo' }

export const WithActionButton: Story = {
  parameters: {
    docs: {
      source: {
        code: allVariantsCode(withActionButton_alertProps),
      },
    },
  },
  render: (args) => ({
    components: { PToast, PButton },
    setup() {
      return {...allVariantsSetup(args, withActionButton_alertProps)}
    },
    template: allVariantsTemplate,
  }),
}
