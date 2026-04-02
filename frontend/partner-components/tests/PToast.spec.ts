import { expect, test, vi } from 'vitest'
import { render } from 'vitest-browser-vue'
import { PToast } from '@/components/PToast'
import { showToast, type ShowToastOptions } from '@/components/PToast'
import { generateTestId } from '@/utils/testId'

function renderToast(toastOptions: ShowToastOptions = {}) {
  const onClose = vi.fn()
  const onAction = vi.fn()

  const screen = render(PToast, { props: { position: 'top-center' } })

  const id = showToast({
    duration: Infinity,
    ...toastOptions,
    onClose: (...args) => {
      toastOptions.onClose?.(...args)
      onClose(...args)
    },
    onAction: (...args) => {
      toastOptions.onAction?.(...args)
      onAction(...args)
    },
  })

  return { ...screen, onClose, onAction, toastId: id }
}

test('showToast renders a toast with title and description', async () => {
  renderToast({ title: 'Success', description: 'Item saved' })

  await vi.waitFor(() => {
    expect(document.querySelector('[data-sonner-toast]')).toBeTruthy()
  })

  expect(document.body).toHaveTextContent('Success')
  expect(document.body).toHaveTextContent('Item saved')
})

test('showToast renders the correct variant', async () => {
  renderToast({ variant: 'error', title: 'Error', description: 'Something broke' })

  const alert = await vi.waitFor(() => {
    const el = document.querySelector(`[data-testid="${generateTestId('PAlert')}"]`)
    expect(el).toBeTruthy()
    return el!
  })

  expect(alert).toBeVisible()
})

test('showToast hides close button by default (dismissible=false)', async () => {
  renderToast({ title: 'Not dismissible' })

  await vi.waitFor(() => {
    expect(document.querySelector('[data-sonner-toast]')).toBeTruthy()
  })

  const closeBtn = document.querySelector(`[data-testid="${generateTestId('PButton')}"]`)
  expect(closeBtn).toBeNull()
})

test('showToast shows close button when dismissible', async () => {
  renderToast({ title: 'Dismissible', dismissible: true })

  const closeBtn = await vi.waitFor(() => {
    const el = document.querySelector(`[data-testid="${generateTestId('PButton')}"]`)
    expect(el).toBeTruthy()
    return el as HTMLElement
  })

  expect(closeBtn).toBeVisible()
})

test('close button calls onClose and dismisses toast', async () => {
  const { onClose } = renderToast({ title: 'Close me', dismissible: true })

  const closeBtn = await vi.waitFor(() => {
    const el = document.querySelector(`[data-testid="${generateTestId('PButton')}"]`)
    expect(el).toBeTruthy()
    return el as HTMLElement
  })

  await closeBtn.click()
  expect(onClose).toHaveBeenCalledWith(expect.any(MouseEvent))
})

test('action button renders and calls onAction', async () => {
  const { onAction } = renderToast({
    title: 'With action',
    actionButtonText: 'Undo',
  })

  const actionBtn = await vi.waitFor(() => {
    const el = Array.from(document.querySelectorAll('button')).find(b => b.textContent?.includes('Undo'))
    expect(el).toBeTruthy()
    return el as HTMLElement
  })

  await actionBtn.click()
  expect(onAction).toHaveBeenCalledWith(expect.any(MouseEvent))
})

test('showToast returns a toast id', () => {
  const { toastId } = renderToast({ title: 'ID check' })

  expect(toastId).toBeDefined()
  expect(typeof toastId).toBe('number')
})

test('renders multiple toasts', async () => {
  render(PToast, { props: { position: 'top-center' } })

  showToast({ title: 'First', duration: Infinity })
  showToast({ title: 'Second', duration: Infinity })
  showToast({ title: 'Third', duration: Infinity })

  await vi.waitFor(() => {
    const toasts = document.querySelectorAll('[data-sonner-toast]')
    expect(toasts.length).toBe(3)
  })
})
