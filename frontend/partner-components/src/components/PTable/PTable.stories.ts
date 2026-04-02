import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/shadcn/ui/card'
import { 
  PTable,
  PTableBody,
  PTableHead,
  PTableHeader,
  PTableCell,
  PTableRow,
  PTableEmpty,
  PTableFooter,
  PTableCaption,
} from './index'
import { PTypography } from '@/components/PTypography'
import { PIcon } from '@/components/PIcon'
import { PButton, type PButtonProps } from '@/components/PButton'
import { PCheckbox, type CheckedState } from '@/components/PCheckbox'
import { PPagination } from '@/components/PPagination'
import { sizeOptions } from '@/types/size'
import { ref, computed } from 'vue'

interface TableAction {
  label: string
  icon: string
  onClick: () => void
}

interface TableVariantsStoryArgs {
  size?: (typeof sizeOptions)[number]
  onSortChanged?: (headerName: string, direction: 'asc' | 'desc' | 'none') => void
  onFilterClicked?: (headerName: string, rect: DOMRect) => void
  onSelectChanged?: (headerName: string, value: CheckedState) => void
  onExpandClicked?: (headerName: string) => void
  onCellClick?: (cellValue: string) => void
  onOverflowMenuClick?: (actions: TableAction[]) => void
}

type ResolvedTableVariantsStoryArgs =
  Omit<TableVariantsStoryArgs, 'onSortChanged' | 'onFilterClicked' | 'onSelectChanged' | 'onExpandClicked' | 'onCellClick' | 'onOverflowMenuClick'> & {
    onSortChanged: NonNullable<TableVariantsStoryArgs['onSortChanged']>
    onFilterClicked: NonNullable<TableVariantsStoryArgs['onFilterClicked']>
    onSelectChanged: NonNullable<TableVariantsStoryArgs['onSelectChanged']>
    onExpandClicked: NonNullable<TableVariantsStoryArgs['onExpandClicked']>
    onCellClick: NonNullable<TableVariantsStoryArgs['onCellClick']>
    onOverflowMenuClick: NonNullable<TableVariantsStoryArgs['onOverflowMenuClick']>
  }

const buttonProps: PButtonProps = {
  variant: 'neutral',
  appearance: 'text',
  iconButton: true,
  size: 'small',
}

const meta: Meta<typeof PTable> = {
  title: 'Components/PTable',
  component: PTable,
  subcomponents: {
    PTableHead,
    PTableHeader,
    PTableBody,
    PTableCaption,
    PTableCell,
    PTableEmpty,
    PTableFooter,
    PTableRow,
    PTypography,
    PIcon,
    Card, CardContent, CardHeader, CardTitle, CardDescription,
    PButton,
    PCheckbox,
    PPagination,
  },
}

export default meta

type Story = StoryObj<typeof meta>

