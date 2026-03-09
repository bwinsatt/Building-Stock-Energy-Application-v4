import type { StorybookConfig } from '@storybook/vue3-vite'
import { resolve } from 'path'
import tailwindcss from '@tailwindcss/vite'

const config: StorybookConfig = {
  stories: ['../src/**/*.stories.@(js|jsx|mjs|ts|tsx|vue)'],
  addons: [
    '@storybook/addon-links',
    '@storybook/addon-themes',
    '@storybook/addon-docs'
  ],
  framework: {
    name: '@storybook/vue3-vite',
    options: {},
  },
  viteFinal: async (config) => {
    // Simple and direct path alias configuration
    const projectRoot = process.cwd()

    config.resolve = {
      ...config.resolve,
      alias: {
        ...config.resolve?.alias,
        '@': resolve(projectRoot, 'src'),
        '@/types': resolve(projectRoot, 'src/types'),
        '@/components': resolve(projectRoot, 'src/components'),
        '@/utils': resolve(projectRoot, 'src/utils'),
      },
      extensions: ['.mjs', '.js', '.ts', '.jsx', '.tsx', '.json', '.vue'],
    }

    // Add Tailwind CSS v4 Vite plugin
    config.plugins = [...(config.plugins || []), tailwindcss()]

    // Configure optimization
    config.optimizeDeps = {
      ...config.optimizeDeps,
      include: ['vue'],
    }

    return config
  },
}
export default config
