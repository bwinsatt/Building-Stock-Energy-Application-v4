import { expect, test, vi } from 'vitest'
import { render } from 'vitest-browser-vue'
import { PAvatar, type PAvatarProps } from '@/index'
import { generateTestId } from '@/utils/testId'
import { getInitials } from '@/utils/strings'
import avatarExamplePhoto from '@/assets/images/avatar_example_photo.jpg'

test.each([
  { size: 'small', shape: 'circle', name: 'Jane Doe' },
  { size: 'medium', shape: 'square', name: 'John' },
  { size: 'large', shape: 'circle', name: 'Mary Jane Watson' },
  { size: 'xlarge', shape: 'circle', initials: 'AB', name: 'Different' },
  { size: 'medium', shape: 'circle' },
  { size: 'medium', shape: 'circle', name: 'Jane', badge: 'online' },
  { size: 'large', shape: 'square', name: 'Test User', badge: 'error', badgePosition: 'top-left' },
  { size: 'medium', shape: 'circle', image: avatarExamplePhoto, name: 'Jane Doe' },
  { size: 'large', shape: 'square', image: avatarExamplePhoto },
  { size: 'medium', shape: 'circle', image: avatarExamplePhoto, badge: 'online' },
])('PAvatar with props: %o', async (propsToTest) => {
  const testProps = propsToTest as PAvatarProps
  const onClick = vi.fn()

  const { getByText, getByTestId } = render({
    components: { PAvatar },
    template: `<PAvatar v-bind="testProps" @click="onClick" />`,
    setup() {
      return { testProps, onClick }
    },
  })

  const avatar = getByTestId(generateTestId('PAvatar', testProps.name))
  expect(avatar).toBeInTheDocument()

  // --- Image ---
  if (testProps.image) {
    await expect.poll(() => avatar.element().style.backgroundImage, { timeout: 1000 }).toContain(propsToTest.image)

    // Image hides the default slot — no initials or icon should render
    expect(document.querySelector(`[data-testid="${generateTestId('PIcon', 'user-filled')}"]`)).toBeNull()
  }

  const expectedInitials = testProps.initials ?? getInitials(testProps.name ?? '')

  // --- Initials / Icon fallback ---
  if (!testProps.image) {
    if (expectedInitials) {
      const initialsEl = getByText(expectedInitials, { exact: true })
      expect(initialsEl).toBeInTheDocument()
    } else {
      const icon = getByTestId(generateTestId('PIcon', 'user-filled'))
      expect(icon).toBeInTheDocument()
    }
  }

  // --- Badge ---
  if (testProps.badge) {
    const badge = getByTestId(generateTestId('PBadge'))
    expect(badge).toBeInTheDocument()
  }

  // --- Click event ---
  await avatar.click()
  expect(onClick).toHaveBeenCalled()
  expect(onClick).toHaveBeenCalledWith(expect.any(MouseEvent))
})