const defaultCode = `
    <Card>
      <CardHeader>
        <CardTitle>Table Example</CardTitle>
        <CardDescription>This example table can be modified by the controls below.</CardDescription>
      </CardHeader>
      <CardContent>
        <PTable :class="args.truncate ? 'table-fixed w-100' : ''">
          <PTableHeader :variant="args.variant" :size="args.size">
            <PTableRow>
              <PTableHead
                v-if="args.selectable || args.expandable"
                class="w-10"
                @select-changed="(value) => args.onSelectChanged('Name', value)"
                @expand-clicked="(expanded) => args.onExpandClicked('Name', expanded)"
                :selectable="args.selectable" 
                :selected="args.selected"
                :expandable="args.expandable" 
                :expanded="args.expanded"
              ></PTableHead>
              <PTableHead 
                @sort-changed="(direction) => args.onSortChanged('Name', direction)"
                @filter-clicked="(rect) => args.onFilterClicked('Name', rect)"
                :sortable="args.sortable" 
                :sortDirection="args.sortDirection" 
                :filterable="args.filterable" 
                :filtered="args.filtered" 
              >
                Name</PTableHead>
              <PTableHead>Email</PTableHead>
              <PTableHead>Phone</PTableHead>
            </PTableRow>
          </PTableHeader>
          <PTableBody>
            <PTableEmpty v-if="args.empty"><PIcon name="face-dissatisfied-filled" size="small" /> <PTypography>No data found</PTypography></PTableEmpty>
            <PTableRow v-else-if="!args.empty">
              <PTableCell v-if="args.selectable || args.expandable">
                <div class="flex items-center">
                  <PButton v-if="args.expandable" v-bind="buttonProps" :icon="args.expanded ? 'chevron-down' : 'chevron-right'"></PButton>
                  <PCheckbox v-if="args.selectable" :checked="args.selected === true || args.selected === 'true' || args.selected === 'indeterminate'"/>
                </div>
              </PTableCell>
              <PTableCell :truncate="args.truncate"><PTypography>John Doe</PTypography></PTableCell>
              <PTableCell :truncate="args.truncate"><PTypography>john.doe@example.com</PTypography></PTableCell>
              <PTableCell :truncate="args.truncate"><PTypography>1234567890</PTypography></PTableCell>
            </PTableRow>
            <PTableRow v-if="!args.empty">
              <PTableCell v-if="args.selectable || args.expandable">
                <div class="flex items-center">
                  <PButton v-if="args.expandable" v-bind="buttonProps" :icon="args.expanded ? 'chevron-down' : 'chevron-right'"></PButton>
                  <PCheckbox v-if="args.selectable" :checked="args.selected === true || args.selected === 'true'"/>
                </div>
              </PTableCell>
              <PTableCell :truncate="args.truncate"><PTypography>Jane Doe</PTypography></PTableCell>
              <PTableCell :truncate="args.truncate"><PTypography>jane.doe@example.com</PTypography></PTableCell>
              <PTableCell :truncate="args.truncate"><PTypography>0987654321</PTypography></PTableCell>
            </PTableRow>
          </PTableBody>
          <PTableFooter>
            <PTableRow>
              <PTableCell v-if="args.selectable || args.expandable"></PTableCell>
              <PTableCell :truncate="args.truncate"><PTypography>Name Footer</PTypography></PTableCell>
              <PTableCell :truncate="args.truncate"><PTypography>Email Footer</PTypography></PTableCell>
              <PTableCell :truncate="args.truncate"><PTypography>Phone Footer</PTypography></PTableCell>
            </PTableRow>
          </PTableFooter>
          <PTableCaption :location="args.location">
            <PTypography>Caption {{ args.location }}</PTypography>
          </PTableCaption>
        </PTable>
      </CardContent>
    </Card>`

