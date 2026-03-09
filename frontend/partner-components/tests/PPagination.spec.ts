import { expect, test, vi } from 'vitest'
import { render } from 'vitest-browser-vue'
import { PPagination, type PPaginationProps } from '@/index'

test.each([
  { itemsPerPage: 1, totalPages: 5, currentPage: 1, size: 'medium' },
  { itemsPerPage: 1, totalPages: 5, currentPage: 3, size: 'small' },
  { itemsPerPage: 1, totalPages: 12, currentPage: 1, size: 'medium' },
  { itemsPerPage: 1, totalPages: 12, currentPage: 6, size: 'medium' },
  { itemsPerPage: 1, totalPages: 3, currentPage: 1, size: 'medium' },
])('PPagination with props: %o', async (propsToTest) => {
  const testProps = propsToTest as PPaginationProps
  const onUpdatePage = vi.fn()

  const { getByText, getByRole } = render({
    components: { PPagination },
    template: `<PPagination v-bind="testProps" @update:page="onUpdatePage" />`,
    setup() {
      return { testProps, onUpdatePage }
    },
  })

  // --- Container ---
  const pagination = getByRole('navigation')
  expect(pagination).toBeInTheDocument()

  // --- Current page is rendered ---
  const currentPageEl = getByText(String(testProps.currentPage), { exact: true })
  expect(currentPageEl).toBeInTheDocument()

  // --- Previous / Next buttons ---
  const prevButton = document.querySelector('[data-slot="pagination-previous"]') as HTMLElement
  const nextButton = document.querySelector('[data-slot="pagination-next"]') as HTMLElement
  expect(prevButton).not.toBeNull()
  expect(nextButton).not.toBeNull()

  // --- Click next page ---
  nextButton.click()
  await expect.poll(() => onUpdatePage).toHaveBeenCalledWith(testProps.currentPage + 1)

  // --- Click a specific page number ---
  onUpdatePage.mockClear()
  if (testProps.totalPages >= 2) {
    const afterNextPage = testProps.currentPage + 1
    const targetPage = afterNextPage === 1 ? 2 : 1
    const pageButton = getByText(String(targetPage), { exact: true })
    await pageButton.click()
    await expect.poll(() => onUpdatePage).toHaveBeenCalledWith(targetPage)
  }

  // --- Ellipsis for large page counts ---
  if (testProps.totalPages > 7) {
    const ellipsis = document.querySelector('[data-slot="pagination-ellipsis"]')
    expect(ellipsis).not.toBeNull()
  }
})
