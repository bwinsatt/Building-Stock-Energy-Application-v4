import { expect, test, vi } from 'vitest'
import { render } from 'vitest-browser-vue'
import { PAvatarGroup, type PAvatarGroupProps, type PAvatarProps } from '@/index'
import { generateTestId } from '@/utils/testId'

const onClick = vi.fn()

const threeAvatars = [
  { name: 'Alice Doe', onClick },
  { name: 'Bob Smith' },
  { name: 'Charlie Davis' },
] as any as PAvatarProps[]

const fiveAvatars = [
  { name: 'Alice Doe', onClick },
  { name: 'Bob Smith' },
  { name: 'Charlie Davis', onClick },
  { name: 'Diana Johnson' },
  { name: 'Eve Wilson' },
] as any as PAvatarProps[]

test.each([
  { avatars: threeAvatars, maxVisible: 3 },
  { avatars: threeAvatars, maxVisible: 2 },
  { avatars: fiveAvatars, maxVisible: 2 },
  { avatars: fiveAvatars, maxVisible: 4 },
  { avatars: fiveAvatars, maxVisible: 10 },
  { avatars: threeAvatars, maxVisible: 3, spacing: 'compact' },
  { avatars: threeAvatars, maxVisible: 3, spacing: 'none' },
])('PAvatarGroup with props: %o', async (propsToTest) => {
  const testProps = propsToTest as PAvatarGroupProps
  onClick.mockClear()

  const { getByText, getByTestId } = render({
    components: { PAvatarGroup },
    template: `<PAvatarGroup v-bind="testProps" />`,
    setup() {
      return { testProps }
    },
  })

  // Group container should be in the DOM
  const group = getByTestId(generateTestId('PAvatarGroup'))
  expect(group).toBeInTheDocument()

  // maxVisible is clamped to [0, 4]
  const effectiveMaxVisible = Math.min(Math.abs(testProps.maxVisible ?? 2), 4)
  const visibleCount = Math.min(testProps.avatars.length, effectiveMaxVisible)
  const overflowCount = testProps.avatars.length - visibleCount

  // --- Visible avatars ---
  for (let i = 0; i < visibleCount; i++) {
    const avatar = getByTestId(generateTestId('PAvatar', testProps.avatars[i].name))
    expect(avatar).toBeInTheDocument()
  }

  // --- Hidden avatars should not render ---
  for (let i = visibleCount; i < testProps.avatars.length; i++) {
    const hidden = document.querySelector(`[data-testid="${generateTestId('PAvatar', testProps.avatars[i].name)}"]`)
    expect(hidden).toBeNull()
  }

  // --- Overflow indicator ---
  if (overflowCount > 0) {
    const overflowText = `+${overflowCount}`
    const overflow = getByText(overflowText, { exact: true })
    expect(overflow).toBeInTheDocument()
  }

  // --- Click event on first and third avatars (onClick passed via avatar data) ---
  const firstAvatar = getByTestId(generateTestId('PAvatar', testProps.avatars[0].name))
  await firstAvatar.click()
  expect(onClick).toHaveBeenCalled()
  expect(onClick).toHaveBeenCalledWith(expect.any(MouseEvent))

  if (testProps.avatars === fiveAvatars && visibleCount > 2) {
    const thirdAvatar = getByTestId(generateTestId('PAvatar', testProps.avatars[2].name))
    await thirdAvatar.click()
    expect(onClick).toHaveBeenCalled()
    expect(onClick).toHaveBeenCalledWith(expect.any(MouseEvent))
  }

  // --- Spacing class ---
  const spacingMap: Record<string, string> = {
    none: '',
    default: '-space-x-1',
    compact: '-space-x-2',
  }
  const expectedSpacing = spacingMap[testProps.spacing ?? 'default']
  if (expectedSpacing) {
    expect(group).toHaveClass(expectedSpacing)
  }
})
