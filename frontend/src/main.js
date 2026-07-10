import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import i18n from './i18n'
import App from './App.vue'

// Polices de la DA, servies EN LOCAL (aucun CDN externe — outil auto-hébergé /
// hors-ligne). Sous-ensembles latin + latin-ext uniquement (couvrent FR/EN et les
// diacritiques), pour un déploiement léger. Poids alignés sur la maquette.
import '@fontsource/inter/latin-400.css'
import '@fontsource/inter/latin-500.css'
import '@fontsource/inter/latin-600.css'
import '@fontsource/inter/latin-ext-400.css'
import '@fontsource/inter/latin-ext-500.css'
import '@fontsource/inter/latin-ext-600.css'
import '@fontsource/poppins/latin-600.css'
import '@fontsource/poppins/latin-700.css'
import '@fontsource/space-grotesk/latin-500.css'
import '@fontsource/space-grotesk/latin-600.css'
import '@fontsource/space-grotesk/latin-700.css'
import '@fontsource/ibm-plex-mono/latin-400.css'
import '@fontsource/ibm-plex-mono/latin-500.css'
import '@fontsource/ibm-plex-mono/latin-600.css'

import './styles/tokens.css'
import './styles/base.css'
import './styles/corpus.css'

createApp(App).use(createPinia()).use(router).use(i18n).mount('#app')
