import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      // Pipecat voice bot — WebRTC signaling (must come before /api catch-all)
      '/start':    { target: 'http://localhost:7860', changeOrigin: true },
      '/sessions': { target: 'http://localhost:7860', changeOrigin: true },
      '/api/offer': { target: 'http://localhost:7860', changeOrigin: true },
      // Agent CRUD REST API
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
