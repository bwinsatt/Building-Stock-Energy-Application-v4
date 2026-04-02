import { expect, test, vi } from 'vitest'
import { render } from 'vitest-browser-vue'
import { userEvent } from 'vitest/browser'
import { DateTime } from 'luxon'
import { PDateInput, type PDateInputProps } from '@/components/PDateInput'
import { generateTestId } from '@/utils/testId'

function renderDateInput(props: Partial<PDateInputProps> = {}) {
  const onUpdateModelValue = vi.fn()

  const testProps = { label: 'Date', ...props } satisfies Partial<PDateInputProps>

  const screen = render({
    components: { PDateInput },
    template: `<PDateInput v-bind="testProps" @update:modelValue="onUpdateModelValue" />`,
    setup: () => ({ testProps, onUpdateModelValue }),
  })

  const dateInput = screen.getByTestId(generateTestId('PDateInput'))

  return { ...screen, dateInput, onUpdateModelValue }
}

// --- Rendering ---

test.each([
  { label: 'Date', size: 'medium' as const },
  { label: 'Date', size: 'small' as const },
  { label: 'Date', size: 'large' as const },
  { label: 'Date', disabled: true },
  { label: 'Required', required: true },
  { label: 'Error', error: true, errorText: 'Invalid date' },
  { label: 'Helper', helperText: 'Pick a date' },
  { label: 'Both', error: true, errorText: 'Bad date', helperText: 'Hint' },
])('renders correctly with props: %o', async (propsToTest) => {
  const testProps = propsToTest as Partial<PDateInputProps>
  const { dateInput, getByText } = renderDateInput(testProps)

  expect(dateInput).toBeInTheDocument()

  if (testProps.label)
    expect(getByText(testProps.label)).toBeInTheDocument()

  if (testProps.required)
    expect(getByText('*')).toBeInTheDocument()

  if (testProps.error && testProps.errorText)
    expect(getByText(testProps.errorText)).toBeInTheDocument()
  else if (testProps.helperText)
    expect(getByText(testProps.helperText)).toBeInTheDocument()
})

test('renders date segments (MM/DD/YYYY placeholders)', () => {
  const { dateInput } = renderDateInput()

  expect(dateInput).toHaveTextContent('MM')
  expect(dateInput).toHaveTextContent('DD')
  expect(dateInput).toHaveTextContent('YYYY')
})

test('displays default value in segments with leading zeroes', async () => {
  const date = DateTime.fromObject({ year: 2025, month: 3, day: 5 })
  const { dateInput } = renderDateInput({ defaultValue: date })

  await expect.element(dateInput).toHaveTextContent('03')
  await expect.element(dateInput).toHaveTextContent('05')
  await expect.element(dateInput).toHaveTextContent('2025')
})

// --- Calendar trigger ---

test('clicking calendar icon opens the calendar popover', async () => {
  const { dateInput, getByTestId } = renderDateInput()

  const trigger = dateInput.getByRole('button')
  await trigger.click()

  const calendar = getByTestId(generateTestId('PCalendar'))
  await expect.element(calendar).toBeVisible()
})

test('selecting a date in the popover updates the input', async () => {
  const { dateInput, onUpdateModelValue, getByTestId, getByText } = renderDateInput()

  const trigger = dateInput.getByRole('button')
  await trigger.click()

  const calendar = getByTestId(generateTestId('PCalendar'))
  await expect.element(calendar).toBeVisible()

  const day15 = getByText('15', { exact: true })
  await day15.click()

  await expect.poll(() => onUpdateModelValue).toHaveBeenCalled()
  const emitted = onUpdateModelValue.mock.calls[0][0]
  expect(emitted.day).toBe(15)
})

// --- Disabled ---

test('disabled input cannot open calendar', async () => {
  const { dateInput } = renderDateInput({ disabled: true })

  const trigger = dateInput.getByRole('button')
  await trigger.click({ force: true })

  await expect.element(dateInput).not.toHaveTextContent('Su')
})

// --- Sizes ---

test.each([
  { size: 'small' as const },
  { size: 'medium' as const },
  { size: 'large' as const },
])('renders at size "$size"', ({ size }) => {
  const { dateInput } = renderDateInput({ size })
  expect(dateInput).toBeInTheDocument()
})

// --- Keyboard entry ---

