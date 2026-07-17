<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api, ApiError } from '../api/client'
import { icons } from '../icons'
const { t } = useI18n()

// Matrice ATT&CK multi-couches : tactiques en colonnes, techniques en cellules.
// 4 couches d'analyse changent la lecture des couleurs :
//   couverture — meilleur verdict défensif / nature de la couverture
//   détection  — détectée (réponse défensive) vs écart (jouée non détectée)
//   écart      — met en évidence les seuls écarts (jouées sans détection)
//   importée   — surligne les techniques d'une couche ATT&CK Navigator importée
// Données déjà cloisonnées RLS côté serveur.
const data = ref(null)
const loading = ref(true)
const error = ref(null)
const layer = ref('couverture')
const onlyCovered = ref(true) // ne montrer que tactiques/techniques couvertes (lecture facilitée)
const imported = ref(null) // Set d'ext_id importés (couche Navigator)
const expanded = ref(new Set()) // techniques parentes dépliées
const importName = ref('')
const importMsg = ref(null)

const VERDICT_LABEL = {
  prevented: 'Prévenu', alerted: 'Alerté', logged: 'Journalisé',
  no_telemetry: 'Sans télémétrie', not_tested: 'Non testé',
}
const LAYERS = [
  { id: 'couverture', label: 'Couverture' },
  { id: 'detection', label: 'Détection' },
  { id: 'ecart', label: 'Écart' },
  { id: 'importe', label: 'Importée' },
]

async function load() {
  loading.value = true; error.value = null
  try { data.value = await api.get('/analytics/attack-matrix') }
  catch (e) { error.value = e instanceof ApiError && e.status === 403 ? 'Accès refusé' : (e.message || 'Erreur') }
  finally { loading.value = false }
}
onMounted(load)

// Couleur d'une cellule selon la couche active.
function cellClass(t) {
  if (layer.value === 'detection') {
    if (!t.used) return 'untested'
    return t.detected ? 'detected' : 'gap'
  }
  if (layer.value === 'ecart') {
    return (t.used && !t.detected) ? 'gap' : 'muted'
  }
  if (layer.value === 'importe') {
    if (!imported.value) return 'muted'
    return imported.value.has(t.ext_id) ? 'inlayer' : 'muted'
  }
  // couverture (défaut)
  if (t.best_verdict) return 'v-' + t.best_verdict
  if (t.used) return 'touched'
  if (t.in_library) return 'library'
  return 'empty'
}
function cellTitle(t) {
  const parts = []
  if (t.steps) parts.push(`${t.steps} étape(s), verdict ${VERDICT_LABEL[t.best_verdict] || t.best_verdict}`)
  if (t.vulns) parts.push(`${t.vulns} vulnérabilité(s)`)
  if (t.tickets) parts.push(`${t.tickets} ticket(s)`)
  if (t.actions) parts.push(`${t.actions} action(s)`)
  if (t.scenarios) parts.push(`${t.scenarios} scénario(s)`)
  if (imported.value?.has(t.ext_id)) parts.push('dans la couche importée')
  return `${t.ext_id} — ${t.name || 'non référencée'}\n${parts.join(' · ') || 'jamais touchée'}`
}

const summary = computed(() => data.value?.summary || {})

// Une technique est « couverte » dès qu'elle porte une activité (jouée, en
// bibliothèque, ou avec un verdict) — ou qu'elle appartient à la couche importée.
function isCovered(t) {
  if (imported.value?.has(t.ext_id)) return true
  return !!(t.used || t.in_library || t.best_verdict)
}
// Tactiques (colonnes) affichées : filtrées sur les techniques couvertes quand le
// mode « Couvertes uniquement » est actif ; les colonnes vidées disparaissent.
const visibleTactics = computed(() => {
  const tactics = data.value?.tactics || []
  return tactics
    .map((c) => {
      const covered = c.techniques.filter(isCovered)
      return {
        ...c,
        coveredCount: covered.length,
        total: c.techniques.length,
        techniques: onlyCovered.value ? covered : c.techniques,
      }
    })
    .filter((c) => (onlyCovered.value ? c.techniques.length : true))
})

