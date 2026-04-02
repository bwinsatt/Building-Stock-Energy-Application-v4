import { expect, test, vi } from 'vitest'
import { render } from 'vitest-browser-vue'
import { PSwitch, type PSwitchProps } from '@/components/PSwitch'
import { generateTestId } from '@/utils/testId'

function renderSwitch(props: Partial<PSwitchProps> = {}) {
  const onUpdateModelValue = vi.fn()
  const testProps = { ...props } as PSwitchProps

  const screen = render({
    components: { PSwitch },
    template: `<PSwitch v-bind="testProps" @update:modelValue="onUpdateModelValue" />`,
    setup: () => ({ testProps, onUpdateModelValue }),
  })

  const wrapper = screen.getByTestId(generateTestId('PSwitch'))
  const switchControl = wrapper.getByRole('switch')

  return { ...screen, wrapper, switchControl, onUpdateModelValue }
}

test('renders with default props', () => {
  const { wrapper, switchControl } = renderSwitch()

  expect(wrapper).toBeInTheDocument()
  expect(switchControl.element()).toBeTruthy()
  expect(switchControl).toHaveAttribute('data-state', 'unchecked')
})

test('renders with label', () => {
  const { getByText } = renderSwitch({ label: 'Toggle me' })

  expect(getByText('Toggle me')).toBeInTheDocument()
})

test('pre-selects when modelValue is true', async () => {
  const { switchControl } = renderSwitch({ modelValue: true })

  await expect.element(switchControl).toHaveAttribute('data-state', 'checked')
})

test('clicking emits update:modelValue', async () => {
  const { switchControl, onUpdateModelValue } = renderSwitch({ modelValue: false })

  await switchControl.click()
  await expect.poll(() => onUpdateModelValue).toHaveBeenCalledWith(true)
})

test('disabled prevents interaction', async () => {
  const { switchControl, onUpdateModelValue } = renderSwitch({
    modelValue: false,
    disabled: true,
  })

  await expect.element(switchControl).toHaveAttribute('disabled')
  await switchControl.click({ force: true })
  expect(onUpdateModelValue).not.toHaveBeenCalled()
})

test('passes id to the switch element', () => {
  const { switchControl } = renderSwitch({ id: 'my-switch' })

  expect(switchControl).toHaveAttribute('id', 'my-switch')
})

test('applies custom class to wrapper', () => {
  const { wrapper } = renderSwitch({ class: 'custom-class' })

  expect(wrapper).toHaveClass('custom-class')
})

test.each([
  { size: 'small' as const },
  { size: 'medium' as const },
  { size: 'large' as const },
])('renders with size "$size"', ({ size }) => {
  const { switchControl } = renderSwitch({ size })

  expect(switchControl.element()).toBeTruthy()
})
