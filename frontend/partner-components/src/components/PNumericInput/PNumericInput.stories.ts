import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { action } from 'storybook/actions'
import { PNumericInput, type PNumericInputProps } from './index'
import { computed } from 'vue'
import { sizeOptions } from '@/types/size'

type StoryArgs = PNumericInputProps & {
  style?: Intl.NumberFormatOptions['style']
  unit?: Intl.NumberFormatOptions['unit']
  unitDisplay?: Intl.NumberFormatOptions['unitDisplay']
  currency?: Intl.NumberFormatOptions['currency']
  currencyDisplay?: Intl.NumberFormatOptions['currencyDisplay']
  currencySign?: Intl.NumberFormatOptions['currencySign']
  minimumFractionDigits?: Intl.NumberFormatOptions['minimumFractionDigits']
  maximumFractionDigits?: Intl.NumberFormatOptions['maximumFractionDigits']
}

const meta: Meta<StoryArgs> = {
  component: PNumericInput,
  title: 'Components/PNumericInput',
  argTypes: {
    label: {
      control: 'text',
      description: 'The label for the numeric input',
    },
    id: {
      control: 'text',
      description: 'The id for the numeric input',
    },
    size: {
      control: 'select',
      options: sizeOptions,
      description: 'The size of the numeric input',
    },
    defaultValue: {
      control: 'number',
      description: 'The default value for the numeric input',
    },
    modelValue: {
      control: 'number',
      description: 'The model value for the numeric input',
    },
    min: {
      control: 'number',
      description: 'The minimum value for the numeric input',
    },
    max: {
      control: 'number',
      description: 'The maximum value for the numeric input',
    },
    step: {
      control: 'number',
      description: 'The step value for the numeric input',
    },
    stepSnapping: {
      control: 'boolean',
      description: 'Whether the step snapping is enabled',
    },
    focusOnChange: {
      control: 'boolean',
      description: 'Whether the focus is on change',
    },
    locale: {
      control: 'text',
      description: 'The locale for the numeric input',
    },
    formatOptions: {
      control: false,
      description: 'Composed from the individual formatOptions controls below',
    },
    disabled: {
      control: 'boolean',
      description: 'Whether the numeric input is disabled',
    },
    readonly: {
      control: 'boolean',
      description: 'Whether the numeric input is read-only',
    },
    disableWheelChange: {
      control: 'boolean',
      description: 'Whether the wheel change is disabled',
    },
    invertWheelChange: {
      control: 'boolean',
      description: 'Whether the wheel change is inverted',
    },
    required: {
      control: 'boolean',
      description: 'Whether the numeric input is required',
    },
    error: {
      control: 'boolean',
      description: 'Whether the numeric input has an error',
    },
    errorText: {
      control: 'text',
      description: 'The error text for the numeric input',
    },
    helperText: {
      control: 'text',
      description: 'The helper text for the numeric input',
    },
    // --- formatOptions ---
    style: {
      control: 'select',
      options: ['decimal', 'currency', 'percent', 'unit'],
      description: 'The formatting style (Intl.NumberFormatOptions.style)',
      table: {
        category: 'formatOptions',
      }
    },
    unit: {
      control: 'select',
      options: ['kilometer', 'mile', 'foot', 'inch', 'yard', 'mile', 'foot', 'inch', 'yard'],
      description: 'The unit to display (Intl.NumberFormatOptions.unit)',
      if: { arg: 'style', eq: 'unit' },
      table: {
        category: 'formatOptions',
      }
    },
    unitDisplay: {
      control: 'select',
      options: ['long', 'short', 'narrow'],
      description: 'How to display the unit (Intl.NumberFormatOptions.unitDisplay)',
      if: { arg: 'style', eq: 'unit' },
      table: {
        category: 'formatOptions',
      }
    },
    currency: {
      control: 'select',
      options: [
        'USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'CHF', 'CNY',
        'INR', 'MXN', 'BRL', 'KRW', 'SEK', 'NOK', 'DKK', 'NZD',
        'SGD', 'HKD', 'ZAR', 'PLN', 'CZK', 'HUF', 'ILS', 'THB',
      ],
      description: 'ISO 4217 currency code (only used when style is "currency")',
      if: { arg: 'style', eq: 'currency' },
      table: {
        category: 'formatOptions',
      }
    },
    currencyDisplay: {
      control: 'select',
      options: ['symbol', 'narrowSymbol', 'code', 'name'],
      description: 'How to display the currency (Intl.NumberFormatOptions.currencyDisplay). For example in New Zealand Dollars (NZD): symbol: Display the currency symbol (e.g., NZ$). narrowSymbol: Display the narrow currency symbol (e.g., $). code: Display the ISO 4217 currency code (e.g., NZD). name: Display the currency name (e.g., NZD => New Zealand Dollar).',
      if: { arg: 'style', eq: 'currency' },
      table: {
        category: 'formatOptions',
      }
    },
    currencySign: {
      control: 'select',
      options: ['standard', 'accounting'],
      description: 'Currency sign style (Intl.NumberFormatOptions.currencySign). Negative values are displayed with a minus sign or parentheses.',
      if: { arg: 'style', eq: 'currency' },
      table: {
        category: 'formatOptions',
      }
    },
    minimumFractionDigits: {
      control: { type: 'number', min: 0, max: 20 },
      description: 'Minimum fraction digits',
      table: {
        category: 'formatOptions',
      }
    },
    maximumFractionDigits: {
      control: { type: 'number', min: 0, max: 20 },
      description: 'Maximum fraction digits',
      table: {
        category: 'formatOptions',
      }
    },
  },
}

