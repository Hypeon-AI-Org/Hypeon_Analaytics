import path from 'path'
import { fileURLToPath } from 'url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [react()],
  // Load .env from repo root so VITE_API_KEY, VITE_FIREBASE_*, etc. are available (single .env for backend + frontend)
  envDir: path.resolve(__dirname, '..'),
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
