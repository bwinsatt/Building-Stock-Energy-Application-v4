import { expect, test, vi } from 'vitest'
import { render } from 'vitest-browser-vue'
import { PButton, type PButtonProps } from '@/index'
import { buttonVariants } from '@/components/PButton'
import { cn } from '@/lib/utils'
import { generateTestId } from '@/utils/testId'

test.each([
  { variant: 'primary', appearance: 'contained', size: 'medium', iconButton: false, class: 'test-class', disabled: false },
  { variant: 'secondary', appearance: 'outlined', size: 'small', iconButton: true, icon: 'edit', class: 'test-class' },
  { variant: 'error', appearance: 'text', size: 'large', iconButton: false, class: 'test-class' },
  { variant: 'warning', appearance: 'link', size: 'medium', iconButton: true, icon: 'edit', class: 'test-class' },
  { variant: 'success', appearance: 'contained', size: 'small', iconButton: false, class: 'test-class' },
  { variant: 'neutral', appearance: 'outlined', size: 'large', iconButton: true, icon: 'edit', class: 'test-class' },
  { variant: 'neutral', appearance: 'outlined', size: 'large', iconButton: false, class: 'test-class', disabled: true, icon: 'edit' },
])('PButton with props: %o', async (propsToTest) => {
  const buttonProps = propsToTest as PButtonProps
  const onClick = vi.fn()
  const buttonText = 'Button'
  const { getByTestId } = render(PButton, {
    slots: { default: buttonText },
    props: buttonProps,
    attrs: { onClick },
  })
  
  const testId = generateTestId('PButton')
  const button = getByTestId(testId)

  // Assert that the button is in the document and has the correct text
  expect(button).toBeInTheDocument()
  if (buttonProps.iconButton) {
    expect(button).not.toHaveTextContent(buttonText)
  } else {
    expect(button).toHaveTextContent(buttonText)
  }

  // Assert that the button has the correct classes
  const expectedClasses = cn(buttonVariants({
    variant: buttonProps.variant,
    appearance: buttonProps.appearance,
    size: buttonProps.size,
    iconButton: buttonProps.iconButton,
  }), buttonProps.class)
  expect(button).toHaveClass(expectedClasses)
  
  // Assert that the onClick function is called when the button is clicked
  await button.click({ force: true, timeout: 1000 })
  if (!buttonProps.disabled) {
    expect(onClick).toHaveBeenCalled()
    expect(onClick).toHaveBeenCalledWith(expect.any(MouseEvent))
  } else {
    expect(onClick).not.toHaveBeenCalled()
  }
})