// Import d'une couche ATT&CK Navigator (fichier .json).
function onImportFile(ev) {
  const file = ev.target.files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    try {
      const layerJson = JSON.parse(reader.result)
      const techs = (layerJson.techniques || [])
        .map((x) => x.techniqueID || x.techniqueId)
        .filter(Boolean)
      if (!techs.length) { importMsg.value = { kind: 'ko', text: 'Aucune technique dans cette couche.' }; return }
      imported.value = new Set(techs)
      importName.value = layerJson.name || file.name
      layer.value = 'importe'
      importMsg.value = { kind: 'ok', text: `Couche « ${importName.value} » importée — ${techs.length} technique(s).` }
    } catch {
      importMsg.value = { kind: 'ko', text: 'Fichier de couche Navigator invalide (JSON attendu).' }
    }
  }
  reader.readAsText(file)
  ev.target.value = ''
}
function clearImport() { imported.value = null; importName.value = ''; if (layer.value === 'importe') layer.value = 'couverture' }

const importedCount = computed(() => imported.value?.size || 0)

function toggle(id) {
  const next = new Set(expanded.value)
  next.has(id) ? next.delete(id) : next.add(id)
  expanded.value = next
}
function expandAll() {
  const all = new Set()
  for (const c of data.value?.tactics || []) for (const t of c.techniques) if (t.sub_count) all.add(t.ext_id)
  expanded.value = all
}
function collapseAll() { expanded.value = new Set() }
</script>

<template>
  <div>
    <div class="eyebrow">{{ t('views.attack.eyebrow') }}</div>
    <h1>{{ t('views.attack.title') }}</h1>

    <p v-if="loading" class="muted">Chargement…</p>
    <p v-else-if="error" class="err">{{ error }}</p>

    <template v-else-if="data">
      <!-- KPIs 4 couches -->
      <div class="kpis">
        <div class="kpi"><div class="kv cov">{{ summary.covered }}</div><div class="kl">Couvertes</div><div class="ks">{{ summary.reference_total }} référencées</div></div>
        <div class="kpi"><div class="kv det">{{ summary.detected }}</div><div class="kl">Détectées</div><div class="ks">réponse défensive</div></div>
        <div class="kpi"><div class="kv gap">{{ summary.gaps }}</div><div class="kl">Écarts</div><div class="ks">jouées, non détectées</div></div>
        <div class="kpi"><div class="kv unt">{{ summary.untested }}</div><div class="kl">Non testées</div><div class="ks">jamais jouées</div></div>
      </div>

      <!-- Sélecteur de couche + import Navigator -->
      <div class="toolbar">
        <div class="layers">
          <button v-for="l in LAYERS" :key="l.id"
                  :class="['lbtn', { on: layer === l.id }]"
                  :disabled="l.id === 'importe' && !imported"
                  @click="layer = l.id">{{ l.label }}</button>
        </div>
        <div class="expand-ctl">
          <button :class="['btn', 'slim', { on: onlyCovered }]" @click="onlyCovered = !onlyCovered"
                  :title="onlyCovered ? 'Afficher toute la matrice référencée' : 'Masquer les techniques et tactiques non couvertes'">
            {{ onlyCovered ? '✓ Couvertes uniquement' : 'Couvertes uniquement' }}
          </button>
          <button class="btn slim" @click="expandAll">Tout déplier</button>
          <button class="btn slim" @click="collapseAll">Replier</button>
        </div>
        <div class="import">
          <label class="btn slim">
            Importer une couche Navigator
            <input type="file" accept="application/json,.json" @change="onImportFile" hidden />
          </label>
          <span v-if="imported" class="imp-tag">{{ importName }} · {{ importedCount }}
            <button class="x" @click="clearImport" title="Retirer">✕</button></span>
        </div>
      </div>
      <p v-if="importMsg" :class="['msg', importMsg.kind]">{{ importMsg.text }}</p>

      <!-- Légende contextuelle -->
      <div class="legend">
        <template v-if="layer === 'couverture'">
          <span class="lg"><span class="sw v-prevented"></span>Prévenu</span>
          <span class="lg"><span class="sw v-alerted"></span>Alerté</span>
          <span class="lg"><span class="sw v-logged"></span>Journalisé</span>
          <span class="lg"><span class="sw v-no_telemetry"></span>Sans télémétrie</span>
          <span class="lg"><span class="sw touched"></span>Vue (non exercée)</span>
          <span class="lg"><span class="sw library"></span>Bibliothèque</span>
          <span class="lg"><span class="sw empty"></span>Non touchée</span>
        </template>
        <template v-else-if="layer === 'detection'">
          <span class="lg"><span class="sw detected"></span>Détectée</span>
          <span class="lg"><span class="sw gap"></span>Écart (non détectée)</span>
          <span class="lg"><span class="sw untested"></span>Non testée</span>
        </template>
        <template v-else-if="layer === 'ecart'">
          <span class="lg"><span class="sw gap"></span>Écart de détection</span>
          <span class="lg"><span class="sw muted"></span>Hors écart</span>
        </template>
        <template v-else>
          <span class="lg"><span class="sw inlayer"></span>Dans la couche importée</span>
          <span class="lg"><span class="sw muted"></span>Hors couche</span>
        </template>
      </div>

      <!-- Grille -->
      <p v-if="onlyCovered && !visibleTactics.length" class="muted">
        Aucune technique couverte pour l'instant — désactivez « Couvertes uniquement » pour voir la matrice de référence.
      </p>
      <div v-else class="grid">
        <div v-for="col in visibleTactics" :key="col.tactic" class="col">
          <div class="col-head">
            <span class="tac">{{ col.tactic }}</span>
            <span class="tac-count">{{ col.coveredCount }} / {{ col.total }}</span>
          </div>
          <div class="cells">
            <template v-for="t in col.techniques" :key="t.ext_id">
              <div :class="['cell', cellClass(t)]" :title="cellTitle(t)">
                <div class="crow">
                  <div class="cid">{{ t.ext_id }}</div>
                  <button v-if="t.sub_count" class="subtoggle" @click.stop="toggle(t.ext_id)"
                          :title="expanded.has(t.ext_id) ? 'Replier' : 'Déplier les sous-techniques'">
                    {{ expanded.has(t.ext_id) ? '▾' : '▸' }} {{ t.sub_used ? t.sub_used + '/' : '' }}{{ t.sub_count }}
                  </button>
                </div>
                <div class="cname">{{ t.name || '—' }}</div>
                <div class="cbadges">
                  <span v-if="t.steps" class="badge"><span class="bico" v-html="icons.swords"></span>{{ t.steps }}</span>
                  <span v-if="t.vulns" class="badge"><span class="bico" v-html="icons.bug"></span>{{ t.vulns }}</span>
                  <span v-if="t.tickets" class="badge"><span class="bico" v-html="icons.ticket"></span>{{ t.tickets }}</span>
                  <span v-if="t.scenarios" class="badge"><span class="bico" v-html="icons.target"></span>{{ t.scenarios }}</span>
                </div>
              </div>
              <!-- Sous-techniques (dépliées) -->
              <template v-if="expanded.has(t.ext_id)">
                <div v-for="st in t.subtechniques" :key="st.ext_id"
                     :class="['cell', 'sub', cellClass(st)]" :title="cellTitle(st)">
                  <div class="cid sub-id">{{ st.ext_id }}</div>
                  <div class="cname">{{ st.name || '—' }}</div>
                  <div class="cbadges">
                    <span v-if="st.steps" class="badge"><span class="bico" v-html="icons.swords"></span>{{ st.steps }}</span>
                    <span v-if="st.vulns" class="badge"><span class="bico" v-html="icons.bug"></span>{{ st.vulns }}</span>
                    <span v-if="st.tickets" class="badge"><span class="bico" v-html="icons.ticket"></span>{{ st.tickets }}</span>
                    <span v-if="st.scenarios" class="badge"><span class="bico" v-html="icons.target"></span>{{ st.scenarios }}</span>
                  </div>
                </div>
              </template>
            </template>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:10px 0 14px}