const defaultExportableCode = `<PTable>
  <PTableHeader variant="gray-fill" size="medium">
    <PTableRow>
      <PTableHead>Name</PTableHead>
      <PTableHead>Email</PTableHead>
      <PTableHead>Phone</PTableHead>
    </PTableRow>
  </PTableHeader>

  <PTableBody>
    <PTableRow>
      <PTableCell><PTypography>John Doe</PTypography></PTableCell>
      <PTableCell><PTypography>john.doe@example.com</PTypography></PTableCell>
      <PTableCell><PTypography>1234567890</PTypography></PTableCell>
    </PTableRow>
    <PTableRow>
      <PTableCell><PTypography>Jane Doe</PTypography></PTableCell>
      <PTableCell><PTypography>jane.doe@example.com</PTypography></PTableCell>
      <PTableCell><PTypography>0987654321</PTypography></PTableCell>
    </PTableRow>
  </PTableBody>
</PTable>`
export const Default: Story = {
  parameters: {
    exportableCode: defaultExportableCode,
    docs: {
      source: {
        code: defaultCode,
      }
    }
  },
  argTypes: {
    empty: {
      control: 'boolean',
      description: 'Example Toggle - Hide table rows and show empty state when true',
      table: {
        category: 'PTableEmpty',
      }
    },
    variant: {
      control: 'select',
      options: ['gray-fill', 'blue-border'],
      description: 'The variant of the table header style',
      table: {
        category: 'PTableHeader',
      }
    },
    size: {
      control: 'select',
      options: sizeOptions,
      description: 'The size of the table head',
      table: {
        category: 'PTableHeader',
      }
    },
    singleSort: {
      control: 'boolean',
      description: 'Whether to allow only one sort at a time',
      table: {
        category: 'PTableHeader',
      }
    },
    sortable: {
      control: 'boolean',
      description: 'Whether the table head is sortable',
      table: {
        category: 'PTableHead',
      }
    },
    sortDirection: {
      control: 'select',
      options: ['asc', 'desc', 'none'],
      description: 'The direction of the sort',
      table: {
        category: 'PTableHead',
      }
    },
    filterable: {
      control: 'boolean',
      description: 'Whether the table head is filterable',
      table: {
        category: 'PTableHead',
      }
    },
    filtered: {
      control: 'boolean',
      description: 'Whether the table head is filtered',
      table: {
        category: 'PTableHead',
      }
    },
    selectable: {
      control: 'boolean',
      description: 'Whether the table head is selectable',
      table: {
        category: 'PTableHead',
      }
    },
    selected: {
      control: 'select',
      options: [true, false, 'indeterminate'],
      description: 'The selected state of the table head',
      table: {
        category: 'PTableHead',
      }
    },
    expandable: {
      control: 'boolean',
      description: 'Whether the table head is expandable',
      table: {
        category: 'PTableHead',
      }
    },
    expanded: {
      control: 'boolean',
      description: 'Whether the table head is expanded',
      table: {
        category: 'PTableHead',
      }
    },
    onSortChanged: {
      type: 'function',
      args: 'direction: "asc" | "desc" | "none"',
      description: 'A function to call when the sort direction is changed',
      table: {
        category: 'PTableHead',
      }
    },
    onFilterClicked: {
      type: 'function',
      args: 'rect: DOMRect',
      description: 'A function to call when the filter is clicked',
      table: {
        category: 'PTableHead',
      }
    },
    onExpandClicked: {
      type: 'function',
      args: 'event: MouseEvent',
      description: 'A function to call when the expand is clicked',
      table: {
        category: 'PTableHead',
      }
    },
    onSelectChanged: {
      type: 'function',
      args: 'value: CheckedState',
      description: 'A function to call when the select is changed',
      table: {
        category: 'PTableHead',
      }
    },
    location: {
      control: 'select',
      options: ['top', 'bottom'],
      description: 'The location of the caption',
      table: {
        category: 'PTableCaption',
      }
    },
    truncate: {
      control: 'boolean',
      description: 'Whether the table cell content is truncated',
      table: {
        category: 'PTableCell',
      }
    },
    onCellClick: {
      type: 'function',
      args: 'event: MouseEvent',
      description: 'A function to call when the cell is clicked',
      table: {
        category: 'PTableCell',
      }
    }
  },
  render: (args) => ({
    components: { PTable, ...meta.subcomponents },
    setup() {
      return { args, buttonProps }
    },
    template: defaultCode,
  }),
} as Story

