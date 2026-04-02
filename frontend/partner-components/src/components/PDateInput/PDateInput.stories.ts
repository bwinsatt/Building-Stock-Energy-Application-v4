import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { action } from 'storybook/actions'
import { PDateInput, type PDateInputProps } from './index'
import { sizeOptions } from '@/types/size'
import { DateTime } from 'luxon'

const meta: Meta<typeof PDateInput> = {
  component: PDateInput,
  title: 'Components/PDateInput',
  argTypes: {
    modelValue: {
      control: false,
      description: 'Luxon `DateTime` — the selected date',
    },
    defaultValue: {
      control: false,
      description: 'Luxon `DateTime` — the default date',
    },
    label: {
      control: 'text',
      description: 'The label for the date input',
    },
    disabled: {
      control: 'boolean',
      description: 'Whether the date input is disabled',
    },
    required: {
      control: 'boolean',
      description: 'Whether the date input is required',
    },
    size: {
      control: 'select',
      options: sizeOptions,
      description: 'The size of the date input',
    },
    helperText: {
      control: 'text',
      description: 'The helper text for the date input',
    },
    errorText: {
      control: 'text',
      description: 'The error text for the date input',
    },
    error: {
      control: 'boolean',
      description: 'Whether the date input has an error',
    },
    locale: {
      control: 'select',
      options: ['en-US', 'en-GB', 'ja-JP', 'de-DE', 'es-ES', 'it-IT', 'ko-KR', 'zh-CN', 'zh-TW'],
      description: 'The locale for the date input',
    },
    calendarProps: {
      control: 'object',
      description: 'The props for the calendar',
    },
  },
}

export default meta

type Story = StoryObj<typeof PDateInput>

const defaultSetup = (args: PDateInputProps) => {
  const updateModelValue = action('update:modelValue')
  return {
    args,
    updateModelValue,
  }
}
const defaultTemplate = `
  <p class="mb-2">Dates use <a href="https://moment.github.io/luxon/" target="_blank">Luxon DateTime</a></p>
  <PDateInput v-bind="args" @update:modelValue="updateModelValue" />
`

const defaultExportableCode = `<script setup lang="ts">
import { DateTime } from 'luxon'
</script>

<template>
  <PDateInput
    id="due-date"
    label="Due date"
    helperText="Select a target completion date"
    locale="en-US"
    :calendar-props="{
      monthFormat: 'short',
      yearRange: 3,
      unavailableDates: [DateTime.now().minus({ days: 1 })],
    }"
  />
</template>`

export const Default: Story = {
  args: {
    label: 'Date input label',
    disabled: false,
    required: false,
    size: 'medium',
    helperText: 'Helper text',
    errorText: 'Error text',
    error: false,
    locale: 'en-US',
    calendarProps: {
      monthFormat: 'short',
      yearRange: 3,
      unavailableDates: [DateTime.fromObject({ year: new Date().getFullYear(), month: new Date().getMonth() + 1, day: new Date().getDate() - 1 })],
    },
  },
  parameters: {
    exportableCode: defaultExportableCode,
  },
  render: (args) => {
    return {
      components: { PDateInput },
      setup: () => defaultSetup(args),
      template: defaultTemplate,
    }
  },
}

export const MinValue: Story = {
  args: {
    calendarProps: {
      minValue: DateTime.fromObject({ year: new Date().getFullYear(), month: new Date().getMonth() + 1, day: new Date().getDate() - 1 }),
    },
  },
  render: (args) => {
    return {
      components: { PDateInput },
      setup: () => defaultSetup(args),
      template: `<div class="flex flex-col items-center gap-2">min: ${args.calendarProps?.minValue?.toISO()}<br />${defaultTemplate}</div>`,
    }
  },
}

export const MaxValue: Story = {
  args: {
    calendarProps: {
      maxValue: DateTime.fromObject({ year: new Date().getFullYear(), month: new Date().getMonth() + 1, day: new Date().getDate() + 1 }),
    },
  },
  render: (args) => {
    return {
      components: { PDateInput },
      setup: () => defaultSetup(args),
      template: `<div class="flex flex-col items-center gap-2">max: ${args.calendarProps?.maxValue?.toISO()}<br />${defaultTemplate}</div>`,
    }
  },
}
