import { expect, test, vi } from 'vitest'
import { render } from 'vitest-browser-vue'
import { PSelect, type PSelectProps } from '@/components/PSelect'
import type { PMenuItemProps } from '@/components/PMenu'
import { generateTestId } from '@/utils/testId'

const defaultItems: PMenuItemProps[] = [
  { id: '1', label: 'Apple' },
  { id: '2', label: 'Banana' },
  { id: '3', label: 'Cherry' },
  { id: '4', label: 'Date', disabled: true },
]

function renderSelect(props: Partial<PSelectProps> = {}) {
  const onApply = vi.fn()
  const onClear = vi.fn()
  const onUpdateOpen = vi.fn()
  const onUpdateModelValue = vi.fn()

  const testProps = {
    items: defaultItems,
    type: 'single' as const,
    placeholder: 'Select an item',
    label: 'Fruit',
    ...props,
  } satisfies PSelectProps

  const screen = render({
    components: { PSelect },
    template: `
      <PSelect
        v-bind="testProps"
        @apply="onApply"
        @clear="onClear"
        @update:open="onUpdateOpen"
        @update:modelValue="onUpdateModelValue"
      />
    `,
    setup: () => ({ testProps, onApply, onClear, onUpdateOpen, onUpdateModelValue }),
  })

  const button = screen.getByTestId(generateTestId('PSelect'))

  return { ...screen, button, onApply, onClear, onUpdateOpen, onUpdateModelValue }
}

// --- Rendering ---

test('renders placeholder when nothing is selected', () => {
  const { button } = renderSelect()

  expect(button).toBeInTheDocument()
  expect(button).toHaveTextContent('Select an item')
})

test('renders label when provided', () => {
  const { getByText } = renderSelect({ label: 'Fruit' })

  expect(getByText('Fruit')).toBeInTheDocument()
})

test('renders required asterisk when required', () => {
  const { getByText } = renderSelect({ label: 'Fruit', required: true })

  expect(getByText('*')).toBeInTheDocument()
})

test('renders helper text', () => {
  const { getByText } = renderSelect({ helperText: 'Pick your favorite' })

  expect(getByText('Pick your favorite')).toBeInTheDocument()
})

test('renders error text instead of helper text when error is true', async () => {
  const { getByText } = renderSelect({
    helperText: 'Pick your favorite',
    errorText: 'Selection required',
    error: true,
  })

  expect(getByText('Selection required')).toBeInTheDocument()
  await expect.element(getByText('Pick your favorite')).not.toBeInTheDocument()
})

test('renders helper text when error is false', async () => {
  const { getByText } = renderSelect({
    helperText: 'Pick your favorite',
    errorText: 'Selection required',
    error: false,
  })

  expect(getByText('Pick your favorite')).toBeInTheDocument()
  await expect.element(getByText('Selection required')).not.toBeInTheDocument()
})

// --- Disabled ---

test('disabled select cannot be opened', async () => {
  const { button, onUpdateOpen } = renderSelect({ disabled: true })

  await expect.element(button).toHaveAttribute('disabled')

  await button.click({ force: true })
  expect(onUpdateOpen).not.toHaveBeenCalled()
})

// --- Single-select ---

test('single: opens dropdown and shows items on click', async () => {
  const { button, getByText, onUpdateOpen } = renderSelect()

  await button.click()

  await expect.poll(() => onUpdateOpen).toHaveBeenCalledWith(true)
  await expect.element(getByText('Apple')).toBeVisible()
  await expect.element(getByText('Banana')).toBeVisible()
  await expect.element(getByText('Cherry')).toBeVisible()
})

test('single: selecting an item updates display and emits', async () => {
  const { button, getByText, onApply, onUpdateModelValue } = renderSelect()

  await button.click()

  await expect.element(getByText('Apple')).toBeVisible()
  await getByText('Apple').click()

  await expect.poll(() => onApply).toHaveBeenCalledWith(
    expect.arrayContaining([expect.objectContaining({ label: 'Apple' })]),
  )
  await expect.poll(() => onUpdateModelValue).toHaveBeenCalledWith('Apple')
})

test('single: shows selected value from modelValue', () => {
  const { button } = renderSelect({ modelValue: 'Banana' })

  expect(button).toHaveTextContent('Banana')
  expect(button.element().textContent).not.toContain('Select an item')
})

// --- Multi-select ---