const variantsCode = `
    <Card>
      <CardHeader>
        <CardTitle>Table Variants</CardTitle>
        <CardDescription>Table variants can be used to change header appearance. The controls below can be used to modify the table header size.</CardDescription>
      </CardHeader>
      <CardContent>
        <PTypography variant="h2">Gray Fill (Fixed Width) - {{ args.size || 'Default Size' }}</PTypography>
        <PTable class="w-full table-fixed">
          <PTableHeader variant="gray-fill" :size="args.size">
            <PTableRow>
              <PTableHead @expand-clicked="args.onExpandClicked('Gray Fill > Expand')" expandable></PTableHead>
              <PTableHead @select-changed="(value) => args.onSelectChanged('Gray Fill > Select', value)" selectable></PTableHead>
              <PTableHead @sort-changed="(direction) => args.onSortChanged('Gray Fill > Name', direction)" @filter-clicked="(rect) => args.onFilterClicked('Gray Fill > Name', rect)" sortable filterable>Name lorem ipsum dolor sit amet consectetur adipisicing elit. Quisquam, quos. Lorem ipsum dolor sit amet consectetur adipisicing elit. Quisquam, quos.</PTableHead>
              <PTableHead @sort-changed="(direction) => args.onSortChanged('Gray Fill > Email', direction)" sortable>Email</PTableHead>
              <PTableHead @filter-clicked="(rect) => args.onFilterClicked('Gray Fill > Phone', rect)" filterable filtered>Phone</PTableHead>
            </PTableRow>
          </PTableHeader>
          <PTableBody>
            <PTableRow>
              <PTableCell><PButton v-bind="buttonProps" icon="chevron-right"></PButton></PTableCell>
              <PTableCell><PCheckbox /></PTableCell>
              <PTableCell><PTypography>John Doe</PTypography></PTableCell>
              <PTableCell><PTypography>john.doe@example.com</PTypography></PTableCell>
              <PTableCell><PTypography>1234567890</PTypography></PTableCell>
            </PTableRow>
            <PTableRow>
              <PTableCell><PButton v-bind="buttonProps" icon="chevron-right"></PButton></PTableCell>
              <PTableCell><PCheckbox /></PTableCell>
              <PTableCell><PTypography>Jane Doe</PTypography></PTableCell>
              <PTableCell><PTypography>jane.doe@example.com</PTypography></PTableCell>
              <PTableCell><PTypography>0987654321</PTypography></PTableCell>
            </PTableRow>
          </PTableBody>
        </PTable>
        <br />
        <PTypography variant="h2">Blue Border - {{ args.size || 'Default Size' }}</PTypography>
        <PTable>
          <PTableHeader variant="blue-border" :size="args.size">
            <PTableRow>
              <PTableHead></PTableHead>
              <PTableHead @sort-changed="(direction) => args.onSortChanged('Blue Border > Name', direction)" @filter-clicked="(rect) => args.onFilterClicked('Blue Border > Name', rect)" sortable filterable>Name</PTableHead>
              <PTableHead @sort-changed="(direction) => args.onSortChanged('Blue Border > Email', direction)" sortable>Email</PTableHead>
              <PTableHead @filter-clicked="(rect) => args.onFilterClicked('Blue Border > Phone', rect)" filterable filtered>Phone</PTableHead>
              <PTableHead></PTableHead>
            </PTableRow>
          </PTableHeader>
          <PTableBody>
            <PTableRow>
              <PTableCell><PButton v-bind="buttonProps" icon="draggable"></PButton></PTableCell>
              <PTableCell><PTypography>John Doe</PTypography></PTableCell>
              <PTableCell><div class="flex items-center gap-1"><PTypography>john.doe@example.com</PTypography> <PIcon name="email" size="small" class="ml-auto"/></div></PTableCell>
              <PTableCell @click="args.onCellClick('1234567890')"><div class="flex items-center gap-1"><PIcon name="phone" size="small" /><PTypography component="span">1234567890</PTypography></div></PTableCell>
              <PTableCell><PButton v-for="action in actions" :key="action.label" v-bind="buttonProps" :icon="action.icon" @click="action.onClick"></PButton></PTableCell>
            </PTableRow>
            <PTableRow>
              <PTableCell><PButton v-bind="buttonProps" icon="draggable"></PButton></PTableCell>
              <PTableCell><PTypography>Jane Doe</PTypography></PTableCell>
              <PTableCell><PTypography>jane.doe@example.com</PTypography></PTableCell>
              <PTableCell><PTypography>0987654321</PTypography></PTableCell>
              <PTableCell><PButton v-bind="buttonProps" icon="overflow-menu-vertical" @click="args.onOverflowMenuClick(actionsBig)"></PButton></PTableCell>
            </PTableRow>
          </PTableBody>
        </PTable>
      </CardContent>
    </Card>`
