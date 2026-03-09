import { expect, test, vi } from 'vitest'
import { render } from 'vitest-browser-vue'
import { PTextArea, type PTextAreaProps } from '@/index'
import { generateTestId } from '@/utils/testId'

test.each([
  { label: 'Description', placeholder: 'Enter description', size: 'medium' },
  { label: 'Notes', placeholder: 'Enter notes', size: 'small' },
  { label: 'Comments', placeholder: 'Enter comments', size: 'large' },
  { label: 'Bio', maxLength: 100 },
  { label: 'Fixed', fixedHeight: true },
  { label: 'Resizable', resize: true },
  { label: 'Required', required: true },
  { label: 'Disabled', disabled: true, defaultValue: 'Cannot edit' },
  { label: 'Error', error: true, errorText: 'Field is required' },
  { label: 'Helper', helperText: 'Keep it brief' },
  { label: 'Error + Helper w/ Error', error: true, errorText: 'Too long', helperText: 'Hint text' },
  { label: 'Error + Helper w/o Error', error: false, errorText: 'Too long', helperText: 'Hint text' },
  { placeholder: 'No label' },
])('PTextArea with props: %o', async (propsToTest) => {
  const testProps = propsToTest as PTextAreaProps
  const onUpdateModelValue = vi.fn()

  const { getByTestId, getByText } = render({
    components: { PTextArea },
    template: `<PTextArea v-bind="testProps" @update:modelValue="onUpdateModelValue" />`,
    setup() {
      return { testProps, onUpdateModelValue }
    },
  })

  // --- Container ---
  const textarea = getByTestId(generateTestId('PTextArea'))
  expect(textarea).toBeInTheDocument()

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

  // --- Max length counter ---
  if (testProps.maxLength) {
    const counter = getByText(`/${testProps.maxLength}`, { exact: false })
    expect(counter).toBeInTheDocument()
  }

  // --- Disabled ---
  if (testProps.disabled) {
    expect(textarea).toHaveAttribute('disabled')
  } else {
    expect(textarea).not.toHaveAttribute('disabled')
  }

  // --- Error text takes priority over helper text ---
  if (testProps.error && testProps.errorText) {
    const errorLabel = getByText(testProps.errorText)
    expect(errorLabel).toBeInTheDocument()
  } else if (testProps.helperText) {
    const helperLabel = getByText(testProps.helperText)
    expect(helperLabel).toBeInTheDocument()
  }

  // --- Typing emits update:modelValue ---
  if (!testProps.disabled) {
    const expectedValue = 'Hello'
    await textarea.fill(expectedValue)
    await expect.poll(() => onUpdateModelValue).toHaveBeenCalledWith(expectedValue)
  }

  // --- Max length counter updates after typing ---
  if (testProps.maxLength && !testProps.disabled) {
    const initialCounter = getByText(`5/${testProps.maxLength}`)
    expect(initialCounter).toBeInTheDocument()

    // --- Update value and check counter ---
    const updatedValue = 'Hello world'
    await textarea.fill(updatedValue)
    await expect.poll(() => onUpdateModelValue).toHaveBeenCalledWith(updatedValue)
    const updatedCounter = getByText(`${updatedValue.length}/${testProps.maxLength}`)
    expect(updatedCounter).toBeInTheDocument()
  }
})
