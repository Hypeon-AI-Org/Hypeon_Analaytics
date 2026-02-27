import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': { target: 'http://localhost:8001', changeOrigin: true },
      '/insights': { target: 'http://localhost:8001', changeOrigin: true },
      '/recommendations': { target: 'http://localhost:8001', changeOrigin: true },
      '/copilot_query': { target: 'http://localhost:8001', changeOrigin: true },
      '/copilot': { target: 'http://localhost:8001', changeOrigin: true },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.js'],
    globals: true,
  },
})
