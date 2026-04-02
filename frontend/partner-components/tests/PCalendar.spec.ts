import { expect, test, vi } from 'vitest'
import { render } from 'vitest-browser-vue'
import { DateTime } from 'luxon'
import { PCalendar, type PCalendarProps } from '@/components/PCalendar'
import { generateTestId } from '@/utils/testId'

function renderCalendar(props: Partial<PCalendarProps> = {}) {
  const onUpdateModelValue = vi.fn()

  const testProps = { ...props } satisfies Partial<PCalendarProps>

  const screen = render({
    components: { PCalendar },
    template: `
      <PCalendar
        v-bind="testProps"
        @update:modelValue="onUpdateModelValue"
      />
    `,
    setup: () => ({ testProps, onUpdateModelValue }),
  })

  const calendar = screen.getByTestId(generateTestId('PCalendar'))

  return { ...screen, calendar, onUpdateModelValue }
}

test('renders calendar with day-of-week headers', () => {
  const { calendar } = renderCalendar()

  expect(calendar).toBeInTheDocument()
  for (const day of ['S', 'M', 'T', 'W', 'F']) {
    expect(calendar).toHaveTextContent(day)
  }
})

test('displays month and year selectors in heading', async () => {
  const date = DateTime.fromObject({ year: 2025, month: 6, day: 15 })
  const { calendar } = renderCalendar({ modelValue: date })

  await expect.element(calendar).toHaveTextContent('Jun')
  await expect.element(calendar).toHaveTextContent('2025')
})

test('month and year selectors update the date', async () => {
  const date = DateTime.fromObject({ year: 2025, month: 6, day: 15 })
  const { calendar, getByTestId } = renderCalendar({ modelValue: date })

  const monthSelector = calendar.getByTestId(generateTestId('PSelect', 'month'))
  await monthSelector.click()
  const monthMenu = getByTestId(generateTestId('PSelectMenu'))
  await expect.element(monthMenu).toHaveTextContent('Jul')
  await monthMenu.getByText('Jul').click()
  await expect.element(calendar).toHaveTextContent('Jul')

  const yearSelector = calendar.getByTestId(generateTestId('PSelect', 'year'))
  await yearSelector.click()
  const yearMenu = getByTestId(generateTestId('PSelectMenu'))
  await expect.element(yearMenu).toHaveTextContent('2026')
  await yearMenu.getByText('2027').click()
  await expect.element(calendar).toHaveTextContent('2027')
})

test('selecting a day cell emits update:date', async () => {
  const date = DateTime.fromObject({ year: 2025, month: 3, day: 1 })
  const { calendar, onUpdateModelValue } = renderCalendar({ modelValue: date })

  const day15 = calendar.getByRole('button', { name: /15/ })
  await day15.click()

  await expect.poll(() => onUpdateModelValue).toHaveBeenCalled()
  const emitted = onUpdateModelValue.mock.calls[0][0]
  expect(emitted.day).toBe(15)
  expect(emitted.month).toBe(3)
  expect(emitted.year).toBe(2025)
})

test('previous and next buttons navigate months', async () => {
  const date = DateTime.fromObject({ year: 2025, month: 6, day: 15 })
  const { calendar } = renderCalendar({ modelValue: date })

  await expect.element(calendar).toHaveTextContent('Jun')

  const prevBtn = calendar.getByRole('button', { name: /prev/i })
  await prevBtn.click()
  await expect.element(calendar).toHaveTextContent('May')

  const nextBtn = calendar.getByRole('button', { name: /next/i })
  await nextBtn.click()
  await expect.element(calendar).toHaveTextContent('Jun')
})

test('unavailable dates cannot be selected', async () => {
  const date = DateTime.fromObject({ year: 2025, month: 3, day: 1 })
  const unavailable = DateTime.fromObject({ year: 2025, month: 3, day: 10 })
  const { getByText, onUpdateModelValue } = renderCalendar({
    modelValue: date,
    unavailableDates: [unavailable],
  })

  const day10 = getByText('10', { exact: true })
  await expect.element(day10).toHaveAttribute('data-unavailable')

  await day10.click({ force: true })
  expect(onUpdateModelValue).not.toHaveBeenCalled()
})

test('disabled calendar prevents interaction', async () => {
  const date = DateTime.fromObject({ year: 2025, month: 3, day: 15 })
  const { getByText, onUpdateModelValue } = renderCalendar({ modelValue: date, disabled: true })

  const day10 = getByText('10', { exact: true })
  await expect.element(day10).toHaveAttribute('data-disabled')

  await day10.click({ force: true })
  expect(onUpdateModelValue).not.toHaveBeenCalled()
})

test('long month format shows full month names', async () => {
  const date = DateTime.fromObject({ year: 2025, month: 6, day: 15 })
  const { calendar } = renderCalendar({ modelValue: date, monthFormat: 'long' })

  await expect.element(calendar).toHaveTextContent('June')
})

test('selected date is visually marked', async () => {
  const date = DateTime.fromObject({ year: 2025, month: 3, day: 15 })
  const { getByText } = renderCalendar({ modelValue: date })

  const day15 = getByText('15', { exact: true })
  await expect.element(day15).toHaveAttribute('data-selected')
})

