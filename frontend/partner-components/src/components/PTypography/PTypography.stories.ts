import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { ref, onMounted, nextTick, watch } from 'vue'
import PTypography from './PTypography.vue'
import { typographyVariants, typographyComponents, typographyAligns } from './types'

const meta: Meta<typeof PTypography> = {
  component: PTypography,
  title: 'Components/PTypography',
  parameters: {
    layout: 'centered',
  },
  args: {
    variant: 'body1',
    align: 'inherit',
    component: undefined,
    noWrap: false,
  },
  argTypes: {
    variant: {
      control: 'select',
      options: typographyVariants,
    },
    align: {
      control: 'select',
      options: typographyAligns,
    },
    component: {
      control: 'select',
      options: [...typographyComponents, undefined],
    },
    noWrap: {
      control: 'boolean',
      description: 'Whether to wrap the text',
    },
  },
}

export default meta

const defaultExportableCode = `<PTypography variant="body1">
  Lorem ipsum dolor sit amet consectetur adipisicing elit.
</PTypography>`

export const Default: StoryObj<typeof PTypography> = {
  parameters: {
    exportableCode: defaultExportableCode,
  },
  render: (args) => ({
    components: { PTypography },
    template: `
    <div class="flex flex-col gap-4">
      <div ref="wrapperRef">
        <PTypography v-bind="args" class="w-full">Lorem ipsum dolor sit amet consectetur adipisicing elit. Quisquam, quos.</PTypography>
      </div>
      <div class="mt-4 p-4 rounded-lg text-xs font-mono max-w-xl bg-muted border border-dashed border-purple-500">
        <p class="text-sm font-mono font-bold mb-2">HTML Output:</p>
        <pre class="text-xs overflow-auto whitespace-pre-wrap">{{ htmlOutput }}</pre>
      </div>
    </div>
    `,
    setup() {
      const wrapperRef = ref<HTMLElement | null>(null)
      const htmlOutput = ref('')
      
      const updateHtmlOutput = async () => {
        await nextTick()
        if (wrapperRef.value) {
          const typographyElement = wrapperRef.value.querySelector('*')
          if (typographyElement) {
            htmlOutput.value = typographyElement.outerHTML
          }
        }
      }
      
      onMounted(updateHtmlOutput)
      
      watch(() => args, updateHtmlOutput, { deep: true })
      
      return {
        args,
        wrapperRef,
        htmlOutput,
      }
    },
  }),
}
