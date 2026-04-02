import { expect, test, vi } from 'vitest'
import { render } from 'vitest-browser-vue'
import { PRadioGroup, type PRadioGroupProps } from '@/components/PRadioGroup'
import { generateTestId } from '@/utils/testId'

const defaultOptions: PRadioGroupProps['options'] = [
  { id: 'apple', value: 'apple', label: 'Apple' },
  { id: 'banana', value: 'banana', label: 'Banana' },
  { id: 'cherry', value: 'cherry', label: 'Cherry' },
]

function renderRadioGroup(props: Partial<PRadioGroupProps> = {}) {
  const onUpdateModelValue = vi.fn()
  const testProps = { options: defaultOptions, ...props } as PRadioGroupProps

  const screen = render({
    components: { PRadioGroup },
    template: `<PRadioGroup v-bind="testProps" @update:modelValue="onUpdateModelValue" />`,
    setup: () => ({ testProps, onUpdateModelValue }),
  })

  const radioGroup = screen.getByTestId(generateTestId('PRadioGroup'))

  const radioFor = (name: string) => radioGroup.getByTestId(generateTestId('PRadioGroupItem', name)).getByRole('radio')

  return { ...screen, radioFor, onUpdateModelValue }
}

test('renders all options with labels', () => {
  const { getByText, radioFor, getByTestId } = renderRadioGroup()

  expect(radioFor('Apple').element()).toBeTruthy()
  expect(radioFor('Banana').element()).toBeTruthy()
  expect(radioFor('Cherry').element()).toBeTruthy()

  expect(getByText('Apple')).toBeInTheDocument()
  expect(getByText('Banana')).toBeInTheDocument()
  expect(getByText('Cherry')).toBeInTheDocument()
  expect(radioFor('Apple')).toHaveClass('cursor-pointer')
  expect(getByTestId(generateTestId('PRadioGroupItem', 'Apple')).getByTestId('plabel')).toHaveClass('cursor-pointer')
})

test('pre-selects the option matching "selected"', async () => {
  const { radioFor } = renderRadioGroup({ selected: 'banana' })

  await expect.poll(() => radioFor('Apple'), { timeout: 100 }).toHaveAttribute('data-state', 'unchecked')
  await expect.poll(() => radioFor('Banana'), { timeout: 100 }).toHaveAttribute('data-state', 'checked')
  await expect.poll(() => radioFor('Cherry'), { timeout: 100 }).toHaveAttribute('data-state', 'unchecked')
})

test('clicking an option emits update:modelValue', async () => {
  const { radioFor, onUpdateModelValue } = renderRadioGroup({ selected: 'apple' })

  await radioFor('Cherry').click()
  await expect.poll(() => onUpdateModelValue).toHaveBeenCalledWith('cherry')
})

test('disabled group prevents all interaction', async () => {
  const { radioFor, onUpdateModelValue, getByTestId } = renderRadioGroup({
    selected: 'apple',
    disabled: true,
  })

  await expect.element(radioFor('Apple')).toHaveAttribute('disabled')
  await expect.element(radioFor('Banana')).toHaveAttribute('disabled')
  await expect.element(radioFor('Cherry')).toHaveAttribute('disabled')
  await expect.element(radioFor('Apple')).toHaveClass('disabled:cursor-not-allowed')
  await expect.element(getByTestId(generateTestId('PRadioGroupItem', 'Apple')).getByTestId('plabel')).not.toHaveClass('cursor-pointer')

  await radioFor('Banana').click({ force: true })
  expect(onUpdateModelValue).not.toHaveBeenCalled()
})

test('individually disabled option does not emit', async () => {
  const { radioFor, onUpdateModelValue } = renderRadioGroup({
    options: [
      { value: 'apple', label: 'Apple' },
      { value: 'banana', label: 'Banana', disabled: true },
      { value: 'cherry', label: 'Cherry' },
    ],
  })

  await expect.element(radioFor('Banana')).toHaveAttribute('disabled')

  await radioFor('Banana').click({ force: true })
  expect(onUpdateModelValue).not.toHaveBeenCalled()

  await radioFor('Cherry').click()
  await expect.poll(() => onUpdateModelValue).toHaveBeenCalledWith('cherry')
})

test('renders label and required asterisk', () => {
  const { getByText } = renderRadioGroup({ label: 'Fruit', required: true })

  expect(getByText('Fruit')).toBeInTheDocument()
  expect(getByText('*')).toBeInTheDocument()
})

test('shows error text over helper text when error is true', () => {
  const { getByText, container } = renderRadioGroup({
    label: 'Fruit',
    error: true,
    errorText: 'Selection required',
    helperText: 'Pick one',
  })

  expect(getByText('Selection required')).toBeInTheDocument()
  expect(container.textContent).not.toContain('Pick one')
})

test('shows helper text when no error', () => {
  const { getByText, container } = renderRadioGroup({
    label: 'Fruit',
    helperText: 'Pick one',
    errorText: 'Selection required',
  })

  expect(getByText('Pick one')).toBeInTheDocument()
  expect(container.textContent).not.toContain('Selection required')
})

test.each([
  { size: 'small' as const },
  { size: 'medium' as const },
  { size: 'large' as const },
])('renders with size "$size"', ({ size }) => {
  const { radioFor } = renderRadioGroup({ size })

  expect(radioFor('Apple').element()).toBeTruthy()
  expect(radioFor('Banana').element()).toBeTruthy()
  expect(radioFor('Cherry').element()).toBeTruthy()
})
