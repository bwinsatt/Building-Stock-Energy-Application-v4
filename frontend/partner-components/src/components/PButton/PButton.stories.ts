import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { PButton } from './index'
import { computed } from 'vue'
import { iconOptions, normalizeIconName } from '@/components/PIcon/iconNames'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/shadcn/ui/table'
import { sizeOptions } from '@/types/size'

const buttonVariants = [
  'primary',
  'secondary',
  'error',
  'warning',
  'success',
  'neutral',
  'white',
]

const buttonAppearances = [
  'contained',
  'outlined',
  'text',
  'link',
]

const buttonSizes = sizeOptions;

const iconPositions = [
  'left',
  'right',
]

const meta: Meta<typeof PButton> = {
  title: 'Components/PButton',
  component: PButton,
  argTypes: {
    variant: {
      control: 'select',
      options: buttonVariants,
      description: 'Figma color / role',
    },
    appearance: {
      control: 'select',
      options: buttonAppearances,
      description: 'Figma appearance',
    },
    size: {
      control: 'select',
      options: buttonSizes,
      description: 'Button size',
    },
    iconButton: {
      control: 'boolean',
      description: 'Whether the button is an icon button',
    },
    iconPosition: {
      control: 'select',
      options: iconPositions,
      description: 'The position of the icon',
    },
    icon: {
      control: 'select',
      options: iconOptions,
      description: 'The icon to display',
    },
    disabled: {
      control: 'boolean',
      description: 'Whether the button is disabled',
    },
    default: {
      control: 'text',
      description: 'The default slot content',
    },
    onClick: {
      type: 'function',
      args: 'event: MouseEvent',
      description: 'The function to call when the button is clicked',
    },
  },
}

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    variant: 'primary',
    appearance: 'contained',
    size: 'medium',
    icon: undefined,
    disabled: false,
    default: 'Button',
  },
  render: (args) => ({
    components: { PButton },
    setup() {
      // Normalize icon name (handle dividers)
      const normalizedArgs = computed(() => {
        const normalizedName = normalizeIconName(args.icon as string)
        return {
          ...args,
          icon: normalizedName,
        }
      })
      return { args: normalizedArgs }
    },
    template: `
      <PButton v-bind="args">
        {{ args.default }}
      </PButton>
    `,
  }),
}

const appearancesTable = `
<Table>
  <TableHeader>
    <TableRow>
      <TableHead v-for="buttonAppearance in buttonAppearances">
        <template v-if="(buttonVariant === 'neutral' || buttonVariant === 'white') && buttonAppearance === 'contained'">  
          <span class="line-through">{{ buttonAppearance }}</span>
        </template>
        <template v-else>
          {{ buttonAppearance }}
        </template>
      </TableHead>
    </TableRow>
  </TableHeader>
  <TableBody>
    <TableRow class="border-0" v-for="buttonSize in buttonSizes">
      <TableCell v-for="buttonAppearance in buttonAppearances">
        <PButton v-bind="{ variant: buttonVariant, appearance: buttonAppearance, size: buttonSize, iconButton: iconButton, icon: iconButton ? 'add-alt' : undefined }">
          {{ "Button" }}
        </PButton>
      </TableCell>
    </TableRow>
  </TableBody>
</Table>
`

const variantsTable = `
<Table>
  <TableHeader>
    <TableRow>
      <TableHead></TableHead>
      <TableHead class="text-center" v-for="buttonVariants in buttonVariants">
        <div class="border-b-1 border-border p-2">
          {{ buttonVariants }}
          </div>
      </TableHead>
    </TableRow>
  </TableHeader>
  <TableBody>
    <TableRow>
      <TableCell>{{ buttonSize }}</TableCell>
      <TableCell v-for="buttonVariant in buttonVariants">
        ${appearancesTable}
      </TableCell>
    </TableRow>
  </TableBody>
</Table>
`

const iconButtonTable = `
<Table>
  <TableHeader>
    <TableRow>
      <TableHead></TableHead>
      <TableHead></TableHead>
    </TableRow>
  </TableHeader>
  <TableBody>
    <TableRow v-for="iconButton in [false, true]">
      <TableCell>iconButton: {{ iconButton }}</TableCell>
      <TableCell>
        ${variantsTable}
      </TableCell>
    </TableRow>
  </TableBody>
</Table>
`

const iconPositionsTable = `
<Table>
  <TableHeader>
    <TableRow>
      <TableHead></TableHead>
      <TableHead></TableHead>
    </TableRow>
  </TableHeader>
  <TableBody>
    <TableRow v-for="iconPosition in iconPositions">
      <TableCell>iconPosition: {{ iconPosition }}</TableCell>
      <TableCell>
        ${variantsTable.replace("icon: iconButton ? 'add-alt' : undefined", `icon: 'add-alt', iconPosition: iconPosition`)}
      </TableCell>
    </TableRow>
  </TableBody>
</Table>
`

export const AllButtonVariants: Story = {
  render: () => ({
    components: { PButton, Table, TableBody, TableCell, TableHead, TableHeader, TableRow },
    setup() {
      return { buttonVariants, buttonAppearances, buttonSizes, iconPositions }
    },
    template: `
      <div class="p-8">
        <h2 class="text-lg font-semibold mb-4">Partner Components Button Variants</h2>
        <p class="text-sm text-muted-foreground mb-6">
          All button variants available in the Partner Components button registry.
        </p>
        ${iconButtonTable}
        ${iconPositionsTable}
      </div>
    `,
  }),
  parameters: {
    layout: 'fullscreen',
    controls: { disable: true },
  },
}