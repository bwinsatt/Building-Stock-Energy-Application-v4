import { expect, test, vi } from 'vitest'
import { render } from 'vitest-browser-vue'
import { PMenu, PMenuItem } from '@/components/PMenu'
import { PButton } from '@/components/PButton'
import { generateTestId } from '@/utils/testId'
import { userEvent } from 'vitest/browser'

function renderMenu(props: Record<string, unknown> = {}) {
  const onUpdateOpen = vi.fn()
  const onSelect = vi.fn()
  const onUpdateDebouncedSearch = vi.fn()
  const onSearch = vi.fn()
  
  const screen = render({
    components: { PMenu, PMenuItem, PButton },
    template: `
      <PMenu v-bind="testProps" @update:open="onUpdateOpen" @update:debouncedSearch="onUpdateDebouncedSearch" @search="onSearch">
        <template #trigger>
          <PButton name="trigger">Open menu</PButton>
        </template>
        <template #content>
          <PMenuItem type="item" label="Item 1" @select="onSelect" />
          <PMenuItem type="item" label="Item 2" @select="onSelect" />
          <PMenuItem type="item" label="Item 3" disabled @select="onSelect" />
        </template>
      </PMenu>
    `,
    setup: () => ({ testProps: props, onUpdateOpen, onSelect, onUpdateDebouncedSearch, onSearch }),
  })

  const trigger = screen.getByTestId(generateTestId('PButton', 'trigger'))

  return { ...screen, trigger, onUpdateOpen, onSelect, onUpdateDebouncedSearch, onSearch }
}

test('renders trigger slot', () => {
  const { trigger } = renderMenu()
  expect(trigger).toBeInTheDocument()
  expect(trigger).toHaveTextContent('Open menu')
})

test('opens on trigger click and emits update:open', async () => {
  const { trigger, getByText, onUpdateOpen } = renderMenu()

  await trigger.click()
  await expect.poll(() => onUpdateOpen).toHaveBeenCalledWith(true)
  await expect.element(getByText('Item 1')).toBeVisible()
  await expect.element(getByText('Item 2')).toBeVisible()
})

test('closes on second trigger click and emits update:open false', async () => {
  const { trigger, onUpdateOpen } = renderMenu()

  await trigger.click()
  await expect.poll(() => onUpdateOpen).toHaveBeenCalledWith(true)

  await trigger.click()
  await expect.poll(() => onUpdateOpen).toHaveBeenCalledWith(false)
})

test('renders open by default when defaultOpen is true', async () => {
  const { getByText } = renderMenu({ defaultOpen: true })

  await expect.element(getByText('Item 1')).toBeVisible()
  await expect.element(getByText('Item 2')).toBeVisible()
})

test('selecting a menu item emits select and closes menu', async () => {
  const { trigger, getByText, onSelect, onUpdateOpen } = renderMenu()

  await trigger.click()
  await expect.poll(() => onUpdateOpen).toHaveBeenCalledWith(true)

  const item = getByText('Item 1')
  await expect.element(item).toBeVisible()
  await item.click()

  expect(onSelect).toHaveBeenCalled()
  await expect.poll(() => onUpdateOpen).toHaveBeenCalledWith(false)
})

test('disabled menu item does not emit select', async () => {
  const { trigger, getByText, onSelect, onUpdateOpen } = renderMenu()

  await trigger.click()
  await expect.poll(() => onUpdateOpen).toHaveBeenCalledWith(true)

  const disabledItem = getByText('Item 3')
  await expect.element(disabledItem).toBeVisible()
  await disabledItem.click({ force: true })

  expect(onSelect).not.toHaveBeenCalled()
})

test('disabled trigger prevents menu from opening', async () => {
  const { trigger, onUpdateOpen } = renderMenu({ disabled: true })

  await trigger.click({ force: true })
  expect(onUpdateOpen).not.toHaveBeenCalled()
})

test('renders label when provided', async () => {
  const { getByText } = renderMenu({ defaultOpen: true, label: 'Menu Label' })

  await expect.element(getByText('Menu Label')).toBeVisible()
})

test('renders search bar when searchable is true', async () => {
  const { getByTestId } = renderMenu({ defaultOpen: true, searchable: true })

  await expect.element(getByTestId(generateTestId('PSearchBar'))).toBeVisible()
})

test('does not render search bar when searchable is false', async () => {
  const { getByTestId } = renderMenu({ defaultOpen: true, searchable: false })

  await expect.element(getByTestId(generateTestId('PSearchBar'))).not.toBeInTheDocument()
})

test('renders footer slot content', async () => {
  const onUpdateOpen = vi.fn()

  const { getByText } = render({
    components: { PMenu, PMenuItem, PButton },
    template: `
      <PMenu default-open @update:open="onUpdateOpen">
        <template #trigger>
          <PButton name="trigger">Open</PButton>
        </template>
        <template #content>
          <PMenuItem type="item" label="Item 1" />
        </template>
        <template #footer>
          <span data-testid="footer-content">Footer text</span>
        </template>
      </PMenu>
    `,
    setup: () => ({ onUpdateOpen }),
  })

  await expect.element(getByText('Footer text')).toBeVisible()
})

test('search filters items by label', async () => {
  const { getByTestId, getByText } = renderMenu({ defaultOpen: true, searchable: true })

  const searchBar = getByTestId(generateTestId('PSearchBar'))
  await expect.element(searchBar).toBeVisible()

  const searchInput = searchBar.getByRole('textbox')
  await searchInput.fill('Item 1')

  await expect.element(getByText('Item 1')).toBeVisible()
  await expect.element(getByText('Item 2')).not.toBeVisible()
})

test('syncs open state from prop changes', async () => {
  const onUpdateOpen = vi.fn()
  const { ref } = await import('vue')
  const isOpen = ref(false)

  const { getByText } = render({
    components: { PMenu, PMenuItem, PButton },
    template: `
      <PMenu :open="isOpen" @update:open="onUpdateOpen">
        <template #trigger>
          <PButton name="trigger">Open</PButton>
        </template>
        <template #content>
          <PMenuItem type="item" label="Prop Item" />
        </template>
      </PMenu>
    `,
    setup: () => ({ isOpen, onUpdateOpen }),
  })

  isOpen.value = true
  await expect.element(getByText('Prop Item')).toBeVisible()
})

test('search emits search and update:debouncedSearch', async () => {
  const searchDebounce = 100
  const { trigger, getByTestId, onSearch, onUpdateDebouncedSearch } = renderMenu({ defaultOpen: true, searchable: true, searchDebounce })

  await trigger.click()

  const searchBar = getByTestId(generateTestId('PSearchBar'))
  await expect.element(searchBar).toBeVisible()

  const searchInput = searchBar.getByRole('textbox')
  await searchInput.fill('Item 1')
  await userEvent.keyboard('{Enter}')

  await expect.poll(() => onSearch).toHaveBeenCalledWith('Item 1')
  await expect.poll(() => onUpdateDebouncedSearch, { timeout: searchDebounce + 1000 }).toHaveBeenCalledWith('Item 1')
})