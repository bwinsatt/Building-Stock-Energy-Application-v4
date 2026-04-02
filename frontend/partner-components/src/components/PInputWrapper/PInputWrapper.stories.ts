import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { PInputWrapper } from './index'

const meta: Meta<typeof PInputWrapper> = {
  component: PInputWrapper,
  title: 'Components/PInputWrapper',
}

export default meta

type Story = StoryObj<typeof PInputWrapper>

export const Default: Story = {
  args: {
    label: 'Input label',
    id: 'input',
    required: false,
    disabled: false,
    error: false,
    helperText: 'Helper text',
    errorText: 'Error text',
  },
  render: (args) => ({
    components: { PInputWrapper },
    setup: () => ({ args }),
    template: `
      <PInputWrapper v-bind="args">
        <input type="text" value="Mock input" />
      </PInputWrapper>
    `,
  }),
}