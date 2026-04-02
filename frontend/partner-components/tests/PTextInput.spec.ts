import { expect, test, vi } from 'vitest'
import { render } from 'vitest-browser-vue'
import { PTextInput, type PTextInputProps } from '@/index'
import { generateTestId } from '@/utils/testId'

test.each([
  { label: 'Name', placeholder: 'Enter name', size: 'medium' },
  { label: 'Name', placeholder: 'Enter name', size: 'small' },
  { label: 'Name', placeholder: 'Enter name', size: 'large' },
  { label: 'Email', type: 'email', placeholder: 'Enter email' },
  { label: 'Password', type: 'password', required: true },
  { label: 'Disabled', disabled: true, defaultValue: 'Cannot edit' },
  { label: 'Error', error: true, errorText: 'Field is required' },
  { label: 'Helper', helperText: 'Enter your full name' },
  { label: 'Error + Helper', error: true, errorText: 'Invalid', helperText: 'Hint text' },
  { placeholder: 'No label' },
])('PTextInput with props: %o', async (propsToTest) => {
  const testProps = propsToTest as PTextInputProps
  const onUpdateModelValue = vi.fn()

  const { getByTestId, getByText } = render({
    components: { PTextInput },
    template: `<PTextInput v-bind="testProps" @update:modelValue="onUpdateModelValue" />`,
    setup() {
      return { testProps, onUpdateModelValue }
    },
  })

  // --- Container ---
  const input = getByTestId(generateTestId('PTextInput'))
  expect(input).toBeInTheDocument()

  // --- Label ---
  if (testProps.label) {
    const label = getByText(testProps.label)
    expect(label).toBeInTheDocument()
  }

  // --- Required indicator ---
  if (testProps.required) {
    const asterisk = getByText('*')
    expect(asterisk).toBeInTheDocument()
  }

  // --- Disabled ---
  if (testProps.disabled) {
    expect(input).toHaveAttribute('disabled')
  } else {
    expect(input).not.toHaveAttribute('disabled')
  }

  // --- Error text takes priority over helper text ---
  if (testProps.error && testProps.errorText) {
    const errorLabel = getByText(testProps.errorText)
    expect(errorLabel).toBeInTheDocument()
  } else if (testProps.helperText) {
    const helperLabel = getByText(testProps.helperText)
    expect(helperLabel).toBeInTheDocument()
  }

  // --- Type attribute ---
  if (testProps.type) {
    expect(input).toHaveAttribute('type', testProps.type)
  }

  // --- Typing emits update:modelValue ---
  if (!testProps.disabled) {
    const expectedValue = 'Hello'
    await input.fill(expectedValue)
    await expect.poll(() => onUpdateModelValue).toHaveBeenCalledWith(expectedValue)
  }
})

test('clearable button clears input value', async () => {
  const onUpdateModelValue = vi.fn()

  const { getByTestId, getByRole } = render({
    components: { PTextInput },
    template: `<PTextInput v-bind="testProps" @update:modelValue="onUpdateModelValue" />`,
    setup() {
      return {
        testProps: { label: 'Name', defaultValue: 'Hello', clearable: true } as PTextInputProps,
        onUpdateModelValue,
      }
    },
  })

  const input = getByTestId(generateTestId('PTextInput'))
  expect(input).toHaveValue('Hello')

  const clearBtn = getByRole('button', { name: 'Clear' })
  await clearBtn.click()

  await expect.poll(() => onUpdateModelValue).toHaveBeenCalledWith('')
  await expect.element(input).toHaveValue('')
})
