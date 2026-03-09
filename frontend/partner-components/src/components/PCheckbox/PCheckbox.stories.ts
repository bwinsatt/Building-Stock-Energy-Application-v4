import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { PCheckbox } from '.'
import { sizeOptions } from '@/types/size'

const meta: Meta<typeof PCheckbox> = {
  component: PCheckbox,
  title: 'Components/PCheckbox',
}

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    id: 'checkbox',
    class: '',
    size: 'medium',
    label: 'Checkbox label',
    checked: false,
    disabled: false,
    indeterminate: false,
    required: false,
  },
  argTypes: {
    id: {
      control: 'text',
      description: 'The id attribute for the checkbox',
    },
    class: {
      control: 'text',
      description: 'The class attribute for the checkbox',
    },
    size: {
      control: 'select',
      options: sizeOptions,
    },
    disabled: {
      control: 'boolean',
      description: 'Whether the checkbox is disabled',
    },
    checked: {
      control: 'boolean',
      description: 'Whether the checkbox default value is checked',
    },
    indeterminate: {
      control: 'boolean',
      description: 'Whether the checkbox is indeterminate',
    },
    required: {
      control: 'boolean',
      description: 'Whether the checkbox is required',
    },
    onChanged: {
      type: 'function',
      args: 'value: boolean | "indeterminate"',
      description: 'The function to call when the checkbox is changed',
    },
  },
}

export const AllStates: Story = {
  render: () => ({
    components: { PCheckbox },
    setup() {
      return { states: [
        { checked: false, indeterminate: false, label: 'Unchecked' },
        { checked: true, indeterminate: false, label: 'Checked' },
        { checked: false, indeterminate: true, label: 'Indeterminate' },
        { checked: true, indeterminate: true, label: 'Checked and Indeterminate' },
      ] }
    },
    template: `
      <div class="grid grid-cols-3 gap-4">
        <div class="grid-item">
          <p class="text-sm text-muted-foreground">Default</p>
          <PCheckbox v-for="state in states" :checked="state.checked" :indeterminate="state.indeterminate" :label="state.label" />
        </div>
        <div class="grid-item">
          <p class="text-sm text-muted-foreground">Disabled</p>
          <PCheckbox v-for="state in states" :checked="state.checked" :indeterminate="state.indeterminate" :label="state.label" :disabled="true" />
        </div>
        <div class="grid-item">
          <p class="text-sm text-muted-foreground">Required</p>
          <PCheckbox v-for="state in states" :checked="state.checked" :indeterminate="state.indeterminate" :label="state.label" :required="true" />
        </div>
      </div>
    `,
  }),
}