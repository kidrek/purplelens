import { computed, ref, watch } from 'vue'

// Tri par en-têtes cliquables, mémorisé par navigateur.
//
// Cycle sur clic : 1er = croissant, 2e = décroissant, 3e = retour à l'ordre serveur
// (`sortKey` à null). L'ordre serveur est le tri par défaut du registre d'entités
// (backend/app/api/registry.py) — ex. scénario le plus récent en tête : on ne le
// duplique donc pas côté client.
//
// La préférence est stockée dans localStorage sous `table.<entity>.sort` et effacée
// dès le retour au défaut : aucune préférence fantôme ne survit à la réinitialisation.

const storeKey = (entity) => `table.${entity}.sort`

// Comparateur naturel : `numeric` classe SCEN_…-100 après SCEN_…-99 (et non avant,
// comme le ferait un tri lexicographique) ; `sensitivity: 'base'` ignore casse et
// accents, indispensable sur des libellés français.
function collatorFor(locale) {
  return new Intl.Collator(locale || 'fr', { numeric: true, sensitivity: 'base' })
}

// Vide = null, undefined, chaîne vide ou tiret cadratin (valeur affichée par défaut).
const isEmpty = (v) => v == null || v === '' || v === '—'

// Départage stable : à valeur égale, le plus récemment créé d'abord, puis l'id — sans
// quoi deux lignes équivalentes peuvent permuter d'un rendu à l'autre.
function tieBreak(a, b) {
  const ta = new Date(a?.created_at || 0).getTime() || 0
  const tb = new Date(b?.created_at || 0).getTime() || 0
  if (ta !== tb) return tb - ta
  return String(a?.id || '').localeCompare(String(b?.id || ''))
}

/**
 * @param {import('vue').Ref<string>|{value:string}} entity  entité (clé de stockage)
 * @param {() => string[]} knownKeys  clés de colonne actuellement affichées
 * @param {{ value: string }} locale  locale i18n (recalcul du comparateur au changement)
 */
export function useTableSort(entity, knownKeys, locale) {
  const sortKey = ref(null)
  const sortDir = ref('asc')

  // Restauration : une préférence portant sur une colonne disparue (schéma de colonnes
  // modifié entre deux versions) est ignorée plutôt que d'imposer un tri invisible.
  function restore() {
    sortKey.value = null
    sortDir.value = 'asc'
    try {
      const raw = localStorage.getItem(storeKey(entity.value))
      if (!raw) return
      const { key, dir } = JSON.parse(raw)
      if (key && knownKeys().includes(key)) {
        sortKey.value = key
        sortDir.value = dir === 'desc' ? 'desc' : 'asc'
      }
    } catch { /* stockage indispo ou valeur illisible : ordre par défaut */ }
  }

  function persist() {
    try {
      if (sortKey.value) {
        localStorage.setItem(storeKey(entity.value), JSON.stringify({ key: sortKey.value, dir: sortDir.value }))
      } else {
        localStorage.removeItem(storeKey(entity.value))
      }
    } catch { /* ignore */ }
  }

  function toggleSort(key) {
    if (sortKey.value !== key) { sortKey.value = key; sortDir.value = 'asc' }
    else if (sortDir.value === 'asc') { sortDir.value = 'desc' }
    else { sortKey.value = null; sortDir.value = 'asc' }
    persist()
  }

  // État ARIA de l'en-tête (lecteurs d'écran) — miroir de l'indicateur ▲/▼.
  function ariaSort(key) {
    if (sortKey.value !== key) return 'none'
    return sortDir.value === 'asc' ? 'ascending' : 'descending'
  }

  const collator = computed(() => collatorFor(locale?.value))

  /**
   * Trie une copie des lignes. `sortValue(row)` renvoie la valeur de tri de la colonne
   * active : un nombre (dates, valeurs numériques) ou un texte (libellé affiché).
   * Les valeurs vides sont toujours reléguées en fin, quel que soit le sens.
   */
  function applySort(rows, sortValue) {
    if (!sortKey.value) return rows
    const dir = sortDir.value === 'desc' ? -1 : 1
    return [...rows].sort((a, b) => {
      const va = sortValue(a)
      const vb = sortValue(b)
      const ea = isEmpty(va)
      const eb = isEmpty(vb)
      if (ea || eb) return ea && eb ? tieBreak(a, b) : (ea ? 1 : -1)
      const c = (typeof va === 'number' && typeof vb === 'number')
        ? va - vb
        : collator.value.compare(String(va), String(vb))
      return c ? c * dir : tieBreak(a, b)
    })
  }

  watch(() => entity.value, restore, { immediate: true })

  return { sortKey, sortDir, toggleSort, ariaSort, applySort, restore }
}
