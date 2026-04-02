import { expect, test, vi } from 'vitest'
import { render } from 'vitest-browser-vue'
import { PSelectMenu, type PMenuItemProps } from '@/components/PMenu'
import { PButton } from '@/components/PButton'
import { generateTestId } from '@/utils/testId'
import { userEvent } from 'vitest/browser'

const defaultItems: PMenuItemProps[] = [
  { id: 'item-1', label: 'Item 1' },
  { id: 'item-2', label: 'Item 2' },
  { id: 'item-3', label: 'Item 3' },
  { id: 'item-4', label: 'Item 4', disabled: true },
]

function renderSelectMenu(props: Record<string, unknown> = {}) {
  const onApply = vi.fn()
  const onClear = vi.fn()
  const onSelect = vi.fn()
  const onUpdateOpen = vi.fn()
  const onUpdateDebouncedSearch = vi.fn()
  const onSearch = vi.fn()
  
  const screen = render({
    components: { PSelectMenu, PButton },
    template: `
      <PSelectMenu
        v-bind="testProps"
        :items="items"
        @apply="onApply"
        @clear="onClear"
        @select="onSelect"
        @update:open="onUpdateOpen"
        @update:debouncedSearch="onUpdateDebouncedSearch"
        @search="onSearch"
      >
        <template #trigger>
          <PButton name="trigger">Open select</PButton>
        </template>
      </PSelectMenu>
    `,
    setup: () => ({
      testProps: props,
      items: (props.items as PMenuItemProps[]) ?? defaultItems,
      onApply,
      onClear,
      onSelect,
      onUpdateOpen,
      onUpdateDebouncedSearch,
      onSearch,
    }),
  })

  const trigger = screen.getByTestId(generateTestId('PButton', 'trigger'))

  return { ...screen, trigger, onApply, onClear, onSelect, onUpdateOpen, onUpdateDebouncedSearch, onSearch }
}

// --- Multi-select ---

test('multi: renders checkbox items when opened', async () => {
  const { trigger, getByRole } = renderSelectMenu({ type: 'multi' })

  await trigger.click()

  const checkboxes = getByRole('menuitemcheckbox')
  await expect.poll(() => checkboxes.all()).toHaveLength(5) // 4 items + Select All
})

test('multi: Select All toggles all non-disabled items', async () => {
  const { trigger, getByText } = renderSelectMenu({ type: 'multi' })

  await trigger.click()

  const selectAll = getByText('Select All')
  await expect.element(selectAll).toBeVisible()
  await selectAll.click()

  await expect.element(getByText('Deselect All')).toBeVisible()
})

test('multi: Apply button emits apply with selected items', async () => {
  const { trigger, getByText, onApply, onUpdateOpen } = renderSelectMenu({ type: 'multi' })

  await trigger.click()
  await expect.poll(() => onUpdateOpen).toHaveBeenCalledWith(true)

  await getByText('Item 1').click()
  await getByText('Item 2').click()

  const applyBtn = getByText('Apply')
  await expect.element(applyBtn).toBeVisible()
  await applyBtn.click()

  await expect.poll(() => onApply).toHaveBeenCalledWith(
    expect.arrayContaining([
      expect.objectContaining({ label: 'Item 1' }),
      expect.objectContaining({ label: 'Item 2' }),
    ]),
  )
})

test('multi: Clear button clears selection and emits clear', async () => {
  const items: PMenuItemProps[] = [
    { id: '1', label: 'A', modelValue: true },
    { id: '2', label: 'B', modelValue: true },
  ]

  const { trigger, getByText, onClear } = renderSelectMenu({ type: 'multi', items })

  await trigger.click()

  const clearBtn = getByText('Clear (2)')
  await expect.element(clearBtn).toBeVisible()
  await clearBtn.click()

  expect(onClear).toHaveBeenCalled()
  await expect.element(getByText('Clear')).toBeVisible()
})

