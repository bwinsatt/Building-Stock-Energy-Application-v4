import { expect, test, vi } from 'vitest'
import { render } from 'vitest-browser-vue'
import { userEvent } from 'vitest/browser'
import { PDialog, PDialogClose, PButton, type PDialogProps } from '@/index'
import { generateTestId } from '@/utils/testId'

const dialogTemplate = `
  <PDialog v-bind="testProps" @update:open="onUpdateOpen">
    <template #trigger>
      <PButton name="open-dialog" variant="primary" appearance="contained">Open</PButton>
    </template>
    <template #content>
      <span data-testid="dialog-content">Dialog body</span>
    </template>
    <template #footer>
      <div class="flex gap-2 justify-end">
        <PDialogClose>
          <PButton name="cancel" variant="primary" appearance="outlined">Cancel</PButton>
        </PDialogClose>
        <PButton name="submit" variant="primary" appearance="contained">Submit</PButton>
      </div>
    </template>
  </PDialog>
`

function renderDialog(props: Partial<PDialogProps> = {}) {
  const onUpdateOpen = vi.fn()
  const testProps = { ...props } as PDialogProps

  const screen = render({
    components: { PDialog, PDialogClose, PButton },
    template: dialogTemplate,
    setup: () => ({ testProps, onUpdateOpen }),
  })

  const trigger = screen.getByTestId(generateTestId('PButton', 'open-dialog'))

  return { ...screen, trigger, onUpdateOpen }
}

test('renders trigger button', () => {
  const { trigger } = renderDialog()

  expect(trigger).toBeInTheDocument()
  expect(trigger).toHaveTextContent('Open')
})

test('dialog is hidden by default', () => {
  const { getByTestId } = renderDialog()

  expect(getByTestId('dialog-content')).not.toBeInTheDocument()
})

test('opens when defaultOpen is true', async () => {
  const { getByTestId } = renderDialog({ defaultOpen: true })

  await expect.element(getByTestId('dialog-content')).toBeVisible()
})

test('displays title and description', async () => {
  const { getByText } = renderDialog({
    defaultOpen: true,
    title: 'Confirm Action',
    description: 'Are you sure?',
  })

  await expect.element(getByText('Confirm Action')).toBeVisible()
  await expect.element(getByText('Are you sure?')).toBeVisible()
})

test('renders content slot', async () => {
  const { getByTestId } = renderDialog({ defaultOpen: true })

  const content = getByTestId('dialog-content')
  await expect.element(content).toBeVisible()
  expect(content).toHaveTextContent('Dialog body')
})

test('renders footer slot', async () => {
  const { getByTestId } = renderDialog({ defaultOpen: true })

  const cancelBtn = getByTestId(generateTestId('PButton', 'cancel'))
  const submitBtn = getByTestId(generateTestId('PButton', 'submit'))
  await expect.element(cancelBtn).toBeVisible()
  await expect.element(submitBtn).toBeVisible()
})

test('clicking trigger opens the dialog', async () => {
  const { trigger, getByTestId, onUpdateOpen } = renderDialog()

  await trigger.click()
  await expect.poll(() => onUpdateOpen).toHaveBeenCalledWith(true)
  await expect.element(getByTestId('dialog-content')).toBeVisible()
})

test('built-in close button closes the dialog', async () => {
  const { getByTestId, onUpdateOpen } = renderDialog({ defaultOpen: true })

  await expect.element(getByTestId('dialog-content')).toBeVisible()

  const closeBtn = getByTestId(generateTestId('PButton', 'close-large'))
  await closeBtn.click()
  await expect.poll(() => onUpdateOpen).toHaveBeenCalledWith(false)
  await expect.poll(() => getByTestId('dialog-content')).not.toBeInTheDocument()
})

test('PDialogClose wrapping a button closes the dialog', async () => {
  const { getByTestId, onUpdateOpen } = renderDialog({ defaultOpen: true })

  await expect.element(getByTestId('dialog-content')).toBeVisible()

  const cancelBtn = getByTestId(generateTestId('PButton', 'cancel'))
  await cancelBtn.click()
  await expect.poll(() => onUpdateOpen).toHaveBeenCalledWith(false)
  await expect.poll(() => getByTestId('dialog-content')).not.toBeInTheDocument()
})

test('hideCloseButton hides the built-in close button', async () => {
  const { getByTestId } = renderDialog({
    defaultOpen: true,
    hideCloseButton: true,
  })

  await expect.element(getByTestId('dialog-content')).toBeVisible()
  expect(getByTestId(generateTestId('PButton', 'close-large'))).not.toBeInTheDocument()
})

test('disableCloseOnEscape prevents closing with Escape key', async () => {
  const { getByTestId, onUpdateOpen } = renderDialog({
    defaultOpen: true,
    disableCloseOnEscape: true,
  })

  await expect.element(getByTestId('dialog-content')).toBeVisible()

  await userEvent.keyboard('{Escape}')
  expect(onUpdateOpen).not.toHaveBeenCalled()
  await expect.element(getByTestId('dialog-content')).toBeVisible()
})

test('disableCloseOnInteractOutside prevents closing by clicking overlay', async () => {
  const { getByTestId, onUpdateOpen } = renderDialog({
    defaultOpen: true,
    disableCloseOnInteractOutside: true,
  })

  await expect.element(getByTestId('dialog-content')).toBeVisible()

  const overlay = document.querySelector('[aria-hidden="true"][data-state="open"]') as HTMLElement
  overlay.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, cancelable: true }))
  await expect.poll(() => onUpdateOpen, { timeout: 100 }).not.toHaveBeenCalled()
  await expect.element(getByTestId('dialog-content')).toBeVisible()
})