export const Variants: Story = {
  parameters: {
    docs: {
      source: {
        code: variantsCode,
      }
    }
  },
  argTypes: {
    size: {
      control: 'select',
      options: sizeOptions,
      description: 'PTableHead - The size of the table head',
    },
    onSortChanged: {
      type: 'function',
      args: 'headerName: string, direction: "asc" | "desc" | "none"',
      description: 'Example - A function to call when the sort direction is changed',
    },
    onFilterClicked: {
      type: 'function',
      args: 'headerName: string, rect: DOMRect',
      description: 'Example - A function to call when the filter is clicked',
    },
    onSelectChanged: {
      type: 'function',
      args: 'headerName: string, value: CheckedState',
      description: 'Example - A function to call when the select is changed',
    },
    onExpandClicked: {
      type: 'function',
      args: 'headerName: string',
      description: 'Example - A function to call when the expand is clicked',
    },
    onCellClick: {
      type: 'function',
      args: 'cellValue: string',
      description: 'Example - A function to call when the cell is clicked',
    },
    onOverflowMenuClick: {
      type: 'function',
      args: 'actions: Action[]',
      description: 'Example - A function to call when the overflow menu is clicked',
    },
  },
  render: (args) => ({
    components: { PTable, ...meta.subcomponents },
    setup() {
      const storyArgs = {
        ...(args as typeof args & TableVariantsStoryArgs),
        onSortChanged: (args as TableVariantsStoryArgs).onSortChanged ?? (() => undefined),
        onFilterClicked: (args as TableVariantsStoryArgs).onFilterClicked ?? (() => undefined),
        onSelectChanged: (args as TableVariantsStoryArgs).onSelectChanged ?? (() => undefined),
        onExpandClicked: (args as TableVariantsStoryArgs).onExpandClicked ?? (() => undefined),
        onCellClick: (args as TableVariantsStoryArgs).onCellClick ?? (() => undefined),
        onOverflowMenuClick: (args as TableVariantsStoryArgs).onOverflowMenuClick ?? (() => undefined),
      } satisfies typeof args & ResolvedTableVariantsStoryArgs

      const actions: TableAction[] = [
        { label: 'Edit', icon: 'edit', onClick: () => storyArgs.onCellClick('Edit') },
        { label: 'Email', icon: 'email', onClick: () => storyArgs.onCellClick('Email') },
        { label: 'Delete', icon: 'trash-can', onClick: () => storyArgs.onCellClick('Delete') },
      ]
      const actionsBig: TableAction[] = [
        { label: 'Edit', icon: 'edit', onClick: () => storyArgs.onCellClick('Edit') },
        { label: 'Email', icon: 'email', onClick: () => storyArgs.onCellClick('Email') },
        { label: 'Phone', icon: 'phone', onClick: () => storyArgs.onCellClick('Phone') },
        { label: 'Delete', icon: 'trash-can', onClick: () => storyArgs.onCellClick('Delete') },
      ]

      return { args: storyArgs, buttonProps, actions, actionsBig }
    },
    template: variantsCode,
  }),
} as Story

const truncateCode = `
          <PTableBody>
            <PTableRow>
              <PTableCell><PTypography>Lorem ipsum dolor sit amet consectetur adipisicing elit. Quisquam, quos.</PTypography></PTableCell>
              <PTableCell><PIcon name="bat" size="small"/> <PTypography component="span">Lorem ipsum</PTypography></PTableCell>
            </PTableRow>
            <PTableRow>
              <PTableCell truncate><PTypography>Lorem ipsum dolor sit amet consectetur adipisicing elit. Quisquam, quos.</PTypography></PTableCell>
              <PTableCell truncate><PTypography>Typography short</PTypography></PTableCell>
            </PTableRow>
            <PTableRow>
              <PTableCell truncate><PTypography>Typography with truncation and no margin that respects truncation provided by the parent</PTypography></PTableCell>
              <PTableCell truncate><PTypography>Lorem ipsum</PTypography></PTableCell>
            </PTableRow>
          </PTableBody>`
export const Truncate: Story = {
  parameters: {
    docs: {
      source: {
        code: truncateCode,
      }
    }
  },
  render: (args) => ({
    component: PTableCell,
    components: { PTable, ...meta.subcomponents },
    setup() {
      return { args }
    },
    template: `
    <Card>
      <CardHeader>
        <CardTitle>Cell Content Truncation</CardTitle>
        <CardDescription>Cell content can be truncated. PTypography component inherits truncation provided by the parent cell.</CardDescription>
      </CardHeader>
      <CardContent>
        <PTable class="w-100 table-fixed">
          <PTableHeader variant="blue-border" :size="args.size">
            <PTableRow>
              <PTableHead>Long Content</PTableHead>
              <PTableHead>Short Content</PTableHead>
            </PTableRow>
          </PTableHeader>
          ${truncateCode}
        </PTable>
      </CardContent>
    </Card>`,
  }),
} as Story

const emptyCode = `
          <PTableBody>
            <PTableEmpty><PIcon name="face-dissatisfied-filled" size="small" /> <PTypography>No data found</PTypography></PTableEmpty>
          </PTableBody>`
