import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { action } from 'storybook/actions'
import { PDialog, PDialogClose } from './index'
import { PButton, PTypography, PTextInput } from '@/index'

const meta: Meta<typeof PDialog> = {
  component: PDialog,
  title: 'Components/PDialog',
  subcomponents: {
    PDialog,
    PDialogClose,
    PButton,
    PTypography,
    PTextInput,
  },
  argTypes: {
    defaultOpen: {
      control: 'boolean',
      description: 'Whether the dialog is open by default',
    },
    open: {
      control: 'boolean',
      description: 'Whether the dialog is open',
    },
    title: {
      control: 'text',
      description: 'The title of the dialog',
    },
    description: {
      control: 'text',
      description: 'The description of the dialog',
    },
    modal: {
      control: 'boolean',
      description: 'Whether the dialog is modal',
    },
    hideCloseButton: {
      control: 'boolean',
      description: 'Whether the close button is hidden',
    },
    disableCloseOnEscape: {
      control: 'boolean',
      description: 'Whether the close on escape is disabled',
    },
    disableCloseOnInteractOutside: {
      control: 'boolean',
      description: 'Whether the close on interact outside is disabled',
    },
  },
}

export default meta

type Story = StoryObj<typeof PDialog>

const defaultCode = `<PDialog v-bind="args" @update:open="updateOpen">
  <template #trigger>
    <PButton name="open" variant="primary" appearance="contained">Open Dialog</PButton>
  </template>
  <template #content>
    <PTypography variant="body1">Dialog Content</PTypography>
    <br />
    <PTextInput label="Name" placeholder="Enter your name" id="name" required />
  </template>
  <template #footer>
    <div class="flex gap-2 justify-end">
      <PDialogClose>
        <!-- This wrapper allows the button to close the dialog -->
        <PButton variant="primary" appearance="outlined">Cancel</PButton>
      </PDialogClose>
      <PButton variant="primary" appearance="contained">Submit</PButton>
    </div>
  </template>
</PDialog>`

const defaultExportableCode = `<PDialog title="Dialog title" description="Dialog description">
  <template #trigger>
    <PButton variant="primary" appearance="contained">
      Open dialog
    </PButton>
  </template>

  <template #content>
    <p>Dialog content goes here.</p>
  </template>

  <template #footer>
    <PButton variant="primary" appearance="contained">
      Save
    </PButton>
  </template>
</PDialog>`

export const Default: Story = {
  parameters: {
    exportableCode: defaultExportableCode,
    docs: {
      source: {
        code: defaultCode,
      },
    },
  },
  args: {
    defaultOpen: true,
    title: 'Dialog Title',
    description: 'Dialog Description',
  },
  render: (args) => ({
    components: { PDialog, ...meta.subcomponents },
    setup() {
      return { args, updateOpen: action('update:open') }
    },
    template: defaultCode,
  }),
}

const noTriggerCode =  `<PDialog v-bind="args" @update:open="updateOpen">
  <template #content>
    This dialog has no trigger, is open by default, is not modal, and without title, footer, or description.
  </template>
</PDialog>`

export const NoTrigger: Story = {
  parameters: {
    docs: {
      source: {
        code: noTriggerCode,
      },
    },
  },
  args: {
    defaultOpen: true,
    modal: false,
  },
  render: (args) => ({
    components: { PDialog, ...meta.subcomponents },
    setup() {
      return { args, updateOpen: action('update:open') }
    },
    template: noTriggerCode,
  }),
}
