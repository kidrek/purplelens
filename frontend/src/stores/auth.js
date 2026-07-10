import { defineStore } from 'pinia'
import { api, ApiError } from '../api/client'

// L'état d'authentification reflète UNIQUEMENT ce que le serveur affirme via
// /auth/whoami. Le rôle et le périmètre client ne sont jamais décidés ni élevés
// côté client : ils servent seulement à masquer/afficher l'UI (le serveur reste
// l'autorité — un bouton masqué n'est pas une protection).
export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null,        // { user_id, email, role, client_scope, mfa, display_name }
    ready: false,      // whoami résolu au moins une fois
    stepUpNeeded: false,
  }),
  getters: {
    isAuthenticated: (s) => !!s.user,
    role: (s) => s.user?.role || null,
    isMultiClient: (s) => (s.user?.client_scope?.length ?? 0) === 0,
    scope: (s) => s.user?.client_scope || [],
  },
  actions: {
    async fetchMe() {
      try {
        this.user = await api.whoami()
      } catch (e) {
        this.user = null
        if (!(e instanceof ApiError && e.status === 401)) throw e
      } finally {
        this.ready = true
      }
    },
    async login(email, password, otp) {
      await api.login(email, password, otp)
      await this.fetchMe()
    },
    async logout() {
      try { await api.logout() } finally { this.user = null }
    },
  },
})
