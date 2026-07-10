import { ref } from 'vue'
import { api } from '../api/client'

// Résout un ext_id de référentiel (ex. "CWE-79", "T1566") vers son nom lisible, et
// donne accès aux autres attributs de l'entrée (tactic pour ATT&CK, category pour
// D3FEND). Les catalogues sont chargés une fois puis mis en cache pour toute l'app.
const cache = ref({}) // { catalog: { ext_id: entry } } — entry = { ext_id, name, tactic?, category? }
const loading = {}

async function ensure(catalog) {
  if (cache.value[catalog]) return
  if (loading[catalog]) { await loading[catalog]; return }
  loading[catalog] = (async () => {
    try {
      const d = await api.get(`/reference/${catalog}/entries`)
      const map = {}
      for (const e of d.entries || []) map[e.ext_id] = e
      cache.value = { ...cache.value, [catalog]: map }
    } catch {
      cache.value = { ...cache.value, [catalog]: {} }
    }
  })()
  await loading[catalog]
}

export function useRefNames() {
  // Charge un ou plusieurs catalogues (à appeler au montage du composant).
  async function preload(catalogs) {
    await Promise.all(catalogs.map(ensure))
  }
  // Nom d'une entrée, ou l'ext_id brut si non résolu.
  function refName(catalog, extId) {
    if (!extId) return ''
    return cache.value[catalog]?.[extId]?.name || ''
  }
  // "T1566 — Phishing" (ou juste l'ext_id si le nom manque).
  function refLabel(catalog, extId) {
    const n = refName(catalog, extId)
    return n ? `${extId} — ${n}` : extId
  }
  // Entrée complète (ex. { ext_id, name, tactic } ou { ext_id, name, category }).
  function refMeta(catalog, extId) {
    return (extId && cache.value[catalog]?.[extId]) || null
  }
  return { preload, refName, refLabel, refMeta }
}
