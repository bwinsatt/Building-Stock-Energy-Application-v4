import { expect, test, vi } from 'vitest'
import { render } from 'vitest-browser-vue'
import { PTableRow, PTableHeader, PTableHead, type PTableHeadProps, type PTableHeadEmits } from '@/index'
import { Table } from '@/components/shadcn/ui/table'
import { generateTestId } from '@/utils/testId'

test.each([
  { size: 'small' },
  { size: 'medium' },
  { size: 'large' },
  { sortable: true, sortDirection: 'asc' },
  { sortable: true, sortDirection: 'desc' },
  { filterable: true, filtered: true },
  { filterable: true, filtered: false },
  { selectable: true },
  { expandable: true, expanded: true },
  { expandable: true },
])('PTableHead with props: %o', async (propsToTest) => {
  const testProps = propsToTest as PTableHeadProps
  const testEmits = vi.fn<PTableHeadEmits>()

  const { getByTestId } = render({
    components: { Table, PTableHeader, PTableRow, PTableHead },
    template: `
      <Table>
        <PTableHeader>
          <PTableRow>
            <PTableHead v-bind="testProps"
                        @sort-changed="testEmits('sortChanged', $event)"
                        @filter-clicked="testEmits('filterClicked')"
                        @select-changed="testEmits('selectChanged', $event)"
                        @expand-clicked="testEmits('expandClicked', $event)"
            >
              Header Name
            </PTableHead>
          </PTableRow>
        </PTableHeader>
      </Table>
    `,
    setup() {
      return {
        testProps,
        testEmits
      }
    },
    emits: ['sortChanged', 'filterClicked', 'selectChanged', 'expandClicked']
  })

  const tableHead = getByTestId(generateTestId('PTableHead'))
  expect(tableHead).toBeInTheDocument()
  expect(tableHead).toHaveTextContent('Header Name')


  if (testProps.sortable) {
    const sortCycle = new Map([
      ['asc', 'desc'],
      ['desc', undefined],
      [undefined, 'asc']
    ])
  
    for (let i = 0; i < 3; i++) {
      await tableHead.click()
      let expectedDirection = sortCycle.get(testProps.sortDirection)
      expect(testEmits).toHaveBeenCalledWith('sortChanged', expectedDirection)
    }
  }
  if (testProps.filterable) {
    const filterIcon = getByTestId('filter-icon')
    await filterIcon.click()
    expect(testEmits).toHaveBeenCalledWith('filterClicked')
  }
  if (testProps.selectable) {
    const selectCheckbox = getByTestId('select-checkbox')
    await selectCheckbox.click()
    expect(testEmits).toHaveBeenCalledWith('selectChanged', true)
    await selectCheckbox.click()
    expect(testEmits).toHaveBeenCalledWith('selectChanged', false)
  }
  if (testProps.expandable) {
    const expectedExpanded = !(testProps.expanded ?? false)
    const expandButton = getByTestId('expand-icon')
    await expandButton.click()
    expect(testEmits).toHaveBeenCalledWith('expandClicked', expectedExpanded)
    await expandButton.click()
    expect(testEmits).toHaveBeenCalledWith('expandClicked', !expectedExpanded)
  }
})