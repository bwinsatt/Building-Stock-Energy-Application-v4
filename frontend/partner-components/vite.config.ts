import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import tailwindcss from '@tailwindcss/vite'
import dts from 'vite-plugin-dts'

export default defineConfig({
  build: {
    lib: {
      entry: resolve(__dirname, 'src/index.ts'),
      name: 'PComponents',
      fileName: (format) => `p-components.${format}.js`,
    },
    rollupOptions: {
      external: ['vue', 'reka-ui'],
      output: {
        globals: {
          vue: 'Vue',
          'reka-ui': 'RekaUI',
        },
      },
    },
    cssCodeSplit: false,
  },
  define: {
    global: 'globalThis',
  },
  // Handle native modules and external dependencies
  optimizeDeps: {
    exclude: [
      '@tailwindcss/oxide',
      '@tailwindcss/oxide-linux-x64-gnu',
      '@tailwindcss/oxide-linux-x64-musl',
      'lightningcss',
    ],
  },
  plugins: [vue(), tailwindcss(), dts({ include: ['src/**/*'] })],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  // Development server configuration
  server: {
    port: 3000,
    open: true,
  },
})
