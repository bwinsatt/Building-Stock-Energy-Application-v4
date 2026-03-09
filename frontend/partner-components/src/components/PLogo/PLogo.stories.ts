import type { Meta, StoryObj } from '@storybook/vue3-vite'
import PLogo from './PLogo.vue'
import { logoOptions } from './logoConstants'
import { ref, watchEffect, nextTick } from 'vue'

const meta: Meta<typeof PLogo> = {
  component: PLogo,
  title: 'Components/PLogo',
  parameters: {
    layout: 'centered',
  },
  decorators: [
    () => ({
      template: `
        <div class="flex flex-col items-center gap-4">
          <story />
          <div class="mt-4 p-4 rounded-lg text-xs font-mono max-w-xl bg-muted border border-dashed border-purple-500">
            <div class="font-semibold mb-1">Rendered HTML:</div>
            <pre class="whitespace-pre-wrap break-all">{{ html }}</pre>
          </div>
        </div>
      `,
      setup() {
        const html = ref('')
        
        const updateHtml = () => {
          nextTick(() => {
            const img = document.querySelector('img[data-testid]')
            html.value = img?.outerHTML || 'Not found'
            html.value = html.value.replace(/src="[^"]*"/g, 'src="..."')
          })
        }
        
        // Watch for any DOM changes and update
        watchEffect(() => {
          updateHtml()
        })
        
        // Also use MutationObserver to catch attribute changes
        const observer = new MutationObserver(updateHtml)
        nextTick(() => {
          const img = document.querySelector('img[data-testid]')
          if (img) {
            observer.observe(img, { 
              attributes: true, 
              attributeFilter: ['data-testid', 'width', 'height', 'alt'] 
            })
          }
        })
        
        return { html }
      }
    })
  ],
  argTypes: {
    logoName: {
      control: 'select',
      options: logoOptions,
      description: 'Logo name to display. Resulting filename will be used in the data-testid attribute',
    },
    name: {
      control: 'text',
      description: 'Name for this logo instance, used in the data-testid attribute',
    },
    width: {
      control: 'text',
      description: 'Logo width',
    },
    height: {
      control: 'text',
      description: 'Logo height',
    },
    alt: {
      control: 'text',
      description: 'Alt text for the logo image',
    },
  },
}

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    logoName: 'Partner',
    name: 'Main Logo',
    /* width and height intentionally left blank to test undefined values */
    alt: 'Partner Logo',
  },
  parameters: {
    docs: {
      description: {
        story: 'The calculated `data-testid` will be: `plogo-main-logo-partner`',
      },
    },
  },
}