test('multi: Apply button is disabled when required and nothing selected', async () => {
  const { trigger, getByRole } = renderSelectMenu({
    type: 'multi',
    required: true,
  })

  await trigger.click()

  const applyBtn = getByRole('button', { name: 'Apply' })
  await expect.element(applyBtn).toHaveAttribute('disabled')
})

test('multi: closeOnApply closes menu after apply', async () => {
  const { trigger, getByText, onApply, onUpdateOpen } = renderSelectMenu({
    type: 'multi',
    closeOnApply: true,
  })

  await trigger.click()
  await expect.poll(() => onUpdateOpen).toHaveBeenCalledWith(true)

  await getByText('Item 1').click()
  await getByText('Apply').click()

  expect(onApply).toHaveBeenCalled()
  await expect.poll(() => onUpdateOpen).toHaveBeenCalledWith(false)
})

test('multi: disabled item cannot be toggled', async () => {
  const { trigger, getByText, onApply } = renderSelectMenu({ type: 'multi' })

  await trigger.click()

  const disabledItem = getByText('Item 4')
  await expect.element(disabledItem).toBeVisible()
  await disabledItem.click({ force: true })

  await getByText('Apply').click()

  expect(onApply).toHaveBeenCalledWith([])
})

test('multi: menu stays open when checking items (preventClose)', async () => {
  const { trigger, getByText, onUpdateOpen } = renderSelectMenu({ type: 'multi' })

  await trigger.click()
  await expect.poll(() => onUpdateOpen).toHaveBeenCalledWith(true)

  await getByText('Item 1').click()

  await expect.element(getByText('Item 2')).toBeVisible()
})

// --- Single-select ---

test('single: selecting an item emits select and apply', async () => {
  const { trigger, getByText, onSelect, onApply, onUpdateOpen } = renderSelectMenu({
    type: 'single',
    hideFooter: true,
  })

  await trigger.click()
  await expect.poll(() => onUpdateOpen).toHaveBeenCalledWith(true)

  await getByText('Item 1').click()

  await expect.poll(() => onSelect).toHaveBeenCalledWith(
    expect.objectContaining({ label: 'Item 1' }),
  )
  await expect.poll(() => onApply).toHaveBeenCalledWith(
    expect.arrayContaining([expect.objectContaining({ label: 'Item 1' })]),
  )
})

test('single: shows None option when hideFooter and clearable', async () => {
  const { trigger, getByText } = renderSelectMenu({
    type: 'single',
    hideFooter: true,
    clearable: true,
  })

  await trigger.click()
  await expect.element(getByText('None')).toBeVisible()
})

test('single: None option clears selection and emits clear', async () => {
  const items: PMenuItemProps[] = [
    { id: '1', label: 'A', modelValue: true },
    { id: '2', label: 'B' },
  ]

  const { trigger, getByText, onClear } = renderSelectMenu({
    type: 'single',
    hideFooter: true,
    clearable: true,
    items,
  })

  await trigger.click()

  await getByText('None').click()
  expect(onClear).toHaveBeenCalled()
})

test('single: shows footer with Clear button when hideFooter is false', async () => {
  const { trigger, getByText } = renderSelectMenu({
    type: 'single',
    hideFooter: false,
    clearable: true,
  })

  await trigger.click()
  await expect.element(getByText('Clear')).toBeVisible()
})

// --- modelValue initialization ---

test('initializes selection from modelValue array', async () => {
  const { trigger, getByRole } = renderSelectMenu({
    type: 'multi',
    modelValue: ['Item 1', 'Item 2'],
  })

  await trigger.click()

  const checkboxes = getByRole('menuitemcheckbox')
  const allCheckboxes = await checkboxes.all()

  // Select All + 4 items = 5 checkboxes
  // Item 1 (index 1) and Item 2 (index 2) should be checked
  await expect.element(allCheckboxes[1]).toHaveAttribute('data-state', 'checked')
  await expect.element(allCheckboxes[2]).toHaveAttribute('data-state', 'checked')
  await expect.element(allCheckboxes[3]).toHaveAttribute('data-state', 'unchecked')
})

