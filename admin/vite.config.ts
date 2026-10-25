import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// found. admin console. Talks to the same FastAPI backend, but only to /api/admin/* with its own login.
const backend = process.env.BACKEND_URL || 'http://127.0.0.1:8030'

export default defineConfig({
  base: '/admin/', // served at /admin by the backend (python run.py); dev: http://localhost:5186/admin/
  plugins: [react()],
  server: { port: 5186, strictPort: true, proxy: { '/api': backend } },
})
