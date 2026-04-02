import type { Meta, StoryObj } from '@storybook/vue3-vite'
import POverflowGroup from './POverflowGroup.vue'
import { PChip } from '@/components/PChip'

const meta: Meta<typeof POverflowGroup> = {
  component: POverflowGroup,
  subcomponents: { PChip },
  title: 'Components/POverflowGroup',
  argTypes: {
    truncate: {
      control: 'boolean',
      description: 'Whether to truncate the overflow group',
    },
  },
}

export default meta

type Story = StoryObj<typeof POverflowGroup>

const defaultExportableCode = `<POverflowGroup :truncate="true">
  <PChip variant="primary" appearance="contained" size="medium">Item 1</PChip>
  <PChip variant="primary" appearance="contained" size="medium">Item 2</PChip>
  <PChip variant="primary" appearance="contained" size="medium">Item 3</PChip>
  <PChip variant="primary" appearance="contained" size="medium">Item 4</PChip>
</POverflowGroup>`

export const Default: Story = {
  args: {
    truncate: true,
  },
  parameters: {
    exportableCode: defaultExportableCode,
  },
  render: (args) => ({
    components: { POverflowGroup, PChip },
    setup() {
      const pchipArgs = {
        variant: 'primary',
        appearance: 'contained',
        size: 'medium',
      }
      return { args, pchipArgs }
    },
    template: `
    <div class="resize-x overflow-auto border border-dashed border-gray-300 p-2 w-72">
      <POverflowGroup v-bind="args">
        <PChip v-bind="pchipArgs">Item 1</PChip>
        <PChip v-bind="pchipArgs">Item 2</PChip>
        <PChip v-bind="pchipArgs">Item 3</PChip>
        <PChip v-bind="pchipArgs">Item 4</PChip>
        <PChip v-bind="pchipArgs">Item 5</PChip>
        <PChip v-bind="pchipArgs">Item 6</PChip>
        <PChip v-bind="pchipArgs">Item 7</PChip>
        <PChip v-bind="pchipArgs">Item 8</PChip>
        <PChip v-bind="pchipArgs">Item 9</PChip>
        <PChip v-bind="pchipArgs">Item 10</PChip>
      </POverflowGroup>
    </div>
    `,
  }),
}
