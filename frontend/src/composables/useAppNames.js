import { ref } from 'vue'
import { api } from '../api/client'

// Résout un application_id vers son nom, pour les colonnes marquées { apps: true }
// d'EntityTable où la valeur est un tableau natif d'identifiants (uuid[]) — un audit
// cible plusieurs applications. Miroir de useOrgNames : chargé à la demande, une seule
// fois, et cloisonné RLS par l'API. Sans ce cache, une colonne applications afficherait
// des UUID bruts.
const cache = ref({}) // { id: nom }
let loaded = false
let loading = null

async function ensure() {
  if (loaded) return
  if (loading) { await loading; return }
  loading = (async () => {
    try {
      const rows = await api.list('applications')
      const list = Array.isArray(rows) ? rows : (rows?.items ?? [])
      const map = {}
      for (const a of list) map[a.id] = a.nom
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

export function useAppNames() {
  async function preload() { await ensure() }
  // Nom résolu, ou l'id brut si l'application n'est pas (ou pas encore) en cache.
  function appName(id) { return (id && cache.value[id]) || id }
  return { preload, appName }
}
