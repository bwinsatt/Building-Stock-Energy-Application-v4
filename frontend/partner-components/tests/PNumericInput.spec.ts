import { expect, test, vi } from 'vitest'
import { render } from 'vitest-browser-vue'
import { userEvent } from 'vitest/browser'
import { PNumericInput, type PNumericInputProps } from '@/components/PNumericInput'
import { generateTestId } from '@/utils/testId'

const CONTAINER_ID = generateTestId('PNumericInput')
const INPUT_ID = generateTestId('PNumericInput', 'input')

function renderNumericInput(testProps: PNumericInputProps) {
  const onUpdateModelValue = vi.fn()
  const onFocus = vi.fn()
  const onBlur = vi.fn()

  const screen = render({
    components: { PNumericInput },
    template: `<PNumericInput v-bind="testProps" @update:modelValue="onUpdateModelValue" @focus="onFocus" @blur="onBlur" />`,
    setup: () => ({ testProps, onUpdateModelValue, onFocus, onBlur }),
  })

  const container = screen.getByTestId(CONTAINER_ID)
  const input = container.getByTestId(INPUT_ID)

  return { ...screen, container, input, onUpdateModelValue, onFocus, onBlur }
}

test.each([
  { label: 'Label', size: 'medium' },
  { label: 'Label', size: 'small' },
  { label: 'Label', size: 'large' },
  { label: 'Label', size: 'medium', disabled: true },
  { label: 'Label', size: 'small', disabled: true },
  { label: 'Label', size: 'large', disabled: true },
  { label: 'Required', required: true },
  { label: 'Error', error: true, errorText: 'Field is required' },
  { label: 'Helper', helperText: 'Enter a value' },
  { label: 'Error + Helper', error: true, errorText: 'Invalid', helperText: 'Hint text' },
])('renders correctly with props: %o', async (propsToTest) => {
  const testProps = propsToTest as PNumericInputProps
  const { container, input, getByText, onUpdateModelValue } = renderNumericInput(testProps)

  expect(container).toBeInTheDocument()
  expect(input.element()).toBeTruthy()

  if (testProps.label)
    expect(getByText(testProps.label)).toBeInTheDocument()

  if (testProps.required)
    expect(getByText('*')).toBeInTheDocument()

  if (testProps.disabled)
    expect(input.element()).toHaveAttribute('disabled')
  else
    expect(input.element()).not.toHaveAttribute('disabled')

  if (testProps.error && testProps.errorText)
    expect(getByText(testProps.errorText)).toBeInTheDocument()
  else if (testProps.helperText)
    expect(getByText(testProps.helperText)).toBeInTheDocument()

  if (!testProps.disabled) {
    await input.fill('100')
    await userEvent.tab()
    await expect.poll(() => onUpdateModelValue).toHaveBeenCalledWith(100)
  }
})

test('increment and decrement update value by step', async () => {
  const { container, onUpdateModelValue } = renderNumericInput({
    label: 'Counter', defaultValue: 10, step: 5,
  })

  const increase = container.getByRole('button', { name: /increase/i })
  const decrease = container.getByRole('button', { name: /decrease/i })

  await increase.click()
  await expect.poll(() => onUpdateModelValue).toHaveBeenCalledWith(15)

  onUpdateModelValue.mockClear()
  await decrease.click()
  await expect.poll(() => onUpdateModelValue).toHaveBeenCalledWith(10)
})

test('typed value above max is clamped on commit', async () => {
  const { input, onUpdateModelValue } = renderNumericInput({
    label: 'Clamped', defaultValue: 5, min: 0, max: 10, step: 1,
  })

  await input.fill('99')
  await userEvent.tab()
  await expect.poll(() => onUpdateModelValue).toHaveBeenCalledWith(10)
})

test('buttons are disabled at min/max boundaries', async () => {
  const { container, input } = renderNumericInput({
    label: 'Boundary', defaultValue: 10, min: 0, max: 10, step: 1,
  })

  const increase = container.getByRole('button', { name: /increase/i })
  const decrease = container.getByRole('button', { name: /decrease/i })

  await expect.element(increase).toHaveAttribute('disabled')
  await expect.element(decrease).not.toHaveAttribute('disabled')

  await input.fill('0')
  await userEvent.tab()

  await expect.element(decrease).toHaveAttribute('disabled')
  await expect.element(increase).not.toHaveAttribute('disabled')
})

test('buttons are hidden without step prop', async () => {
  const { container } = renderNumericInput({ label: 'No step', defaultValue: 0 })

  expect(container.element().querySelectorAll('button').length).toBe(0)
})

test('currency format displays correctly', async () => {
  const { input, onUpdateModelValue } = renderNumericInput({
    label: 'Price',
    defaultValue: 1234.5,
    formatOptions: { style: 'currency', currency: 'USD', minimumFractionDigits: 2 },
  })

  const value = () => (input.element() as HTMLInputElement).value
  await expect.poll(value).toContain('$')
  await expect.poll(value).toContain('1,234.50')

  await input.fill('99.01')
  await userEvent.tab()
  await expect.poll(() => onUpdateModelValue).toHaveBeenCalledWith(99.01)
})

test('clearable button clears input value', async () => {
  const { container, input, onUpdateModelValue } = renderNumericInput({
    label: 'Clearable', defaultValue: 42, clearable: true,
  })

  const clearBtn = container.getByRole('button', { name: 'Clear' })
  await clearBtn.click()

  await expect.poll(() => onUpdateModelValue).toHaveBeenCalledWith(null)
  await expect.poll(() => (input.element() as HTMLInputElement).value).toBe('')
})

test('clearable button clears currency formatted value', async () => {
  const { container, input, onUpdateModelValue } = renderNumericInput({
    label: 'Price',
    defaultValue: 99.99,
    clearable: true,
    formatOptions: { style: 'currency', currency: 'USD', minimumFractionDigits: 2 },
  })

  const clearBtn = container.getByRole('button', { name: 'Clear' })
  await clearBtn.click()

  await expect.poll(() => onUpdateModelValue).toHaveBeenCalledWith(null)
  await expect.poll(() => (input.element() as HTMLInputElement).value).toBe('')
})

test('percent format displays correctly', async () => {
  const { input, onUpdateModelValue } = renderNumericInput({
    label: 'Rate',
    defaultValue: 0.75,
    formatOptions: { style: 'percent' },
  })

  const value = () => (input.element() as HTMLInputElement).value
  await expect.poll(value).toContain('%')
  await expect.poll(value).toContain('75')

  const tests = [
    { value: '120', expected: 1.2 },
    { value: '-12', expected: -0.12 },
    { value: '0', expected: 0 },
    { value: '100', expected: 1 },
  ]
  for (const test of tests) {
    onUpdateModelValue.mockClear()
    await input.fill(test.value)
    await userEvent.tab()
    await expect.poll(() => onUpdateModelValue).toHaveBeenCalledWith(test.expected)
  }
})
