import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import VueI18nPlugin from '@intlify/unplugin-vue-i18n/vite'

// En production, Nginx (reverse proxy unique) route /api, /storage et /idp.
// En dev, on proxifie vers l'API locale.
export default defineConfig({
  plugins: [
    vue(),
    // PRÉCOMPILATION des messages i18n au build. vue-i18n, sinon, compile les chaînes
    // de traduction au RUNTIME via new Function() (JIT) — ce qui exige `unsafe-eval`
    // dans la CSP. Ce plugin transforme les fichiers de messages en messages déjà
    // compilés et alias vue-i18n vers son build « runtime-only » (sans compilateur) :
    // plus aucun new Function côté navigateur, donc CSP sans 'unsafe-eval'.
    //
    // IMPORTANT : `include` ne cible QUE les *.json (les ressources de messages), jamais
    // index.js (qui exporte le createI18n, pas un objet de messages) — sinon le plugin
    // tente de le précompiler et échoue (« define an object as the locale message »).
    VueI18nPlugin({
      include: [fileURLToPath(new URL('./src/i18n/**/*.json', import.meta.url))],
      strictMessage: false,
    }),
  ],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/storage': { target: 'http://localhost:9000', changeOrigin: true },
    },
  },
  build: { outDir: 'dist', sourcemap: false },
})