// --- Clearable ---

test('clear button is hidden when clearable is false', () => {
  const date = DateTime.fromObject({ year: 2025, month: 3, day: 15 })
  const { calendar } = renderCalendar({ modelValue: date })

  const clearBtn = calendar.getByText('Clear')
  expect(clearBtn).not.toBeInTheDocument()
})

test('clear button is visible when clearable is true', async () => {
  const date = DateTime.fromObject({ year: 2025, month: 3, day: 15 })
  const { getByText } = renderCalendar({ modelValue: date, clearable: true })

  await expect.element(getByText('Clear')).toBeVisible()
})

test('clicking clear resets the selected date', async () => {
  const date = DateTime.fromObject({ year: 2025, month: 3, day: 15 })
  const { getByText, onUpdateModelValue } = renderCalendar({ modelValue: date, clearable: true })

  const clearBtn = getByText('Clear')
  await clearBtn.click()

  await expect.poll(() => onUpdateModelValue).toHaveBeenCalledWith(undefined)
})

test('clear button is disabled when calendar is disabled', async () => {
  const date = DateTime.fromObject({ year: 2025, month: 3, day: 15 })
  const { getByRole } = renderCalendar({ modelValue: date, clearable: true, disabled: true })

  const clearBtn = getByRole('button', { name: 'Clear' })
  await expect.element(clearBtn).toHaveAttribute('disabled')
})

// --- minValue / maxValue ---

test('dates before minValue are disabled', async () => {
  const date = DateTime.fromObject({ year: 2025, month: 3, day: 15 })
  const minValue = DateTime.fromObject({ year: 2025, month: 3, day: 10 })
  const { getByRole, onUpdateModelValue } = renderCalendar({ modelValue: date, minValue })

  const day5 = getByRole('button', { name: /March 5/ })
  await expect.element(day5).toHaveAttribute('data-disabled')

  await day5.click({ force: true })
  expect(onUpdateModelValue).not.toHaveBeenCalled()
})

test('dates after maxValue are disabled', async () => {
  const date = DateTime.fromObject({ year: 2025, month: 3, day: 15 })
  const maxValue = DateTime.fromObject({ year: 2025, month: 3, day: 20 })
  const { getByRole, onUpdateModelValue } = renderCalendar({ modelValue: date, maxValue })

  const day25 = getByRole('button', { name: /March 25/ })
  await expect.element(day25).toHaveAttribute('data-disabled')

  await day25.click({ force: true })
  expect(onUpdateModelValue).not.toHaveBeenCalled()
})

test('dates within minValue and maxValue are selectable', async () => {
  const date = DateTime.fromObject({ year: 2025, month: 3, day: 15 })
  const minValue = DateTime.fromObject({ year: 2025, month: 3, day: 10 })
  const maxValue = DateTime.fromObject({ year: 2025, month: 3, day: 20 })
  const { getByText, onUpdateModelValue } = renderCalendar({ modelValue: date, minValue, maxValue })

  const day12 = getByText('12', { exact: true })
  await day12.click()

  await expect.poll(() => onUpdateModelValue).toHaveBeenCalled()
  const emitted = onUpdateModelValue.mock.calls[0][0]
  expect(emitted.day).toBe(12)
})

// --- isDateUnavailable function ---

test('isDateUnavailable function marks dates as unavailable', async () => {
  const date = DateTime.fromObject({ year: 2025, month: 3, day: 1 })
  const isDateUnavailable = (d: DateTime) => d.day >= 5 && d.day <= 8 && d.month === 3
  const { getByRole, onUpdateModelValue } = renderCalendar({ modelValue: date, isDateUnavailable })

  for (const day of [5, 6, 7, 8]) {
    const cell = getByRole('button', { name: new RegExp(`March ${day},`) })
    await expect.element(cell).toHaveAttribute('data-unavailable')
  }

  const day6 = getByRole('button', { name: /March 6,/ })
  await day6.click({ force: true })
  expect(onUpdateModelValue).not.toHaveBeenCalled()
})

// --- Custom years ---

test('custom years prop limits year selector options', async () => {
  const date = DateTime.fromObject({ year: 2025, month: 3, day: 15 })
  const { calendar, getByTestId } = renderCalendar({ modelValue: date, years: [2024, 2025, 2026] })

  const yearSelector = calendar.getByTestId(generateTestId('PSelect', 'year'))
  await yearSelector.click()

  const yearMenu = getByTestId(generateTestId('PSelectMenu'))
  await expect.element(yearMenu).toHaveTextContent('2024')
  await expect.element(yearMenu).toHaveTextContent('2025')
  await expect.element(yearMenu).toHaveTextContent('2026')
  expect(yearMenu).not.toHaveTextContent('2023')
  expect(yearMenu).not.toHaveTextContent('2027')
})

// --- Locale ---

test('locale changes month labels', async () => {
  const date = DateTime.fromObject({ year: 2025, month: 3, day: 15 })
  const { calendar } = renderCalendar({ modelValue: date, locale: 'ja-JP' })

  await expect.element(calendar).toHaveTextContent('3月')
})
