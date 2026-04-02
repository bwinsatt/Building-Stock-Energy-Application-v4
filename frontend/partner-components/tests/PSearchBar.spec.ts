import { expect, test, vi } from 'vitest'
import { render } from 'vitest-browser-vue'
import { PSearchBar, type PSearchBarProps } from '@/components/PSearchBar'
import { generateTestId } from '@/utils/testId'

test.each([
  { placeholder: 'Search...' },
  { placeholder: 'Search...', size: 'small' },
  { placeholder: 'Search...', size: 'medium' },
  { placeholder: 'Search...', size: 'large' },
  { placeholder: 'Search...', disabled: true },
  { placeholder: 'Search...', disabled: true, defaultValue: 'locked' },
  { placeholder: 'Search...', defaultValue: 'prefilled' },
  { placeholder: 'Search...', defaultValue: 'prefilled', size: 'small' },
  { placeholder: 'Search...', defaultValue: 'prefilled', size: 'large' },
  { placeholder: 'Search...', defaultValue: 'prefilled', size: 'large', debounce: 100 },
])('PSearchBar with props: %o', async (propsToTest) => {
  const testProps = propsToTest as PSearchBarProps
  const onUpdateModelValue = vi.fn()
  const onUpdateDebouncedValue = vi.fn()
  const onSearch = vi.fn()

  const { getByTestId } = render({
    components: { PSearchBar },
    template: `<PSearchBar v-bind="testProps" @update:modelValue="onUpdateModelValue" @update:debouncedValue="onUpdateDebouncedValue" @search="onSearch" />`,
    setup() {
      return { testProps, onUpdateModelValue, onUpdateDebouncedValue, onSearch }
    },
  })

  const container = getByTestId(generateTestId('PSearchBar'))
  expect(container).toBeInTheDocument()

  const input = container.getByTestId(generateTestId('PSearchBar', 'input')).element() as HTMLInputElement
  expect(input).toBeTruthy()

  // --- Placeholder ---
  if (testProps.placeholder) {
    expect(input.placeholder).toBe(testProps.placeholder)
  }

  // --- Disabled ---
  if (testProps.disabled) {
    expect(input.disabled).toBe(true)
    expect(container).toHaveAttribute('data-disabled', 'true')
  } else {
    expect(input.disabled).toBe(false)
  }

  // --- Default value ---
  if (testProps.defaultValue) {
    expect(input.value).toBe(String(testProps.defaultValue))
  }

  // --- Search icon focuses input ---
  if(!testProps.disabled) {
    const searchIcon = container.getByTestId(generateTestId('PIcon', 'search'))
    expect(searchIcon).toBeInTheDocument()
    await searchIcon.click()
    await expect.element(input).toHaveFocus()
  }

  // --- Typing emits update:modelValue ---
  if (!testProps.disabled) {
    const expectedValue = 'Hello'
    await container.getByRole('textbox').fill(expectedValue)
    await expect.poll(() => onUpdateModelValue).toHaveBeenCalledWith(expectedValue)
  }

  // --- Search button emits search event ---
  const searchButton = container.getByTestId(generateTestId('PButton', 'search'))
  expect(searchButton).toBeInTheDocument()

  if (!testProps.disabled) {
    onSearch.mockClear()
    await searchButton.click()
    const expectedSearchValue = testProps.disabled ? undefined : input.value
    await expect.poll(() => onSearch).toHaveBeenCalledWith(expectedSearchValue)
  }

  // --- Enter key emits search event ---
  if (!testProps.disabled) {
    onSearch.mockClear()
    await input.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter' }))
    const expectedSearchValue = testProps.disabled ? undefined : input.value
    await expect.poll(() => onSearch).toHaveBeenCalledWith(expectedSearchValue)
  }

  // --- Clear button resets value ---
  if (input.value) {
    const clearButton = container.getByTestId(generateTestId('PButton', 'clear'))
    expect(clearButton).toBeInTheDocument()

    if (!testProps.disabled) {
      onUpdateModelValue.mockClear()
      await clearButton.click()
      await expect.poll(() => onUpdateModelValue).toHaveBeenCalledWith('')
      await expect.poll(() => input.value).toBe('')
    }
  }

  // --- Debounce, only test if debounce is provided to avoid lengthy test times ---
  if(!testProps.disabled && testProps.debounce) {
    onUpdateDebouncedValue.mockClear()
    const debouncedValue = "debounced value"
    await container.getByRole('textbox').fill(debouncedValue)
    await expect.poll(() => onUpdateDebouncedValue, { timeout: testProps.debounce + 500 }).toHaveBeenCalledWith(debouncedValue)
  }
})