export default meta

type Story = StoryObj<StoryArgs>

const commmonSetup = (args: StoryArgs) => {
  const formatOptions = computed<Intl.NumberFormatOptions>(() => {
    const opts: Intl.NumberFormatOptions = {}
    if (args.style) opts.style = args.style

    switch (args.style) {
      case 'currency':
        if (args.currency) opts.currency = args.currency
        if (args.currencyDisplay) opts.currencyDisplay = args.currencyDisplay
        if (args.currencySign) opts.currencySign = args.currencySign
        break
      case 'unit':
        if (args.unit) opts.unit = args.unit
        if (args.unitDisplay) opts.unitDisplay = args.unitDisplay
        break
    }

    if (args.minimumFractionDigits != null) opts.minimumFractionDigits = args.minimumFractionDigits
    if (args.maximumFractionDigits != null) opts.maximumFractionDigits = args.maximumFractionDigits

    // Prevent min from exceeding max to avoid errors
    if (opts.minimumFractionDigits != null && opts.maximumFractionDigits != null) {
      opts.minimumFractionDigits = Math.min(opts.minimumFractionDigits, opts.maximumFractionDigits)
    }

    return opts
  })

  const formatOptionsJson = computed(() => JSON.stringify(formatOptions.value, null, 2))

  const formatOptionKeys = new Set(['style', 'currency', 'currencyDisplay', 'currencySign',
    'minimumFractionDigits', 'maximumFractionDigits', 'unit', 'unitDisplay', 'formatOptions'])

  const componentProps = computed(() =>
    Object.fromEntries(Object.entries(args).filter(([key]) => !formatOptionKeys.has(key)))
  )

  const onUpdateModelValue = action('update:modelValue')
  const onFocus = action('focus')
  const onBlur = action('blur')

  return { componentProps, formatOptions, formatOptionsJson, onUpdateModelValue, onFocus, onBlur }
}

const commonRender = (args: StoryArgs) => {
  return {
    components: { PNumericInput },
    setup() {
      return commmonSetup(args)
    },
    template: `
      <div>
        <PNumericInput 
          v-bind="componentProps" 
          :format-options="formatOptions" 
          @update:model-value="onUpdateModelValue" 
          @focus="onFocus" 
          @blur="onBlur" 
        />
        <details class="mt-4" open>
          <summary class="cursor-pointer text-gray-500">formatOptions</summary>
          <pre class="bg-gray-100 p-3 rounded text-sm">{{ formatOptionsJson }}</pre>
        </details>
      </div>
    `,
  }
}

export const Default: Story = {
  args: {
    label: 'Label',
    defaultValue: 1500.00,
    disabled: false,
    required: false,
    error: false,
    errorText: 'Error text',
    helperText: 'Helper text',
    // These populate the individual controls on load:
    style: 'currency',
    currency: 'USD',
    currencyDisplay: 'symbol',
    currencySign: 'standard',
    unit: 'mile',
    unitDisplay: 'long',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  },
  render: commonRender,
}

export const Currency: Story = {
  args: {
    label: 'Cost',
    defaultValue: 2500,
    style: 'currency',
    currency: 'GBP',
    currencyDisplay: 'symbol',
    currencySign: 'standard',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
    disabled: false,
    required: false,
    error: false,
    errorText: 'Error text',
    helperText: 'Helper text',
  },
  render: commonRender,
}

export const Percent: Story = {
  args: {
    label: 'Percentage',
    defaultValue: 0.5,
    step: 0.05,
    stepSnapping: true,
    focusOnChange: true,
    style: 'percent',
    disabled: false,
    required: false,
    error: false,
    errorText: 'Error text',
    helperText: 'Helper text',
  },
  render: commonRender,
}

export const Unit: Story = {
  args: {
    label: 'Distance',
    defaultValue: 160,
    style: 'unit',
    unit: 'mile',
    unitDisplay: 'long',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
    disabled: false,
    required: false,
    error: false,
    errorText: 'Error text',
    helperText: 'Helper text',
  },
  render: commonRender,
}