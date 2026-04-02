import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { action } from 'storybook/actions'
import { PAlert, alertVariantOptions, alertAppearanceOptions, alertAlignOptions, type PAlertProps } from './index'
import { sizeOptions } from '@/types/size'
import { iconOptions } from '@/components/PIcon/iconNames'

const meta: Meta<typeof PAlert> = {
  component: PAlert,
  subcomponents: {
    PAlert,
  },
  title: 'Components/PAlert',
  argTypes: {
    variant: {
      control: 'select',
      options: alertVariantOptions,
      description: 'Alert variant',
    },
    appearance: {
      control: 'select',
      options: alertAppearanceOptions,
      description: 'Alert appearance',
    },
    size: {
      control: 'select',
      options: sizeOptions,
      description: 'Alert size',
    },
    icon: {
      control: 'select',
      options: iconOptions,
      description: 'Alert icon',
    },
    hideIcon: {
      control: 'boolean',
      description: 'Whether the icon is hidden',
    },
    title: {
      control: 'text',
      description: 'Alert title',
    },
    description: {
      control: 'text',
      description: 'Alert description',
    },
    align: {
      control: 'select',
      options: alertAlignOptions,
      description: 'Alert alignment',
    },
    hideCloseButton: {
      control: 'boolean',
      description: 'Whether the close button is hidden',
    },
    actionButtonProps: {
      control: 'object',
      description: 'Action button props',
    },
    actionButtonText: {
      control: 'text',
      description: 'Action button text',
    },
    closeButtonProps: {
      control: 'object',
      description: 'Close button props',
    },
  },
}

export default meta
type Story = StoryObj<typeof meta>

const defaultExportableCode = `<PAlert
  variant="default"
  appearance="contained"
  size="medium"
  title="Alert title"
  description="Alert description"
/>`

export const Default: Story = {
  args: {
    variant: 'default',
    appearance: 'contained',
    size: 'medium',
    title: 'Alert Title',
    description: 'Alert Description',
  },
  parameters: {
    exportableCode: defaultExportableCode,
  },
  render: (args: PAlertProps) => ({
    components: { PAlert, ...meta.subcomponents },
    setup() {
      return { args, close: action('close'), action: action('action') }
    },
    template: `
      <PAlert v-bind="args" @close="close" @action="action" />
    `,
  }),
}
