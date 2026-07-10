import { ref } from 'vue'
import { api } from '../api/client'

// Résout un organisation_id vers son nom, sur TOUTES les organisations (client,
// prestataire, interne) — à la différence de ui.clients (store), qui ne contient
// que les organisations de rôle "client" pour le sélecteur global de périmètre.
// Sans ce composable, une Ressource rattachée à une organisation prestataire/interne
// affichait son UUID brut faute de correspondance dans ui.clients.
const cache = ref({}) // { id: nom }
let loaded = false
let loading = null

async function ensure() {
  if (loaded) return
  if (loading) { await loading; return }
  loading = (async () => {
    try {
      const rows = await api.list('organisations')
      const list = Array.isArray(rows) ? rows : (rows?.items ?? [])
      const map = {}
      for (const o of list) map[o.id] = o.nom
      cache.value = map
      loaded = true
    } catch {
      cache.value = {}
    } finally {
      loading = null
    }
  })()
  await loading
}

export function useOrgNames() {
  async function preload() { await ensure() }
  // Nom résolu, ou l'id brut si l'organisation n'est pas (ou pas encore) en cache.
  function orgName(id) { return (id && cache.value[id]) || id }
  return { preload, orgName }
}
