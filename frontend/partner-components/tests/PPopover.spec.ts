import { expect, test, vi } from 'vitest'
import { render } from 'vitest-browser-vue'
import { PPopover, PButton, PTypography, type PPopoverProps } from '@/index'
import { generateTestId } from '@/utils/testId'

const popoverTemplate = `
  <PPopover v-bind="testProps" @update:open="onUpdateOpen">
    <template #trigger>
      <PButton name="trigger" variant="primary" appearance="contained">Open</PButton>
    </template>
    <template #content>
      <PTypography variant="body1">Popover content</PTypography>
    </template>
  </PPopover>
`

test.each([
  { defaultOpen: false, openDuration: 0, closeDuration: 0 },
  { defaultOpen: true, openDuration: 0, closeDuration: 0 },
  { defaultOpen: true, showClose: true, openDuration: 0, closeDuration: 0 },
  { defaultOpen: true, showArrow: true, openDuration: 0, closeDuration: 0 },
  { defaultOpen: true, showClose: true, showArrow: true, openDuration: 0, closeDuration: 0 },
  { defaultOpen: true, openDuration: 100, closeDuration: 100 },
])('PPopover with props: %o', async (propsToTest) => {
  const testProps = propsToTest as PPopoverProps
  const onUpdateOpen = vi.fn()
  const openDuration = testProps.openDuration ?? 400
  const closeDuration = testProps.closeDuration ?? 100

  const { getByTestId } = render({
    components: { PPopover, PButton, PTypography },
    template: popoverTemplate,
    setup() {
      return { testProps, onUpdateOpen }
    },
  })

  // --- Trigger renders ---
  const trigger = getByTestId(generateTestId('PButton', 'trigger'))
  expect(trigger).toBeInTheDocument()

  const popover = getByTestId(generateTestId('PPopover'))
  if (testProps.defaultOpen || testProps.open) {
    await expect.poll(() => popover, { timeout: openDuration }).toBeVisible()

    // --- Content renders ---
    const content = popover.getByTestId(generateTestId('PTypography'))
    expect(content).toBeInTheDocument()
    expect(content).toHaveTextContent('Popover content')
  } else {
    expect(popover).not.toBeInTheDocument()
  }

  // --- Close button closes popover ---
  const closeButton = getByTestId(generateTestId('PButton', 'close'))
  if (testProps.showClose) {
    // Open popover first if it's not already open
    if (!testProps.defaultOpen && !testProps.open) {
      expect(closeButton).not.toBeInTheDocument()
      await trigger.click()
      expect(closeButton).toBeInTheDocument()
    }
    // Close popover with close button
    await closeButton.click()
    expect(onUpdateOpen).toHaveBeenCalledWith(false)
    await expect.poll(() => popover, { timeout: closeDuration }).not.toBeInTheDocument()
    // Return to initial state
    await trigger.click()
  } else {
    expect(closeButton).not.toBeInTheDocument()
  }

  // --- Trigger opens popover ---
  if (!testProps.defaultOpen && !testProps.open) {
    await trigger.click()
    expect(onUpdateOpen).toHaveBeenCalledWith(true)
    await expect.poll(() => popover, { timeout: openDuration }).toBeVisible()
  }

  // --- Trigger closes popover when already open ---
  if (testProps.defaultOpen) {
    await trigger.click()
    expect(onUpdateOpen).toHaveBeenCalledWith(false)
  }
})
