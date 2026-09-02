import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      // Forward WebRTC signaling to the pipecat backend
      '/api': { target: 'http://localhost:7860', changeOrigin: true },
    },
  },
})
