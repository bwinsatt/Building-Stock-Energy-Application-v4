import type { Meta, StoryObj } from '@storybook/vue3-vite'
import PCard from './PCard.vue'
import { PButton, PRadioGroup, PCheckboxGroup, PCheckbox, PTextInput, PTypography } from '@/index'
import { ref } from 'vue'
import { action } from 'storybook/actions'

const meta: Meta<typeof PCard> = {
  component: PCard,
  subcomponents: {
    PButton,
    PRadioGroup,
    PCheckboxGroup,
    PCheckbox,
    PTextInput,
    PTypography,
  },
  title: 'Components/PCard',
}

export default meta

type Story = StoryObj<typeof meta>

const defaultExportableCode = `<PCard
  title="Card Title"
  description="Card Description"
  footer="Card Footer"
/>`

export const Default: Story = {
  parameters: {
    exportableCode: defaultExportableCode,
  },
  args: {
    title: 'Card Title',
    description: 'Card Description',
    footer: 'Card Footer',
  },
  render: (args) => ({
    components: { PCard, ...meta.subcomponents },
    setup() {
      const radioSelected = ref('default')
      const text = ref('')
      const radioOptions = [
        { id: 'default', value: 'default', label: 'Default' },
        { id: 'comfortable', value: 'comfortable', label: 'Comfortable' },
        { id: 'compact', value: 'compact', label: 'Compact' },
      ]
      const checkboxOptions = [
        { id: 'checkbox1', value: 'checkbox1', label: 'Checkbox 1', checked: false },
        { id: 'checkbox2', value: 'checkbox2', label: 'Checkbox 2', checked: false },
        { id: 'checkbox3', value: 'checkbox3', label: 'Checkbox 3', checked: false },
      ]
      const checkboxSelected = ref<string[]>([])
      const handleCancel = () => {
        radioSelected.value = 'default'
        checkboxSelected.value = []
        text.value = ''
        action('cancel')()
      }
      const handleSubmit = () => {
        action('submit')({ radioSelected: radioSelected.value, checkboxSelected: checkboxSelected.value, text: text.value })
      }
      return { args, radioSelected, checkboxSelected, text, radioOptions, checkboxOptions, handleCancel, handleSubmit }
    },
    template: `
    <PCard v-bind="args">
      <div class="flex flex-col gap-2">
        <PRadioGroup v-model="radioSelected" label="Radio Group Label" :options="radioOptions" />
        <PCheckboxGroup label="Checkbox Group Label" orientation="horizontal" v-model="checkboxSelected" :checkboxes="checkboxOptions" />
        <PTextInput v-model="text" label="Text Input Label" placeholder="Text Input Placeholder" />
      </div>
      <template #footer>
        <PTypography variant="body2">{{ args.footer }}</PTypography>
        <div class="flex gap-2 align-center ml-auto justify-end">
          <PButton variant="primary" appearance="outlined" @click="handleCancel">Cancel</PButton>
          <PButton variant="primary" appearance="contained" @click="handleSubmit">Submit</PButton>
        </div>
      </template>
    </PCard>`,
  }),
}