export const Empty: Story = {
  parameters: {
    docs: {
      source: {
        code: emptyCode,
      }
    }
  },
  render: (args) => ({
    components: { PTable, ...meta.subcomponents },
    setup() {
      return { args }
    },
    template: `
    <Card>
      <CardHeader>
        <CardTitle>Table Empty</CardTitle>
        <CardDescription>Table empty can be used to display a message when there is no data. It defaults to a full width row with the content centered.</CardDescription>
      </CardHeader>
      <CardContent>
        <PTable>
          <PTableHeader>
            <PTableRow>
              <PTableHead>Name</PTableHead>
              <PTableHead>Email</PTableHead>
              <PTableHead>Phone</PTableHead>
            </PTableRow>
          </PTableHeader>
          ${emptyCode}
        </PTable>
      </CardContent>
    </Card>`,
  }),
} as Story

const footerCode = `
          <PTableFooter>
            <PTableRow>
              <PTableCell><PTypography>Name Footer</PTypography></PTableCell>
              <PTableCell><PTypography>Email Footer</PTypography></PTableCell>
              <PTableCell><PTypography>Phone Footer</PTypography></PTableCell>
            </PTableRow>
            <PTableRow>
              <PTableCell colspan="999"><div class="flex items-center justify-center gap-1"><PTypography>Full Width Footer</PTypography></div></PTableCell>
            </PTableRow>
            <PTableRow>
              <PTableCell colspan="999">
                <PPagination :items-per-page="itemsPerPage" :total-pages="mockData.length" :current-page="currentPage" @update:page="updatePage" />
              </PTableCell>
            </PTableRow>            
          </PTableFooter>`
export const Footers: Story = {
  parameters: {
    docs: {
      source: {
        code: footerCode,
      }
    }
  },
  render: (args) => ({
    components: { PTable, ...meta.subcomponents },
    setup() {
      /**
       * Pagination example data
       */
      const currentPage = ref(1)
      const itemsPerPage = 2
      const mockData = [
        ['John Doe', 'john@example.com', '1234567890'],
        ['Jane Smith', 'jane@example.com', '0987654321'],
        ['Bob Johnson', 'bob@example.com', '5551234567'],
        ['Alice Brown', 'alice@example.com', '5559876543'],
        ['Gary Ribbit', 'gary@ribbit.com', '5551234567'],
        ['Billie Biscuit', 'billie@biscuit.com', '5559876543'],
        ['Don Yolk', 'don@yolk.com', '5551234567'],
        ['Cindy Egg', 'cindy@egg.com', '5559876543'],
      ]

      const paginatedData = computed(() => {
        const start = (currentPage.value - 1) * itemsPerPage
        const result = mockData.slice(start, start + itemsPerPage)
        console.log('Current page:', currentPage.value)
        console.log('Paginated data:', result)
        return result
      })

      const updatePage = (page: number) => {
        currentPage.value = page
      }
      
      return { args,
        currentPage,
        mockData,
        itemsPerPage,
        paginatedData,
        updatePage
      }
    },
    template: `
    <Card>
      <CardHeader>
        <CardTitle>Table Footer</CardTitle>
        <CardDescription>Table footer can be placed at the bottom of the table. It has custom row styling based on the footer content.</CardDescription>
      </CardHeader>
      <CardContent>
        <PTable id="table-footer">
          <PTableHeader>
            <PTableRow>
              <PTableHead class="w-100">Name</PTableHead>
              <PTableHead class="w-100">Email</PTableHead>
              <PTableHead class="w-50">Phone</PTableHead>
            </PTableRow>
          </PTableHeader>
          <PTableBody>
            <PTableRow v-for="(row, index) in paginatedData" :key="index">
              <PTableCell><PTypography>{{ row[0] }}</PTypography></PTableCell>
              <PTableCell><PTypography>{{ row[1] }}</PTypography></PTableCell>
              <PTableCell><PTypography>{{ row[2] }}</PTypography></PTableCell>
            </PTableRow>
          </PTableBody>
          ${footerCode}
        </PTable>
      </CardContent>
    </Card>`,
  }),
} as Story

