import { ref } from 'vue'
import { api, ApiError } from '../api/client'

// Corpus méthodologique (Bibliothèque, DA v2.7 §4). Chargé une fois puis mis en
// cache pour toute l'app : la liste est petite (quelques dizaines d'articles,
// seedée au démarrage) et sert à la fois la page Bibliothèque, la palette ⌘K
// et les boutons contextuels « Corpus » des drawers Scénario/Vulnérabilité (§4.6).
const rows = ref([])
const loaded = ref(false)
const error = ref(null)
let loading = null

async function ensureLoaded() {
  if (loaded.value) return
  if (loading) { await loading; return }
  loading = (async () => {
    try {
      const d = await api.list('corpus', '?limit=500')
      rows.value = (Array.isArray(d) ? d : (d?.items ?? []))
        .sort((a, b) => (a.slug || '').localeCompare(b.slug || ''))
      loaded.value = true
    } catch (e) {
      error.value = e instanceof ApiError && e.status === 403 ? 'Accès refusé' : (e.message || 'Erreur')
    }
  })()
  await loading
}

// Couleur par nature (DA §4.0, réemploi strict) : procédure = ambre, processus = cyan, article métier = violet.
const NATURE_TONE = { procedure: 'amber', processus: 'cyan', metier: 'violet' }

// Type d'affichage (DA §4.1 : "Gabarit exportable" / "Méthodologie" / "Mapping conformité").
// Porté par la donnée depuis l'enrichissement du seed (contenu.type, repris de la
// maquette) ; l'heuristique gabarit+nature ne sert plus que de repli.
function corpusType(article) {
  if (article?.contenu?.type) return article.contenu.type
  if (article?.gabarit) return 'gabarit'
  return article?.nature === 'metier' ? 'mapping' : 'methodo'
}

// tr(v) : rend une valeur bilingue {fr,en} dans la langue demandée (repli fr, puis en).
function tr(v, locale) {
  if (v && typeof v === 'object' && ('fr' in v || 'en' in v)) {
    return v[locale] || v.fr || v.en || ''
  }
  return v ?? ''
}

export function useCorpus() {
  function corpusById(id) { return rows.value.find((r) => r.id === id) || null }
  function corpusBySlug(slug) { return rows.value.find((r) => r.slug === slug) || null }
  function natureTone(nature) { return NATURE_TONE[nature] || 'gray' }
  return {
    corpusRows: rows, corpusLoaded: loaded, corpusError: error,
    preloadCorpus: ensureLoaded, corpusById, corpusBySlug, natureTone, corpusType, tr,
  }
}
