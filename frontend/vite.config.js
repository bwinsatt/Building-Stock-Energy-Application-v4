import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    proxy: {
      '/assess': 'http://localhost:8001',
      '/offload': 'http://localhost:8001',
      '/metadata': 'http://localhost:8001',
      '/lookup': 'http://localhost:8001',
      '/bps': 'http://localhost:8001',
      '/autocomplete': 'http://localhost:8001',
      '/energy-star': 'http://localhost:8001',
      '/health': 'http://localhost:8001',
      '/projects': 'http://localhost:8001',
    },
  },
})
