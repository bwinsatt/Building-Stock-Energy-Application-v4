import { expect, test, vi } from 'vitest'
import { render } from 'vitest-browser-vue'
import { PTable,PTableRow, PTableHeader, PTableHead,type PTableHeaderProps, type PTableHeadEmits } from '@/index'
import { generateTestId } from '@/utils/testId'

test.each([
  { singleSort: true },
])('PTableHeader with props: %o', async (propsToTest) => {
  const testProps = propsToTest as PTableHeaderProps
  const testEmits = vi.fn<PTableHeadEmits>()
  
  const { getByTestId } = render({
    components: { PTable, PTableRow, PTableHeader, PTableHead },
    template: `
      <PTable>
        <PTableHeader v-bind="testProps">
          <PTableRow>
            <PTableHead @sort-changed="testEmits('sortChanged', $event)" sortable>Header Name</PTableHead>
            <PTableHead @sort-changed="testEmits('sortChanged', $event)" sortable sort-direction="desc">Header Name 2</PTableHead>
          </PTableRow>
        </PTableHeader>
      </PTable>
    `,
    setup() {
      return { testProps, testEmits }
    },
  })

  const firstHead = getByTestId(generateTestId('PTableHead')).nth(0)
  const secondHead = getByTestId(generateTestId('PTableHead')).nth(1)

  // --- Sort first head ---
  expect(secondHead).toHaveAttribute('data-sort-direction', 'desc')
  await firstHead.click()
  expect(testEmits).toHaveBeenCalledWith('sortChanged', 'asc')
  expect(firstHead).toHaveAttribute('data-sort-direction', 'asc')
  expect(secondHead).not.toHaveAttribute('data-sort-direction')

  // --- Sort second head ---
  await secondHead.click()
  expect(testEmits).toHaveBeenCalledWith('sortChanged', 'asc')
  expect(secondHead).toHaveAttribute('data-sort-direction', 'asc')
  expect(firstHead).not.toHaveAttribute('data-sort-direction')
})