test('typing into date segments updates the model value', async () => {
  const { dateInput, onUpdateModelValue } = renderDateInput()

  const segments = await dateInput.getByRole('spinbutton').all()

  await segments[0].click()
  await userEvent.keyboard('03')

  await segments[1].click()
  await userEvent.keyboard('05')

  await segments[2].click()
  await userEvent.keyboard('2025')

  await expect.poll(() => onUpdateModelValue).toHaveBeenCalled()
  const emitted = onUpdateModelValue.mock.lastCall![0]
  expect(emitted.month).toBe(3)
  expect(emitted.day).toBe(5)
  expect(emitted.year).toBe(2025)
})

// --- calendarProps: unavailableDates ---

test('unavailable dates are marked in the calendar popover', async () => {
  const unavailable = DateTime.fromObject({ year: 2025, month: 3, day: 10 })
  const { dateInput, getByText, getByTestId } = renderDateInput({
    defaultValue: DateTime.fromObject({ year: 2025, month: 3, day: 1 }),
    calendarProps: { unavailableDates: [unavailable] },
  })

  const trigger = dateInput.getByRole('button')
  await trigger.click()
  await expect.element(getByTestId(generateTestId('PCalendar'))).toBeVisible()

  const day10 = getByText('10', { exact: true })
  await expect.element(day10).toHaveAttribute('data-unavailable')
})

// --- calendarProps: minValue / maxValue ---

test('dates before calendarProps.minValue are disabled in popover', async () => {
  const { dateInput, getByRole, getByTestId } = renderDateInput({
    defaultValue: DateTime.fromObject({ year: 2025, month: 3, day: 15 }),
    calendarProps: { minValue: DateTime.fromObject({ year: 2025, month: 3, day: 10 }) },
  })

  const trigger = dateInput.getByRole('button')
  await trigger.click()
  await expect.element(getByTestId(generateTestId('PCalendar'))).toBeVisible()

  const day5 = getByRole('button', { name: /March 5/ })
  await expect.element(day5).toHaveAttribute('data-disabled')
})

test('dates after calendarProps.maxValue are disabled in popover', async () => {
  const { dateInput, getByRole, getByTestId } = renderDateInput({
    defaultValue: DateTime.fromObject({ year: 2025, month: 3, day: 15 }),
    calendarProps: { maxValue: DateTime.fromObject({ year: 2025, month: 3, day: 20 }) },
  })

  const trigger = dateInput.getByRole('button')
  await trigger.click()
  await expect.element(getByTestId(generateTestId('PCalendar'))).toBeVisible()

  const day25 = getByRole('button', { name: /March 25/ })
  await expect.element(day25).toHaveAttribute('data-disabled')
})

// --- calendarProps: clearable ---

test('clear button is visible in calendar popover when clearable', async () => {
  const { dateInput, getByTestId, getByText } = renderDateInput({
    defaultValue: DateTime.fromObject({ year: 2025, month: 3, day: 15 }),
    calendarProps: { clearable: true },
  })

  const trigger = dateInput.getByRole('button')
  await trigger.click()

  await expect.element(getByTestId(generateTestId('PCalendar'))).toBeVisible()
  await expect.element(getByText('Clear')).toBeVisible()
})

test('clicking clear in popover emits undefined modelValue', async () => {
  const { dateInput, getByTestId, getByText, onUpdateModelValue } = renderDateInput({
    defaultValue: DateTime.fromObject({ year: 2025, month: 3, day: 15 }),
    calendarProps: { clearable: true },
  })

  const trigger = dateInput.getByRole('button')
  await trigger.click()

  await expect.element(getByTestId(generateTestId('PCalendar'))).toBeVisible()

  const clearBtn = getByText('Clear')
  await clearBtn.click()

  await expect.poll(() => onUpdateModelValue).toHaveBeenCalledWith(undefined)
})

// --- Locale ---

test('locale changes date segment order', async () => {
  const { dateInput } = renderDateInput({
    locale: 'en-GB',
    defaultValue: DateTime.fromObject({ year: 2025, month: 3, day: 5 }),
  })

  await expect.element(dateInput).toHaveTextContent('05')
  await expect.element(dateInput).toHaveTextContent('03')

  const el = dateInput.element() as HTMLElement
  const text = el.textContent ?? ''
  const dayIndex = text.indexOf('05')
  const monthIndex = text.indexOf('03')
  expect(dayIndex).toBeLessThan(monthIndex)
})