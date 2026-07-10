import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// En production, Nginx (reverse proxy unique) route /api, /storage et /idp.
// En dev, on proxifie vers l'API locale.
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/storage': { target: 'http://localhost:9000', changeOrigin: true },
    },
  },
  build: { outDir: 'dist', sourcemap: false },
})
