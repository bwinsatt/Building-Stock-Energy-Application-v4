import { expect, test } from 'vitest'
import { render } from 'vitest-browser-vue'
import { PBadge, type PBadgeProps } from '@/index'
import { badgeVariants } from '@/components/PBadge'
import { cn } from '@/lib/utils'
import { generateTestId } from '@/utils/testId'

test.each([
  { variant: 'primary', appearance: 'standard' },
  { variant: 'secondary', appearance: 'standard' },
  { variant: 'error', appearance: 'standard' },
  { variant: 'warning', appearance: 'standard' },
  { variant: 'success', appearance: 'standard' },
  { variant: 'neutral', appearance: 'standard' },
  { variant: 'primary', appearance: 'dot' },
  { variant: 'error', appearance: 'dot' },
  { variant: 'primary', appearance: 'standard', class: 'test-class' },
])('PBadge with props: %o', async (propsToTest) => {
  const testProps = propsToTest as PBadgeProps
  const badgeText = 'Badge'

  const { getByTestId } = render(PBadge, {
    slots: { default: badgeText },
    props: testProps,
  })

  // Badge should be in the DOM
  const badge = getByTestId(generateTestId('PBadge'))
  expect(badge).toBeInTheDocument()

  // --- Classes ---
  const expectedClasses = cn(
    badgeVariants({ variant: testProps.variant, appearance: testProps.appearance }),
    testProps.class,
  )
  expect(badge).toHaveClass(expectedClasses)

  // --- Content ---
  if (testProps.appearance === 'dot') {
    expect(badge).not.toHaveTextContent(badgeText)
  } else {
    expect(badge).toHaveTextContent(badgeText)
  }
})