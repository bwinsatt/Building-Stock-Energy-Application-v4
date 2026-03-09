import { expect, test, vi } from 'vitest'
import { render } from 'vitest-browser-vue'
import { PTooltip, type PTooltipProps } from '@/index'
import { PButton } from '@/components/PButton'

test.each([
  { direction: 'bottom', delayDuration: 0 },
  { direction: 'top', delayDuration: 0 },
  { direction: 'left', delayDuration: 0 },
  { direction: 'right', delayDuration: 0 },
  { direction: 'none', delayDuration: 0 },
  { direction: 'bottom', open: true },
  { direction: 'bottom', disabled: true, delayDuration: 0 },
  { direction: 'bottom', offset: 10, delayDuration: 0 },
  { direction: 'bottom', delayDuration: 400 },
])('PTooltip with props: %o', async (propsToTest) => {
  const testProps = propsToTest as PTooltipProps
  const onUpdateOpen = vi.fn()

  // Center trigger to prevent viewport collision from flipping the tooltip side
  const { getByText, getByTestId } = render({
    components: { PTooltip, PButton },
    template: `
      <div style="display:flex;justify-content:center;align-items:center;min-height:100vh">
        <PTooltip v-bind="testProps" @update:open="onUpdateOpen">
          <template #tooltip-trigger>
            <PButton>Hover me</PButton>
          </template>
          <template #tooltip-content>
            <span data-testid="tooltip-text">Tooltip text</span>
          </template>
        </PTooltip>
      </div>
    `,
    setup() {
      return { testProps, onUpdateOpen }
    },
  })

  // Trigger should always be visible
  const trigger = getByText('Hover me')
  expect(trigger).toBeInTheDocument()

  // 'none' has no explicit side — PTooltip defaults to 'bottom'
  const expectedSide = (!testProps.direction || testProps.direction === 'none')
    ? 'bottom'
    : testProps.direction

  if (testProps.open) {
    const content = getByTestId('tooltip-text')
    await expect.element(content).toBeVisible()
    await expect.element(content).toHaveTextContent('Tooltip text')
    await expect.poll(() =>
      document.querySelector('[data-side]')?.getAttribute('data-side')
    ).toBe(expectedSide)
    return
  }

  if (testProps.disabled) {
    await trigger.hover()
    await expect.poll(() => onUpdateOpen, { timeout: 200 }).not.toHaveBeenCalled()
    return
  }

  // Hover to open tooltip
  await trigger.hover()
  const delay = testProps.delayDuration ?? 400
  await expect.poll(() => onUpdateOpen, { timeout: delay + 200 }).toHaveBeenCalledWith(true)

  const content = getByTestId('tooltip-text')
  await expect.element(content).toBeVisible()
  await expect.element(content).toHaveTextContent('Tooltip text')

  // Confirm tooltip rendered on the correct side
  await expect.poll(() =>
    document.querySelector('[data-side]')?.getAttribute('data-side')
  ).toBe(expectedSide)
})