.kpi{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-card);padding:12px 14px;text-align:center}
.kv{font-family:var(--font-data);font-size:26px;font-weight:600;line-height:1}
.kv.cov{color:var(--violet-accent)} .kv.det{color:var(--green)} .kv.gap{color:var(--red)} .kv.unt{color:var(--faint)}
.kl{font-size:12px;color:var(--heading);margin-top:3px;font-weight:600}
.ks{font-size:10.5px;color:var(--muted)}
.toolbar{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:10px}
.layers{display:inline-flex;border:1px solid var(--border);border-radius:var(--r-pill);overflow:hidden}
.lbtn{border:0;background:var(--surface);color:var(--muted);padding:6px 14px;font-size:12.5px;cursor:pointer}
.lbtn.on{background:var(--violet);color:#fff}
.lbtn:disabled{opacity:.4;cursor:not-allowed}
.import{display:flex;align-items:center;gap:8px}
.slim{padding:5px 10px;font-size:12px;cursor:pointer}
.imp-tag{font-size:11.5px;color:var(--violet-accent);font-family:var(--font-data);display:inline-flex;align-items:center;gap:6px}
.imp-tag .x{border:0;background:transparent;color:inherit;cursor:pointer}
.msg{font-size:12.5px;margin:2px 0 10px} .msg.ok{color:var(--green)} .msg.ko{color:var(--red)}
.legend{display:flex;flex-wrap:wrap;gap:14px;margin-bottom:14px;font-size:11px;color:var(--muted)}
.lg{display:flex;align-items:center;gap:5px}
.sw{width:12px;height:12px;border-radius:3px;display:inline-block;border:1px solid var(--border-2)}
/* Board — repris de la maquette (§ matrice ATT&CK, .atk-matrix) : cartes détachées
   arrondies sur --surface-2, en-tête sans fond souligné + compteur couvertes/total,
   teinte pleine par statut (fond + bordure + texte), hover qui soulève la carte. */
.grid{display:flex;gap:8px;overflow-x:auto;padding:4px 2px 10px;align-items:flex-start}
.col{flex:0 0 150px;min-width:150px;display:flex;flex-direction:column}
.col-head{padding:4px 4px 8px;border-bottom:2px solid var(--border);margin-bottom:7px}
.tac{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.02em;font-size:10.5px;font-weight:var(--eyebrow-weight);color:var(--heading);line-height:1.22;display:block}
.tac-count{font-family:var(--font-data);font-size:9.5px;color:var(--faint);margin-top:2px;display:block}
.cells{display:flex;flex-direction:column;gap:5px}
.cell{border:1px solid var(--border-2);border-radius:6px;padding:5px 7px;background:var(--surface-2);transition:transform var(--t-fast),box-shadow var(--t-fast)}
.cell:hover{transform:translateY(-1px);box-shadow:var(--shadow)}
.crow{display:flex;align-items:center;justify-content:space-between;gap:6px}
.cid{font-family:var(--font-data);font-size:9px;font-weight:700;opacity:.85;color:var(--heading)}
.subtoggle{border:0;background:var(--surface-3);color:var(--muted);border-radius:99px;font-size:9px;
  padding:0 6px;cursor:pointer;font-family:var(--font-data);line-height:1.6;white-space:nowrap}
.subtoggle:hover{background:var(--violet);color:#fff}
.cell.sub{margin-left:12px}
.sub-id{opacity:.7}
.expand-ctl{display:flex;gap:6px}
.expand-ctl .btn.on{background:var(--violet);color:#fff;border-color:var(--violet)}
.cname{font-size:10.5px;color:var(--muted);line-height:1.25;margin-top:1px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cbadges{display:flex;flex-wrap:wrap;gap:4px;margin-top:4px}
.badge{display:inline-flex;align-items:center;gap:3px;font-size:9.5px;color:var(--text);background:var(--surface-3);border-radius:var(--r-mini);padding:1px 5px}
.bico{display:inline-flex}
.badge :deep(svg){width:11px;height:11px;flex:0 0 auto;opacity:.85}
/* Teintes par statut — fond + bordure + couleur du texte (id/nom) */
.cell.v-prevented,.cell.detected{background:var(--c-green-bg);border-color:var(--c-green-bd)}
.cell.v-prevented .cid,.cell.v-prevented .cname,.cell.detected .cid,.cell.detected .cname{color:var(--c-green-tx)}
.cell.v-alerted{background:var(--c-cyan-bg);border-color:var(--c-cyan-bd)}
.cell.v-alerted .cid,.cell.v-alerted .cname{color:var(--c-cyan-tx)}
.cell.v-logged{background:var(--c-amber-bg);border-color:var(--c-amber-bd)}
.cell.v-logged .cid,.cell.v-logged .cname{color:var(--c-amber-tx)}
.cell.v-no_telemetry,.cell.gap{background:var(--c-red-bg);border-color:var(--c-red-bd)}
.cell.v-no_telemetry .cid,.cell.v-no_telemetry .cname,.cell.gap .cid,.cell.gap .cname{color:var(--c-red-tx)}
.cell.touched,.cell.inlayer{background:var(--c-violet-bg);border-color:var(--c-violet-bd)}
.cell.touched .cid,.cell.touched .cname,.cell.inlayer .cid,.cell.inlayer .cname{color:var(--c-violet-tx)}
.cell.library{background:var(--c-blue-bg);border-color:var(--c-blue-bd)}
.cell.library .cid,.cell.library .cname{color:var(--c-blue-tx)}
.cell.v-not_tested{border-color:var(--border-2)}
.cell.empty{opacity:.55}
.cell.untested{opacity:.5}
.cell.muted{opacity:.4}
.sw.v-prevented,.sw.detected{background:var(--green)} .sw.v-alerted{background:var(--cyan)}
.sw.v-logged{background:var(--amber)} .sw.v-no_telemetry,.sw.gap{background:var(--red)}
.sw.touched,.sw.inlayer{background:var(--violet)} .sw.library{background:var(--blue)}
.sw.empty,.sw.untested,.sw.muted{background:var(--surface-3)}
@media (max-width:820px){ .kpis{grid-template-columns:repeat(2,1fr)} }
</style>
