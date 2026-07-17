<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api/client'
import { useRefNames } from '../composables/useRefNames'
import { attackUrl } from '../utils/mitreLinks'

// Mini-matrice ATT&CK en LECTURE SEULE : générée automatiquement à partir des
// techniques sélectionnées (elles-mêmes dérivées des étapes offensives) — aucune
// interaction ici ne modifie la sélection, cf. constat « rendre cette section en
// lecture seule ». Thème repris de la maquette (badge + puces de tactique + grille).
const props = defineProps({
  techniques: { type: Array, default: () => [] },
  stepsCount: { type: Number, default: null }, // affiché dans le méta si fourni
  description: { type: String, default: '' }, // légende sous l'en-tête (source des techniques)
})
const { preload, refName } = useRefNames()
const attackEntries = ref([])

const TACTIC_ORDER = [
  'reconnaissance', 'resource-development', 'initial-access', 'execution',
  'persistence', 'privilege-escalation', 'defense-evasion', 'credential-access',
  'discovery', 'lateral-movement', 'collection', 'command-and-control',
  'exfiltration', 'impact',
]
const TACTIC_LABEL = {
  'reconnaissance': 'Reconnaissance', 'resource-development': 'Développement de ressources',
  'initial-access': 'Accès initial', 'execution': 'Exécution', 'persistence': 'Persistance',
  'privilege-escalation': 'Élévation de privilèges', 'defense-evasion': 'Évasion défensive',
  'credential-access': 'Accès aux identifiants', 'discovery': 'Découverte',
  'lateral-movement': 'Mouvement latéral', 'collection': 'Collecte',
  'command-and-control': 'Commande & contrôle', 'exfiltration': 'Exfiltration', 'impact': 'Impact',
}

onMounted(async () => {
  await preload(['attack'])
  try { attackEntries.value = (await api.get('/reference/attack/entries')).entries || [] }
  catch { attackEntries.value = [] }
})

function tacticOf(extId) {
  return attackEntries.value.find((e) => e.ext_id === extId)?.tactic || null
}

const matrix = computed(() => {
  const byTactic = {}
  for (const tq of props.techniques) {
    const tac = tacticOf(tq) || 'non-classée'
    ;(byTactic[tac] ||= []).push(tq)
  }
  // Colonnes ordonnées selon la kill-chain ATT&CK. IMPORTANT : on part des seaux
  // RÉELLEMENT présents (pas d'une liste blanche filtrée), pour ne JAMAIS écarter en
  // silence une technique dont la tactique serait absente de TACTIC_ORDER (libellé
  // inattendu, format différent, sous-technique hors socle) — elle est simplement
  // reléguée en fin. « non-classée » reste toujours la dernière colonne.
  const rank = (t) => {
    if (t === 'non-classée') return TACTIC_ORDER.length + 1
    const i = TACTIC_ORDER.indexOf(t)
    return i === -1 ? TACTIC_ORDER.length : i
  }
  return Object.keys(byTactic)
    .sort((a, b) => rank(a) - rank(b))
    .map((t) => ({ tactic: t, techniques: byTactic[t] }))
})
const tacticCount = computed(() => matrix.value.length)
// Nombre de lignes du tableau = la colonne (tactique) qui porte le plus de techniques ;
// les autres colonnes ont des cellules vides au-delà de leur propre nombre.
const rowCount = computed(() => Math.max(0, ...matrix.value.map((c) => c.techniques.length)))
</script>

<template>
  <div class="panel-card">
    <div class="panel-head">
      <div class="panel-title"><span class="badge badge-red">ATT&CK</span>TTPs ATT&CK</div>
      <div class="panel-meta">
        <span v-if="stepsCount !== null">{{ stepsCount }} étape(s) · </span>{{ tacticCount }} tactique(s)
      </div>
    </div>
    <p v-if="description" class="matrix-desc">{{ description }}</p>
    <div v-if="matrix.length" class="matrix-scroll">
      <table class="ttp-table">
        <thead>
          <tr>
            <th v-for="col in matrix" :key="col.tactic">{{ (TACTIC_LABEL[col.tactic] || col.tactic).toUpperCase() }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rowCount" :key="row">
            <td v-for="col in matrix" :key="col.tactic">
              <a v-if="col.techniques[row - 1]" :href="attackUrl(col.techniques[row - 1])" target="_blank" rel="noopener noreferrer"
                 class="tech-cell" :title="'Voir ' + col.techniques[row - 1] + ' sur attack.mitre.org'">
                <div class="tech-id">{{ col.techniques[row - 1] }}</div>
                <div class="tech-name">{{ refName('attack', col.techniques[row - 1]) || col.techniques[row - 1] }}</div>
              </a>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <span v-else class="faint">Aucune technique — générée automatiquement depuis les étapes offensives.</span>
  </div>
</template>

<style scoped>
.panel-card{background:var(--surface-2);border:1px solid var(--border);border-radius:var(--r-card);padding:16px}
.panel-head{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:14px}
.panel-title{display:flex;align-items:center;gap:9px;font-family:var(--font-display);font-weight:600;color:var(--heading);font-size:14px}
.panel-meta{font-size:11.5px;color:var(--faint)}
.matrix-desc{font-size:11.5px;color:var(--faint);margin:0 0 12px;line-height:1.4}
.badge{font-family:var(--font-data);font-size:10px;font-weight:700;border-radius:var(--r-mini);padding:3px 7px;letter-spacing:.02em}
.badge-red{background:var(--c-red-bg);color:var(--c-red-tx);border:1px solid var(--c-red-bd)}

.matrix-scroll{overflow-x:auto}
.ttp-table{border-collapse:separate;border-spacing:0 8px;width:100%;table-layout:fixed}
.ttp-table th{text-align:left;font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.03em;
  font-size:10px;color:var(--c-violet-tx);font-weight:var(--eyebrow-weight);padding:8px 10px;
  background:transparent;border:1px solid var(--c-violet-bd);border-radius:var(--r-pill);
  white-space:normal;line-height:1.25}
.ttp-table thead tr{display:flex;gap:8px}
/* display:flex + align-items:center → libellés courts centrés dans la hauteur commune ;
   la hauteur d'en-tête reste identique sur toutes les colonnes (stretch des items flex). */
.ttp-table th{flex:1;min-width:150px;display:flex;align-items:center}
.ttp-table tbody tr{display:flex;gap:8px}
.ttp-table td{flex:1;min-width:150px;padding:0;vertical-align:top}
.tech-cell{display:block;background:var(--surface-3);border:1px solid var(--border);border-radius:var(--r-mini);
  padding:9px 11px;text-decoration:none;cursor:pointer;box-shadow:var(--shadow)}
.tech-cell:hover{border-color:var(--violet-accent);background:var(--surface)}
.tech-id{font-family:var(--font-data);font-size:11px;font-weight:700;color:var(--c-violet-tx)}
.tech-name{font-size:10.5px;color:var(--text);margin-top:3px}
</style>