test('multi: opens dropdown with checkboxes', async () => {
  const { button, getByRole, onUpdateOpen } = renderSelect({ type: 'multi' })

  await button.click()

  await expect.poll(() => onUpdateOpen).toHaveBeenCalledWith(true)

  const checkboxes = getByRole('menuitemcheckbox')
  await expect.poll(() => checkboxes.all()).toHaveLength(5) // Select All + 4 items
})

test('multi: shows selected values from modelValue array', () => {
  const { button } = renderSelect({
    type: 'multi',
    modelValue: ['Apple', 'Cherry'],
  })

  expect(button).toHaveTextContent('Apple')
  expect(button).toHaveTextContent('Cherry')
})

test('multi: shows placeholder when modelValue is empty array', () => {
  const { button } = renderSelect({
    type: 'multi',
    modelValue: [],
  })

  expect(button).toHaveTextContent('Select an item')
})

test('multi: clear emits clear and update:modelValue', async () => {
  const { button, getByText, onClear, onUpdateModelValue, onUpdateOpen } = renderSelect({
    type: 'multi',
    modelValue: ['Apple', 'Banana'],
    hideFooter: false,
    clearableMenu: true,
  })

  await button.click()
  await expect.poll(() => onUpdateOpen).toHaveBeenCalledWith(true)

  const clearBtn = getByText('Clear (2)')
  await expect.element(clearBtn).toBeVisible()
  await clearBtn.click()

  expect(onClear).toHaveBeenCalled()
  await expect.poll(() => onUpdateModelValue).toHaveBeenCalledWith([])
})

// --- Chip variant ---

test('chip variant renders chips for selected values', () => {
  const { button } = renderSelect({
    type: 'multi',
    variant: 'chip',
    modelValue: ['Apple', 'Banana'],
  })

  expect(button).toHaveTextContent('Apple')
  expect(button).toHaveTextContent('Banana')
})

test('chip variant renders placeholder when empty', () => {
  const { button } = renderSelect({
    type: 'multi',
    variant: 'chip',
    modelValue: [],
  })

  expect(button).toHaveTextContent('Select an item')
})

// --- Sizes ---

test.each([
  { size: 'small' as const },
  { size: 'medium' as const },
  { size: 'large' as const },
])('renders at size "$size"', ({ size }) => {
  const { button } = renderSelect({ size })
  expect(button).toBeInTheDocument()
})

// --- Open state ---

test('emits update:open when opened and closed', async () => {
  const { button, onUpdateOpen } = renderSelect()

  await button.click()
  await expect.poll(() => onUpdateOpen).toHaveBeenCalledWith(true)

  await button.click()
  await expect.poll(() => onUpdateOpen).toHaveBeenCalledWith(false)
})

// --- Searchable ---

test('shows search bar when searchable', async () => {
  const { button, getByTestId, onUpdateOpen } = renderSelect({ searchable: true })

  await button.click()
  await expect.poll(() => onUpdateOpen).toHaveBeenCalledWith(true)

  await expect.element(getByTestId(generateTestId('PSearchBar'))).toBeVisible()
})

test('does not show search bar when searchable is false', async () => {
  const { button, getByTestId, onUpdateOpen } = renderSelect({ searchable: false })

  await button.click()
  await expect.poll(() => onUpdateOpen).toHaveBeenCalledWith(true)

  await expect.element(getByTestId(generateTestId('PSearchBar'))).not.toBeInTheDocument()
})

// --- Clearable (trigger-level) ---

test('single: clearable button clears selected value', async () => {
  const { getByRole, onClear, onUpdateModelValue } = renderSelect({
    modelValue: 'Apple',
    clearable: true,
  })

  const clearBtn = getByRole('button', { name: 'Clear' })
  await expect.element(clearBtn).toBeVisible()
  await clearBtn.click()

  expect(onClear).toHaveBeenCalled()
  await expect.poll(() => onUpdateModelValue).toHaveBeenCalledWith(null)
})

test('multi: clearable button clears all selected values', async () => {
  const { getByRole, onClear, onUpdateModelValue } = renderSelect({
    type: 'multi',
    modelValue: ['Apple', 'Banana'],
    clearable: true,
  })

  const clearBtn = getByRole('button', { name: 'Clear' })
  await expect.element(clearBtn).toBeVisible()
  await clearBtn.click()

  expect(onClear).toHaveBeenCalled()
  await expect.poll(() => onUpdateModelValue).toHaveBeenCalledWith([])
})
