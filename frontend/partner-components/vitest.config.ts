import { defineConfig, mergeConfig } from 'vitest/config'
import { playwright } from '@vitest/browser-playwright'
import viteConfig from './vite.config'

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      include: ['tests/**/*.spec.ts'],
      exclude: ['tests/**/*.node.spec.ts'],
      browser: {
        enabled: true,
        provider: playwright(),
        instances: [
          { browser: 'chromium' },
        ],
      },
    },
  })
)
