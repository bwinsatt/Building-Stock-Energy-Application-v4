import { defineConfig } from 'vite'
import { resolve } from 'path'

export default defineConfig({
  build: {
    rollupOptions: {
      external: (id: string) => {
        const externals = [
          '@tailwindcss/oxide',
          '@tailwindcss/oxide-linux-x64-gnu',
          '@tailwindcss/oxide-linux-x64-musl',
          'lightningcss',
        ]
        return externals.some((external) => id.includes(external))
      },
    },
  },
  define: {
    global: 'globalThis',
  },
  optimizeDeps: {
    exclude: [
      '@tailwindcss/oxide',
      '@tailwindcss/oxide-linux-x64-gnu',
      '@tailwindcss/oxide-linux-x64-musl',
      'lightningcss',
    ],
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, '../src'),
    },
  },
})
