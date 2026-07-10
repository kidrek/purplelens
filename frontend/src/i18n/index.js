import { createI18n } from 'vue-i18n'
import fr from './fr.json'
import en from './en.json'

// Interface bilingue (cahier : livrables FR/EN). FR par défaut.
export default createI18n({
  legacy: false,
  locale: 'fr',
  fallbackLocale: 'en',
  messages: { fr, en },
})
