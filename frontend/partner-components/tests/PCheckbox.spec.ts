import { expect, test, vi } from 'vitest'
import { render } from 'vitest-browser-vue'
import { PCheckbox, type PCheckboxProps } from '@/index'
import type { Size } from '@/types/size'
import { generateTestId } from '@/utils/testId'

test.each([
  { checked: true, indeterminate: false, disabled: false, size: 'small', class: 'test-class' },
  { checked: false, indeterminate: false, disabled: false, size: 'medium', required: true },
  { checked: false, indeterminate: true, disabled: false, size: 'large', id: 'checkbox-2' },
  { checked: true, indeterminate: false, disabled: true, size: 'medium', label: 'Checkbox label 2' },
  { checked: false, indeterminate: false, disabled: true, size: 'small' },
  { checked: false, indeterminate: false, disabled: false, size: 'medium', label: 'Checkbox label', id: 'checkbox-3' },
  { checked: true, indeterminate: true, disabled: true },
  {}
])('PCheckbox with props: %o', async (propsToTest) => {
  const onChange = vi.fn()
  const checkboxProps: PCheckboxProps = {
    ...propsToTest,
    onChange,
    size: propsToTest.size as Size,
  }
  const { getByRole, getByTestId } = render(PCheckbox, {
    props: checkboxProps,
  })

  const testId = generateTestId('PCheckbox', checkboxProps.id || checkboxProps.label)
  const checkbox = getByTestId(testId)
  
  expect(checkbox).toBeInTheDocument()
  if (checkboxProps.label) {
    expect(checkbox).toHaveTextContent(checkboxProps.label)

    const checkboxLabel = getByTestId('plabel')
    if (checkboxProps.required) {
      expect(checkboxLabel).toHaveTextContent(`${checkboxProps.label}*`)
    }
  }
  if (checkboxProps.class) {
    expect(checkbox).toHaveClass(checkboxProps.class)
  }

  const checkboxButton = getByRole('checkbox')
  if (checkboxProps.id) {
    expect(checkboxButton).toHaveAttribute('id', checkboxProps.id)
  }

  expect(checkboxButton).toHaveAttribute('checked', checkboxProps.checked ? 'true' : 'false')
  if (checkboxProps.indeterminate && !checkboxProps.checked) {
    expect(checkboxButton).toHaveAttribute('data-state', 'indeterminate')
  } else {
    expect(checkboxButton).not.toHaveAttribute('data-state', 'indeterminate')
    expect(checkboxButton).toHaveAttribute('data-state', checkboxProps.checked ? 'checked' : 'unchecked')
  }

  if (checkboxProps.disabled) {
    expect(checkboxButton).toHaveAttribute('disabled')
  } else {
    expect(checkboxButton).not.toHaveAttribute('disabled')

    await checkboxButton.click()
    expect(onChange).toHaveBeenCalledWith(checkboxProps.checked ? false : true)
    console.log(`onChange was called with ${onChange.mock.calls[0][0]}`)
  }
})