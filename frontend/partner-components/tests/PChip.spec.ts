import { expect, test, vi } from 'vitest'
import { render } from 'vitest-browser-vue'
import { PChip, type PChipProps } from '@/index'
import { generateTestId } from '@/utils/testId'

test.each([
  { variant: 'primary', appearance: 'contained', size: 'medium', iconPosition: 'right', icon: undefined, disabled: false },
  { variant: 'secondary', appearance: 'outlined', size: 'small', iconPosition: 'left', icon: 'edit', selectable: true, selected: false, disabled: true},
  { variant: 'secondary', appearance: 'outlined', size: 'small', iconPosition: 'left', icon: 'edit', selectable: true, selected: true, disabled: true},
  { variant: 'secondary', appearance: 'outlined', size: 'small', selectable: true, selected: true, disabled: false},
  { variant: 'warning', appearance: 'contained', size: 'large', removable: true },
  { variant: 'warning', appearance: 'contained', size: 'large', removable: true, removed: false},
  { variant: 'warning', appearance: 'contained', size: 'large', removable: true, removed: true},
  { variant: 'warning', appearance: 'contained', size: 'large', removable: true, removed: true, disabled: true},
  { variant: 'warning', appearance: 'contained', size: 'large', removable: true, removed: false, disabled: true},
])('PChip with props: %o', async (propsToTest) => {
  const testProps = propsToTest as PChipProps
  const onRemove = vi.fn()
  const onSelect = vi.fn()
  const { getByTestId } = render(PChip, {
    slots: { default: 'Chip' },
    props: { ...testProps },
    attrs: { onRemove, onSelect },
  })
  const testId = generateTestId('PChip')
  const chip = getByTestId(testId)
  expect(chip).toBeInTheDocument()

  if (testProps.selectable) {
    await chip.click({ force: true, timeout: 1000 })
    expect(onRemove).not.toHaveBeenCalled()
    if (!testProps.disabled) {
      expect(onSelect).toHaveBeenCalledTimes(1)
      const expectedSelected = !testProps.selected
      expect(onSelect).toHaveBeenCalledWith(expectedSelected)
      expect(chip).toHaveAttribute('data-selected', expectedSelected ? 'true' : 'false')
    } else {
      expect(onSelect).not.toHaveBeenCalled()
      if (testProps.selected !== undefined) {
        expect(chip).toHaveAttribute('data-selected', testProps.selected ? 'true' : 'false')
      } else {
        expect(chip).not.toHaveAttribute('data-selected')
      }
    }
  }

  if (testProps.removable) {
    const icon = getByTestId('picon-close')
    expect(icon).toBeInTheDocument()

    if (!testProps.removed) {
      await icon.click({ force: true, timeout: 1000 })
      expect(onSelect).not.toHaveBeenCalled()
      if (!testProps.disabled) {
        expect(onRemove).toHaveBeenCalledTimes(1)
        expect(onRemove).toHaveBeenCalled()
        expect(chip).toHaveClass('hidden')
        expect(chip).toHaveAttribute('data-removed', 'true')
      } else {
        expect(onRemove).not.toHaveBeenCalled()
        expect(chip).not.toHaveClass('hidden')
        if (testProps.removed !== undefined) {
          expect(chip).toHaveAttribute('data-removed', testProps.removed ? 'true' : 'false')
        } else {
          expect(chip).not.toHaveAttribute('data-removed')
        }
      }
    } else if (testProps.removed) {
      expect(icon).not.toBeVisible()
      expect(chip).not.toBeVisible()
      expect(chip).toHaveClass('hidden')
      expect(chip).toHaveAttribute('data-removed', 'true')
    }
  }
})