test('initializes selection from modelValue string for single select', async () => {
  const { trigger, getByText } = renderSelectMenu({
    type: 'single',
    modelValue: 'Item 2',
    hideFooter: true,
  })

  await trigger.click()
  await expect.element(getByText('Item 2')).toBeVisible()
})

// --- open state ---

test('emits update:open when menu opens and closes', async () => {
  const { trigger, onUpdateOpen } = renderSelectMenu({ type: 'multi' })

  await trigger.click()
  await expect.poll(() => onUpdateOpen).toHaveBeenCalledWith(true)

  await trigger.click()
  await expect.poll(() => onUpdateOpen).toHaveBeenCalledWith(false)
})

test('hideFooter auto-applies on close', async () => {
  const { trigger, getByText, onApply, onUpdateOpen } = renderSelectMenu({
    type: 'multi',
    hideFooter: true,
  })

  await trigger.click()
  await expect.poll(() => onUpdateOpen).toHaveBeenCalledWith(true)

  await getByText('Item 1').click()

  await trigger.click()
  await expect.poll(() => onApply).toHaveBeenCalled()
})

// --- Search ---

test('search filters items in multi-select', async () => {
  const { trigger, getByTestId, getByText } = renderSelectMenu({
    type: 'multi',
    searchable: true,
  })

  await trigger.click()

  const searchBar = getByTestId(generateTestId('PSearchBar'))
  await expect.element(searchBar).toBeVisible()

  const searchInput = searchBar.getByRole('textbox')
  await searchInput.fill('Item')

  await expect.element(getByText('Item 1')).toBeVisible()
  await expect.element(getByText('Item 2')).toBeVisible()

  await searchInput.fill('Item 1')

  await expect.element(getByText('Item 1')).toBeVisible()
  await expect.element(getByText('Item 2')).not.toBeVisible()

  await searchInput.fill('Item 2')

  await expect.element(getByText('Item 1')).not.toBeVisible()
  await expect.element(getByText('Item 2')).toBeVisible()
})

test('search emits search and update:debouncedSearch', async () => {
  const searchDebounce = 100
  const { trigger, getByTestId, onSearch, onUpdateDebouncedSearch } = renderSelectMenu({
    type: 'multi',
    searchable: true,
    searchDebounce,
  })

  await trigger.click()

  const searchBar = getByTestId(generateTestId('PSearchBar'))
  await expect.element(searchBar).toBeVisible()

  const searchInput = searchBar.getByRole('textbox')
  await searchInput.fill('Item')
  await userEvent.keyboard('{Enter}')

  await expect.poll(() => onSearch).toHaveBeenCalledWith('Item')
  await expect.poll(() => onUpdateDebouncedSearch, { timeout: searchDebounce + 500 }).toHaveBeenCalledWith('Item')
})

test('multi: Clear uses selectedCountOverride when provided', async () => {
  const items: PMenuItemProps[] = [
    { id: '1', label: 'A', modelValue: true },
    { id: '2', label: 'B', modelValue: true },
  ]

  const { trigger, getByText } = renderSelectMenu({
    type: 'multi',
    items,
    selectedCountOverride: 9,
  })

  await trigger.click()

  await expect.element(getByText('Clear (9)')).toBeVisible()
  await expect.element(getByText('Clear')).not.toBe('Clear (2)')
})

test('multi: Clear falls back to selectedCount when selectedCountOverride is not provided', async () => {
  const items: PMenuItemProps[] = [
    { id: '1', label: 'A', modelValue: true },
    { id: '2', label: 'B', modelValue: true },
    { id: '3', label: 'C' },
  ]

  const { trigger, getByText } = renderSelectMenu({
    type: 'multi',
    items,
  })

  await trigger.click()

  await expect.element(getByText('Clear (2)')).toBeVisible()
})