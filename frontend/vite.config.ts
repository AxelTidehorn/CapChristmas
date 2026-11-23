import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Dev server proxies the API to the local FastAPI backend; production is served by FastAPI itself.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
})
