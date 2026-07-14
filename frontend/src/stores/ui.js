import { defineStore } from 'pinia'

// Préférences d'affichage. Le thème (A clair / B SOC sombre) est piloté par
// body[data-theme="light"|"dark"] conformément à la DA.
export const useUiStore = defineStore('ui', {
  state: () => ({
    theme: 'dark',
    activeClient: null, // id du client filtré (rôles multi-clients)
    clients: [], // organisations client accessibles
    toast: null,
    articleSlug: null, // article corpus ouvert en drawer global (⌘K), sans navigation
  }),
  getters: {
    // Suffixe de requête pour filtrer par client actif (ou chaîne vide).
    clientQuery: (s) => (s.activeClient ? `client_id=${s.activeClient}` : ''),
  },
  actions: {
    setTheme(t) {
      const norm = t === 'A' ? 'light' : t === 'B' ? 'dark' : t
      this.theme = norm
      document.body.setAttribute('data-theme', norm)
    },
    toggleTheme() {
      this.setTheme(this.theme === 'dark' ? 'light' : 'dark')
    },
    setClients(list) { this.clients = list },
    openArticle(slug) { this.articleSlug = slug },
    closeArticle() { this.articleSlug = null },
    setActiveClient(id) { this.activeClient = id || null },
    notify(message, kind = 'info') {
      this.toast = { message, kind, at: Date.now() }
    },
  },
})
