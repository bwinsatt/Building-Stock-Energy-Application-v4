import type { Preview } from '@storybook/vue3'
import { withThemeByDataAttribute } from '@storybook/addon-themes'
import './storybook.css'
import { onMounted, onUnmounted } from 'vue'

const preview: Preview = {
  parameters: {
    actions: { argTypesRegex: '^on[A-Z].*' },
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
    docs: {
      toc: true,
      codePanel: true,
    },
  },
  decorators: [
    withThemeByDataAttribute({
      themes: {
        light: 'light',
        dark: 'dark',
      },
      defaultTheme: 'light',
      attributeName: 'data-mode',
    }),
    (story, context) => ({
      setup() {
        const enabled = !context.parameters.disablePreflight
        onMounted(() => {
          if (enabled) document.body.classList.add('partner-preflight')
        })
        onUnmounted(() => {
          document.body.classList.remove('partner-preflight')
        })
      },
      template: '<story />',
    }),  
  ],
}

export default preview