const captionsCode = `
    <Card>
    <CardHeader>
      <CardTitle>Table Caption</CardTitle>
      <CardDescription>Table caption can be placed at the top or bottom of the table.</CardDescription>
    </CardHeader>
    <CardContent>
      <PTable>
        <PTableHeader>
          <PTableRow>
            <PTableHead>Name</PTableHead>
            <PTableHead>Email</PTableHead>
            <PTableHead>Phone</PTableHead>
          </PTableRow>
        </PTableHeader>
        <PTableBody>
          <PTableRow>
            <PTableCell><PTypography>John Doe</PTypography></PTableCell>
            <PTableCell><PTypography>john.doe@example.com</PTypography></PTableCell>
            <PTableCell><PTypography>1234567890</PTypography></PTableCell>
          </PTableRow>
        </PTableBody>        
        <PTableCaption><PTypography>Caption Bottom (Default)</PTypography></PTableCaption>
      </PTable>
      <br />
      <PTable>
        <PTableHeader>
          <PTableRow>
            <PTableHead>Name</PTableHead>
            <PTableHead>Email</PTableHead>
            <PTableHead>Phone</PTableHead>
          </PTableRow>
        </PTableHeader>
        <PTableBody>
          <PTableRow>
            <PTableCell><PTypography>John Doe</PTypography></PTableCell>
            <PTableCell><PTypography>john.doe@example.com</PTypography></PTableCell>
            <PTableCell><PTypography>1234567890</PTypography></PTableCell>
          </PTableRow>
        </PTableBody>        
        <PTableCaption location="top"><PTypography>Caption Top</PTypography></PTableCaption>
      </PTable>
    </CardContent>
  </Card>`
export const Captions: Story = {
  parameters: {
    docs: {
      source: {
        code: captionsCode,
      }
    }
  },
  render: (args) => ({
    components: { PTable, ...meta.subcomponents },
    setup() {
      return { args }
    },
    template: captionsCode,
  }),
} as Story

const singleSortCode = `
            <PTableHeader variant="gray-fill" :size="args.size" :single-sort="args.singleSort">
              <PTableRow>
                <PTableHead @sort-changed="(direction) => args.onSortChanged('Name', direction)" sortable>Name lorem ipsum dolor sit amet consectetur adipisicing elit. Quisquam, quos. Lorem ipsum dolor sit amet consectetur adipisicing elit. Quisquam, quos.</PTableHead>
                <PTableHead @sort-changed="(direction) => args.onSortChanged('Email', direction)" sortable>Email</PTableHead>
                <PTableHead @sort-changed="(direction) => args.onSortChanged('Phone', direction)" sortable>Phone</PTableHead>
              </PTableRow>
            </PTableHeader>`
export const SingleSort: Story = {
  parameters: {
    docs: {
      source: {
        code: singleSortCode,
      }
    }
  },
  args: {
    singleSort: true,
  },
  argTypes: {
    singleSort: {
      control: 'boolean',
      description: 'Whether to allow only one sort at a time',
      table: {
        category: 'PTableHeader',
      }
    },
    onSortChanged: {
      type: 'function',
      args: 'headerName: string, direction: "asc" | "desc" | "none"',
      description: 'Example - A function to call when the sort direction is changed',
      table: {
        category: 'PTableHead',
      }
    },
  },  
  render: (args) => ({
    components: { PTable, ...meta.subcomponents },
    setup() {
      return { args }
    },
    template: `
      <Card>
        <CardHeader>
          <CardTitle>Single Sort</CardTitle>
          <CardDescription>Allow only one sort at a time</CardDescription>
        </CardHeader>
        <CardContent>
          <PTable class="w-full table-fixed">
            ${singleSortCode}
            <PTableBody>
              <PTableRow>
                <PTableCell><PTypography>John Doe</PTypography></PTableCell>
                <PTableCell><PTypography>john.doe@example.com</PTypography></PTableCell>
                <PTableCell><PTypography>1234567890</PTypography></PTableCell>
              </PTableRow>
              <PTableRow>
                <PTableCell><PTypography>Jane Doe</PTypography></PTableCell>
                <PTableCell><PTypography>jane.doe@example.com</PTypography></PTableCell>
                <PTableCell><PTypography>0987654321</PTypography></PTableCell>
              </PTableRow>
            </PTableBody>
          </PTable>
        </CardContent>
      </Card>`,
  }),
} as Story
