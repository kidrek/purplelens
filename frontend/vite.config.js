import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Toutes les requêtes /api sont relayées vers le backend FastAPI
      '/api': 'http://localhost:8000',
    },
  },
})
