import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// /api is forwarded to the FastAPI backend (run from backend/: uvicorn main:app --reload --port 8030).
const backend = process.env.BACKEND_URL || 'http://127.0.0.1:8030'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5185,
    strictPort: true,
    proxy: { '/api': backend },
  },
})
