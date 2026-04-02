import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { PButton, PTypography } from '@/index'

const meta: Meta<typeof PButton> = {
  component: PButton,
  title: 'Design System/Preflight',
  parameters: {
    disablePreflight: true,
  },
}

export default meta

type Story = StoryObj<typeof PButton>

const exampleTemplate = `
  <h3>Typography:</h3>
  <div class="flex flex-row gap-2">
    <p>This is a regular paragraph</p>
    <PTypography variant="body1">This is a body1 paragraph</PTypography>
  </div>
  <h3>Buttons:</h3>
  <div class="flex flex-row gap-2">
    <button>regular button</button>
    <PButton v-bind="args">
      {{ args.default }}
    </PButton>
  </div>
`

const codeTemplate = `
<div class="flex flex-col gap-2 bg-muted p-4 rounded-md">
  <PTypography variant="h3">Examples of using <code>partner-preflight</code> class applied to the body or other parent elements. All components will inherit this class to allow them to display correctly outside of a <code>partner-preflight</code> container.</PTypography>
</div>
<br />
<div class="flex flex-col gap-2 bg-muted p-4 rounded-md">
  <p>Preflight Disabled</p>
  ${exampleTemplate}
</div>
<br />
<div class="partner-preflight flex flex-col gap-2 bg-muted p-4 rounded-md">
  <p>Preflight Enabled</p>
  ${exampleTemplate}
</div>
`

export const Preflight: Story = {
  parameters: {
    docs: {
      source: {
        code: codeTemplate,
      }
    }
  },
  args: {
    variant: 'primary',
    appearance: 'contained',
    size: 'medium',
    icon: undefined,
    disabled: false,
    default: 'PButton Component',
  },
  render: (args) => ({
    components: { PButton, PTypography },
    setup() {
      return { args }
    },
    template: codeTemplate,
  }),
}