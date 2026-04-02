import { expect, test, vi } from 'vitest'
import { render } from 'vitest-browser-vue'
import { PCheckboxGroup, type PCheckboxGroupProps } from '@/index'
import type { Size } from '@/types/size'
import { generateTestId } from '@/utils/testId'

let checkboxes = [{ label: 'Checkbox 1', checked: true }, { label: 'Checkbox 2', checked: false }, { label: 'Checkbox 3', checked: false }]

test.each([
  { label: 'Checkbox group label', checkboxes: checkboxes.map(checkbox => ({ ...checkbox, checked: true })), size: 'small' },
  { checkboxes: checkboxes.map(checkbox => ({ ...checkbox, checked: true })), size: 'medium' },
  { checkboxes: checkboxes.map(checkbox => ({ ...checkbox, checked: false })), size: 'large' },
  { checkboxes: checkboxes, disabled: true },
  { label: 'Checkbox group label', checkboxes: checkboxes, required: true },
  { label: 'Checkbox group label', checkboxes: checkboxes, error: true, errorText: 'Error text' },
  { label: 'Checkbox group label', checkboxes: checkboxes, helperText: 'Helper text' },
  { label: 'Checkbox group label', checkboxes: checkboxes, class: 'test-class' },
  { label: 'Checkbox group label', checkboxes: checkboxes, orientation: 'horizontal' },
  { label: 'Checkbox group label', checkboxes: checkboxes, orientation: 'vertical' },
])('PCheckboxGroup with props: %o', async (propsToTest) => {
  const onChange = vi.fn()
  const checkboxGroupProps: PCheckboxGroupProps = {
    ...propsToTest,
    size: propsToTest.size as Size,
    onChange,
    orientation: propsToTest.orientation as 'horizontal' | 'vertical',
  }
  const { getByTestId, getByRole, getByText } = render(PCheckboxGroup, {
    props: checkboxGroupProps,
  })

  const checkboxGroup = getByTestId('checkbox-group')
  expect(checkboxGroup).toBeInTheDocument()

  if (propsToTest.label && propsToTest.required) {
    expect(getByText(propsToTest.label)).toBeInTheDocument()
    expect(getByText('*')).toBeInTheDocument()
  } else if (propsToTest.label) {
    expect(getByText(propsToTest.label)).toBeInTheDocument()
  }

  if (propsToTest.errorText && propsToTest.error) {
    expect(getByText(propsToTest.errorText)).toBeInTheDocument()
  } else if (propsToTest.helperText) {
    expect(getByText(propsToTest.helperText)).toBeInTheDocument()
  }

  if (propsToTest.class) {
    expect(checkboxGroup).toHaveClass(propsToTest.class)
  }

  if (propsToTest.orientation) {
    expect(checkboxGroup).toHaveClass(propsToTest.orientation === 'horizontal' ? 'flex flex-row' : 'flex flex-col')
  }

  if (propsToTest.size) {
    for (const checkbox of propsToTest.checkboxes) {
      expect(checkboxGroup.getByTestId(generateTestId('PCheckbox', checkbox.label))).toHaveClass(propsToTest.size === 'small' ? 'py-1' : propsToTest.size === 'medium' ? 'py-2' : 'py-3')
    }
  }

  const checkboxes = getByRole('checkbox')
  expect(checkboxes).toHaveLength(propsToTest.checkboxes.length)
  for (let index = 0; index < propsToTest.checkboxes.length; index++) {
    const checkboxProps = propsToTest.checkboxes[index]
    const checkboxTestId = generateTestId('PCheckbox', checkboxProps.label)
    const checkboxElement = getByTestId(checkboxTestId)
    expect(checkboxElement).toBeInTheDocument()

    const checkboxButton = checkboxes.nth(index)
    expect(checkboxButton).toHaveAttribute('data-state', checkboxProps.checked ? 'checked' : 'unchecked')

    if (propsToTest.disabled) {
      expect(checkboxButton).toHaveAttribute('disabled')
    } else {
      expect(checkboxButton).not.toHaveAttribute('disabled')

      await checkboxButton.click()
      expect(onChange).toHaveBeenCalledTimes(index + 1)
      expect(onChange).toHaveBeenCalledWith(expect.arrayContaining([
        expect.objectContaining({
          label: checkboxProps.label,
          checked: !checkboxProps.checked,
        }),
      ]))
    }
  }

  if (!propsToTest.disabled) {
    // Make sure onChange was called for each checkbox and that all checkboxes flipped their state
    expect(onChange).toHaveBeenCalledTimes(propsToTest.checkboxes.length)
    expect(onChange).toHaveBeenCalledWith(expect.arrayContaining(propsToTest.checkboxes.map((checkbox) => ({
      label: checkbox.label,
      checked: !checkbox.checked,
    }))))
  }
})

test('modelValue updates when checkboxes are clicked', async () => {
  const onUpdateModelValue = vi.fn()

  const { getByRole } = render({
    components: { PCheckboxGroup },
    template: `<PCheckboxGroup :checkboxes="checkboxes" :modelValue="[]" @update:modelValue="onUpdateModelValue" />`,
    setup: () => ({
      checkboxes: [
        { label: 'Checkbox 1', checked: false },
        { label: 'Checkbox 2', checked: false },
        { label: 'Checkbox 3', checked: false },
      ],
      onUpdateModelValue,
    }),
  })

  const checkboxButtons = getByRole('checkbox')
  await checkboxButtons.nth(0).click()

  await expect.poll(() => onUpdateModelValue).toHaveBeenCalledWith(
    expect.arrayContaining(['Checkbox 1'])
  )
})