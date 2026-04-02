import { expect, test, vi } from 'vitest'
import { render } from 'vitest-browser-vue'
import { PAlert, type PAlertProps } from '@/index'
import { PButton } from '@/components/PButton'
import { alertVariants, alertVariantOptions, alertAppearanceOptions } from '@/components/PAlert'
import { cn } from '@/lib/utils'
import { generateTestId } from '@/utils/testId'

function renderAlert(props: Partial<PAlertProps> = {}, template?: string) {
  const onClose = vi.fn()
  const onAction = vi.fn()
  const testProps = { ...props } as PAlertProps

  const screen = render({
    components: { PAlert, PButton },
    template: template ?? `<PAlert v-bind="testProps" @close="onClose" @action="onAction" />`,
    setup: () => ({ testProps, onClose, onAction }),
  })

  const alert = screen.getByTestId(generateTestId('PAlert'))


  return { ...screen, alert, onClose, onAction }
}

test('renders with default props', () => {
  const { alert } = renderAlert()

  expect(alert).toBeInTheDocument()
  const expectedClasses = cn(alertVariants({ variant: 'default', appearance: 'contained', size: 'medium' }))
  expect(alert).toHaveClass(expectedClasses)
})

test('renders title and description', () => {
  const { getByText } = renderAlert({
    title: 'Heads up',
    description: 'Something happened.',
  })

  expect(getByText('Heads up')).toBeInTheDocument()
  expect(getByText('Something happened.')).toBeInTheDocument()
})

test('renders description without title', () => {
  const { alert, getByText } = renderAlert({
    description: 'Standalone message.',
  })

  expect(alert).toBeInTheDocument()
  expect(getByText('Standalone message.')).toBeInTheDocument()
})

test('renders default icon based on variant', () => {
  const { getByTestId } = renderAlert({ variant: 'error' })

  expect(getByTestId(generateTestId('PIcon', 'warning-filled'))).toBeInTheDocument()
})

test('renders custom icon', () => {
  const { getByTestId } = renderAlert({ icon: 'checkmark-filled' })

  expect(getByTestId(generateTestId('PIcon', 'checkmark-filled'))).toBeInTheDocument()
})

test('hideIcon hides the icon', () => {
  const { alert } = renderAlert({ hideIcon: true, variant: 'error' })

  expect(alert).toBeInTheDocument()
  expect(document.querySelector(`[data-testid="${generateTestId('PIcon', 'warning-filled')}"]`)).toBeNull()
})

test('close button emits close event', async () => {
  const { alert, onClose } = renderAlert({ hideCloseButton: false })

  const closeBtn = alert.getByTestId(generateTestId('PButton'))
  await closeBtn.click()
  expect(onClose).toHaveBeenCalledWith(expect.any(MouseEvent))
})

test('hideCloseButton hides the close button', () => {
  const { alert } = renderAlert({ hideCloseButton: true })

  expect(alert.getByTestId(generateTestId('PButton'))).not.toBeInTheDocument()
})

test('action button renders and emits action event', async () => {
  const { getByText, onAction } = renderAlert({
    actionButtonText: 'Retry',
  })

  const actionBtn = getByText('Retry')
  expect(actionBtn).toBeInTheDocument()
  await actionBtn.click()
  expect(onAction).toHaveBeenCalledWith(expect.any(MouseEvent))
})

test('applies custom class', () => {
  const { alert } = renderAlert({ class: 'my-custom-class' })

  expect(alert).toHaveClass('my-custom-class')
})

test.each(
  alertVariantOptions.flatMap(variant => alertAppearanceOptions.map(appearance => ({ variant, appearance })))
)(
  'renders variant "$variant" with appearance "$appearance"', ({ variant, appearance }) => {
  const { alert } = renderAlert({ variant, appearance })

  const expectedClasses = cn(alertVariants({ variant, appearance, size: 'medium' }))
  expect(alert).toHaveClass(expectedClasses)
})

test.each([
  { size: 'small' as const },
  { size: 'medium' as const },
  { size: 'large' as const },
])('renders with size "$size"', ({ size }) => {
  const { alert } = renderAlert({ size, title: 'Title', description: 'Desc' })

  const expectedClasses = cn(alertVariants({ variant: 'default', appearance: 'contained', size }))
  expect(alert).toHaveClass(expectedClasses)
})
