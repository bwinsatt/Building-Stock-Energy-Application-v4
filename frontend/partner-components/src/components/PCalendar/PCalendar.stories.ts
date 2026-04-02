import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { action } from 'storybook/actions'
import { PCalendar } from './index'
import { DateTime } from 'luxon'

const meta: Meta<typeof PCalendar> = {
  component: PCalendar,
  title: 'Components/PCalendar',
  argTypes: {
    modelValue: {
      control: false,
      description: 'Luxon `DateTime` — the selected date',
    },
    defaultValue: {
      control: false,
      description: 'Luxon `DateTime` — the default date',
    },
    monthFormat: {
      control: 'select',
      options: ['numeric', '2-digit', 'short', 'long'],
      description: 'The format of the month',
    },
    yearRange: {
      control: 'number',
      description: 'The range of years to display in the calendar',
    },
    years: {
      control: 'object',
      description: 'The years to display in the calendar',
    },
    minValue: {
      control: false,
      description: 'The minimum date to display in the calendar (Luxon `DateTime`)',
    },
    maxValue: {
      control: false,
      description: 'The maximum date to display in the calendar (Luxon `DateTime`)',
    },
    clearable: {
      control: 'boolean',
      description: 'Whether the calendar is clearable',
    },
    unavailableDates: {
      control: 'object',
      description: 'The dates to mark as unavailable in the calendar (Luxon `DateTime`)',
    },
    isDateUnavailable: {
      control: false,
      description: 'A function that returns true if a date is unavailable (Luxon `DateTime`)',
    },
    disabled: {
      control: 'boolean',
      description: 'Whether the calendar is disabled',
    },
    locale: {
      control: 'select',
      options: ['en-US', 'en-GB', 'ja-JP', 'de-DE', 'es-ES', 'it-IT', 'ko-KR', 'zh-CN', 'zh-TW'],
      description: 'The locale for the calendar',
    },
  },
}

export default meta

type Story = StoryObj<typeof PCalendar>

const today = new Date()

const defaultSetup = (args: typeof Default.args) => {
  // const date = DateTime.now().plus({ days: 7 })
  const date = DateTime.now()
  const isDateUnavailable = (date: DateTime) => date.month === today.getMonth() + 1 && date.day >= 1 && date.day <= today.getDate() - 3
  const unavailableDates = [DateTime.now().minus({ days: 1 })]
  const updateModelValue = action('update:modelValue')
  const updateMonth = action('update:month')
  const updateYear = action('update:year')
  return { args, date, isDateUnavailable, unavailableDates, updateModelValue, updateMonth, updateYear }
}
const defaultTemplate = `
  <p class="mb-2">Dates use <a href="https://moment.github.io/luxon/" target="_blank">Luxon DateTime</a></p>
  <PCalendar v-bind="args" :defaultValue="date" :is-date-unavailable="isDateUnavailable" :unavailable-dates="unavailableDates" @update:modelValue="updateModelValue" @update:month="updateMonth" @update:year="updateYear" />
`

const defaultExportableCode = `<script setup lang="ts">
import { DateTime } from 'luxon'

const unavailableDates = [DateTime.now().minus({ days: 1 })]

function isDateUnavailable(date: DateTime) {
  return unavailableDates.some((unavailableDate) => unavailableDate.hasSame(date, 'day'))
}
</script>

<template>
  <PCalendar
    :default-value="DateTime.now()"
    :unavailable-dates="unavailableDates"
    :is-date-unavailable="isDateUnavailable"
  />
</template>`

export const Default: Story = {
  args: {
  },
  parameters: {
    exportableCode: defaultExportableCode,
    docs: {
      source: {
        code: `<script lang="ts" setup>\n${defaultSetup.toString()}\n</script>\n\n<template>\n${defaultTemplate}\n</template>`,
      },
    },
  },
  render: (args) => ({
    components: { PCalendar },
    setup: () => defaultSetup(args),
    template: defaultTemplate,
  }),
}

export const WithMinMax: Story = {
  args: {
    minValue: DateTime.now().minus({ days: 7 }),
    maxValue: DateTime.now().plus({ days: 7 }),
  },
  parameters: {
    docs: {
      source: {
        code: `<script lang="ts" setup>\n${defaultSetup.toString()}\n</script>\n\n<template>\n${defaultTemplate}\n</template>`,
      },
    },
  },
  render: (args) => ({
    components: { PCalendar },
    setup: () => defaultSetup(args),
    template: `<div class="flex flex-col items-center gap-2">min: ${args.minValue?.toISO()}<br />max: ${args.maxValue?.toISO()}<br />${defaultTemplate}</div>`,
  }),
}

export const WithYearRange: Story = {
  args: {
    yearRange: 3,
  },
  parameters: {
    docs: {
      source: {
        code: `<script lang="ts" setup>\n${defaultSetup.toString()}\n</script>\n\n<template>\n${defaultTemplate}\n</template>`,
      },
    },
  },
  render: (args) => ({
    components: { PCalendar },
    setup: () => defaultSetup(args),
    template: `<div class="flex flex-col items-center gap-2">year range: ${args.yearRange}<br />${defaultTemplate}</div>`,
  }),
}

export const WithYears: Story = {
  args: {
    years: Array.from({ length: 5 }, (_, i) => new Date().getFullYear() + i),
  },
  parameters: {
    docs: {
      source: {
        code: `<script lang="ts" setup>\n${defaultSetup.toString()}\n</script>\n\n<template>\n${defaultTemplate}\n</template>`,
      },
    },
  },
  render: (args) => ({
    components: { PCalendar },
    setup: () => defaultSetup(args),
    template: `<div class="flex flex-col items-center gap-2">years: ${args.years?.join(', ')}<br />${defaultTemplate}</div>`,
  }),
}

export const WithLocale: Story = {
  args: {
    locale: 'ja-JP',
  },
  parameters: {
    docs: {
      source: {
        code: `<script lang="ts" setup>\n${defaultSetup.toString()}\n</script>\n\n<template>\n${defaultTemplate}\n</template>`,
      },
    },
  },
  render: (args) => ({
    components: { PCalendar },
    setup: () => defaultSetup(args),
    template: `<div class="flex flex-col items-center gap-2">locale: ${args.locale}<br />${defaultTemplate}</div>`,
  }),
}

export const Clearable: Story = {
  args: {
    clearable: true,
  },
  parameters: {
    docs: {
      source: {
        code: `<script lang="ts" setup>\n${defaultSetup.toString()}\n</script>\n\n<template>\n${defaultTemplate}\n</template>`,
      },
    },
  },
  render: (args) => ({
    components: { PCalendar },
    setup: () => defaultSetup(args),
    template: `<div class="flex flex-col items-center gap-2">clearable: ${args.clearable}<br />${defaultTemplate}</div>`,
  }),
}
