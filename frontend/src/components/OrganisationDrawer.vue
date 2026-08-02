<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api } from '../api/client'
import DetailDrawer from './DetailDrawer.vue'
import CompanionPanel from './CompanionPanel.vue'
import { useLabels } from '../composables/useLabels'
import { provideDrawerPair } from '../composables/useDrawerPair'
import { SEVERITE_TONE, STATUT_EXO_TONE } from '../tones'

// Drawer de détail d'une Organisation (60 %, cf. correctif largeur EntityDrawer).
// En plus des méta-données, affiche en lecture seule (cahier « constats » Organisations) :
//   - la liste des personnes rattachées,
//   - les exercices Purple (un par audit : le RUN courant),
//   - les derniers audits (les plus récents en premier),
//   - les dernières vulnérabilités (avec renvoi vers la page dédiée pour l'exhaustivité).
// Prop nommée "record" : contrat générique utilisé par EntityTable pour tout composant
// passé via :drawer="..." (cf. AuditDrawer / ScenarioDrawer).
//
// Ce tiroir est HÔTE d'appairage : cliquer une personne, un exercice, un audit ou une
// vulnérabilité ouvre son tiroir en lecture seule à GAUCHE de celui-ci, sans navigation
// (cf. composables/useDrawerPair.js et components/CompanionPanel.vue).
//
// CONTRAT DE LECTURE (assumé, et énoncé dans l'UI sous les tuiles) :
//   - les TUILES affichent les totaux exacts du périmètre — `total` renvoyé par l'API,
//     calculé par un COUNT(*) avant pagination (cf. api/service.py::list_entities) ;
//   - les LISTES n'affichent que les MAX_ROWS éléments les plus récents, lus dans une
//     fenêtre de PAGE enregistrements.
// Les deux chiffres divergent donc dès qu'une organisation dépasse MAX_ROWS : c'est voulu,
// ce tiroir est une fiche de synthèse, pas une vue exhaustive.
const props = defineProps({ record: { type: Object, required: true } })
const emit = defineEmits(['close', 'edit'])
const { fieldLabel, enumLabel } = useLabels()

// Doit être appelé pendant le setup, avant celui des DetailDrawer descendants.
provideDrawerPair()

// Panneau compagnon ouvert à gauche : { kind: 'ressource'|'exercice'|'audit'|'vuln', record }.
const companion = ref(null)
function openCompanion(kind, record) { companion.value = { kind, record } }

const o = computed(() => props.record)
const ressources = ref([])
const exercices = ref([])
const runsByAudit = ref({})
const audits = ref([])
const vulnerabilities = ref([])
// Totaux exacts du périmètre, alimentant les tuiles (cf. contrat de lecture ci-dessus).
const totals = ref({ ressources: 0, exercices: 0, audits: 0, vulns: 0 })
const loading = ref(true)

// Les tons de pills viennent de tones.js — source unique partagée avec le tiroir Personne,
// sans quoi un même statut d'audit s'afficherait dans deux couleurs selon le tiroir.

const MAX_ROWS = 10  // lignes affichées par liste
const PAGE = 50      // fenêtre lue côté serveur

const unwrap = (d) => (Array.isArray(d) ? d : (d?.items ?? []))

// Première page + total. Convient aux entités triées par nom (personnes) : la « queue »
// d'une liste alphabétique n'aurait aucun sens.
async function pagedHead(entity, q) {
  try {
    const res = await api.list(entity, `${q}&limit=${PAGE}`)
    return { items: unwrap(res), total: res?.total ?? unwrap(res).length }
  } catch { return { items: [], total: 0 } }
}

// Queue de liste. Le serveur trie created_at ASCENDANT par défaut (EntitySpec.order_by) :
// demander la première page renverrait les enregistrements les plus ANCIENS. On lit donc
// `total` puis, s'il dépasse la fenêtre, on redemande les PAGE derniers via offset.
// Un seul aller-retour dans le cas courant, deux seulement quand ça change le résultat.
async function pagedTail(entity, q) {
  try {
    const first = await api.list(entity, `${q}&limit=${PAGE}`)
    const total = first?.total ?? unwrap(first).length
    if (total <= PAGE) return { items: unwrap(first), total }
    const tail = await api.list(entity, `${q}&limit=${PAGE}&offset=${total - PAGE}`)
    return { items: unwrap(tail), total }
  } catch { return { items: [], total: 0 } }
}

// Champs méta affichés (schéma volontairement réduit et lisible — pas de refpick ici).
const META_FIELDS = [
  { key: 'code', label: 'Code' },
  { key: 'role', label: 'Rôle' },
  { key: 'secteur', label: "Secteur d'activité" },
  { key: 'referent_interne', label: 'Référent interne' },
  { key: 'siren', label: 'SIREN' },
  { key: 'statut', label: 'Statut' },
  { key: 'commentaires', label: 'Commentaires' },
]
const metaRows = computed(() => META_FIELDS.filter((f) => o.value[f.key]))

function auditDate(a) { return a.date_debut || a.created_at || '' }
const byDateDesc = (get) => (a, b) => (get(b) || '').localeCompare(get(a) || '')

async function loadAll() {
  loading.value = true
  const id = o.value.id
  try {
    const [ress, exos, auds, vulnsRes] = await Promise.all([
      pagedHead('ressources', `?organisation_id=${id}`),
      pagedTail('exercices', `?client_id=${id}`),
      pagedTail('audits', `?client_id=${id}`),
      api.get('/vulnerabilities-enriched').catch(() => ({ items: [] })),
    ])

    ressources.value = ress.items
    audits.value = [...auds.items].sort(byDateDesc(auditDate))

    // Un audit porte plusieurs RUNs et ExerciceDrawer déroule DÉJÀ tous les RUNs de
    // l'audit : on replie donc sur le RUN courant (run_number max), comme le mode groupé
    // de /exercices — sinon N lignes ouvriraient le même tableau de bord.
    // Le décompte de RUNs par audit porte sur la fenêtre lue, pas sur le total serveur.
    const byAudit = {}
    const runs = {}
    for (const e of exos.items) {
      const k = e.audit_id || e.id
      runs[k] = (runs[k] ?? 0) + 1
      if (!byAudit[k] || (e.run_number ?? 0) > (byAudit[k].run_number ?? 0)) byAudit[k] = e
    }
    runsByAudit.value = runs
    exercices.value = Object.values(byAudit).sort(byDateDesc((e) => e.date || e.created_at || ''))

    vulnerabilities.value = unwrap(vulnsRes)
      .filter((v) => v.client_id === id)
      .sort(byDateDesc((v) => v.created_at || ''))

    totals.value = {
      ressources: ress.total,
      // Seul compteur qui ne peut pas venir de `total` : le serveur compte des RUNs, la
      // liste affiche des audits. On compte donc les audits repliés de la fenêtre.
      exercices: exercices.value.length,
      audits: auds.total,
      // /vulnerabilities-enriched n'est pas paginé : le filtre client donne le total exact.
      vulns: vulnerabilities.value.length,
    }
  } finally {
    loading.value = false
  }
}

// Nombre de RUNs de l'audit d'un exercice (≥ 2 → affiché en suffixe de la pastille RUN).
function runCount(e) { return runsByAudit.value[e.audit_id || e.id] ?? 1 }
onMounted(loadAll)
</script>

<template>
  <DetailDrawer :title="o.nom" subtitle="Organisation" wide @close="emit('close')">
    <template #actions>
      <button class="btn slim" @click="emit('edit', o)">{{ $t('common.edit') }}</button>
    </template>

    <div class="badges">
      <span v-if="o.role" class="pill pill-violet">{{ enumLabel(o.role) }}</span>
      <span v-if="o.statut" class="pill pill-gray">{{ enumLabel(o.statut) }}</span>
      <span v-if="o.tlp_defaut" :class="['tlp', 'tlp-' + o.tlp_defaut]">TLP:{{ o.tlp_defaut }}</span>
    </div>

    <!-- Tuiles = totaux du périmètre ; les listes plus bas sont tronquées à MAX_ROWS.
         La note explicite cet écart, sans quoi il passerait pour une incohérence. -->
    <div class="tiles">
      <div class="tile"><b>{{ totals.ressources }}</b><span>Personnes</span></div>
      <div class="tile"><b>{{ totals.exercices }}</b><span>Exercices</span></div>
      <div class="tile"><b>{{ totals.audits }}</b><span>Audits</span></div>
      <div class="tile"><b>{{ totals.vulns }}</b><span>Vulnérabilités</span></div>
    </div>
    <p class="tiles-note">
      Compteurs : totaux du périmètre de l'organisation. Listes : les {{ MAX_ROWS }} éléments les plus récents.
    </p>

    <section class="sec">
      <dl class="dl">
        <template v-for="f in metaRows" :key="f.key">
          <dt>{{ fieldLabel(f) }}</dt>
          <dd>{{ enumLabel(o[f.key]) }}</dd>
        </template>
      </dl>
      <div v-if="o.tags?.length" class="tags"><span v-for="tg in o.tags" :key="tg" class="chip">{{ tg }}</span></div>
    </section>

    <p v-if="loading" class="faint">Chargement…</p>

    <template v-else>
      <!-- Personnes de l'organisation (ordre alphabétique du serveur) -->
      <section class="sec">
        <div class="sec-t">Personnes ({{ totals.ressources }})</div>
        <!-- RessourceDrawer ne recharge pas la personne par id : on passe la ligne complète. -->
        <ul v-if="ressources.length" class="list">
          <li v-for="r in ressources.slice(0, MAX_ROWS)" :key="r.id" class="clickable" @click="openCompanion('ressource', r)">
            <span class="rn link">{{ r.nom }}</span>
            <span v-if="r.role" class="pill pill-violet sm">{{ enumLabel(r.role) }}</span>
            <span class="faint sm">{{ r.contact || '—' }}</span>
          </li>
        </ul>
        <div v-else class="empty">Aucune personne rattachée pour l'instant.</div>
        <div v-if="totals.ressources > MAX_ROWS" class="more faint sm">
          + {{ totals.ressources - MAX_ROWS }} autre(s) personne(s)
        </div>
      </section>

      <!-- Exercices Purple : une ligne par audit (RUN courant) -->
      <section class="sec">
        <div class="sec-t">Exercices Purple ({{ totals.exercices }})</div>
        <!-- ExerciceDrawer pivote sur audit_id / client_id : lui passer l'enregistrement
             COMPLET, pas seulement l'id (cf. CompanionPanel). -->
        <ul v-if="exercices.length" class="list">
          <li v-for="e in exercices.slice(0, MAX_ROWS)" :key="e.id" class="clickable" @click="openCompanion('exercice', e)">
            <span class="rn link">{{ e.nom }}</span>
            <span class="pill pill-violet sm">RUN {{ e.run_number ?? '—' }}{{ runCount(e) > 1 ? ` · ${runCount(e)} runs` : '' }}</span>
            <span v-if="e.statut" :class="['pill', 'sm', 'pill-' + (STATUT_EXO_TONE[e.statut] || 'gray')]">{{ enumLabel(e.statut) }}</span>
            <span class="faint sm">{{ e.date || '—' }}</span>
          </li>
        </ul>
        <div v-else class="empty">Aucun exercice Purple pour cette organisation pour l'instant.</div>
        <div v-if="totals.exercices > MAX_ROWS" class="more faint sm">
          + {{ totals.exercices - MAX_ROWS }} exercice(s) plus ancien(s)
        </div>
      </section>

      <!-- Derniers audits -->
      <section class="sec">
        <div class="sec-t">Derniers audits ({{ totals.audits }})</div>
        <ul v-if="audits.length" class="list">
          <li v-for="a in audits.slice(0, MAX_ROWS)" :key="a.id" class="clickable" @click="openCompanion('audit', { id: a.id })">
            <span class="rn link">{{ a.nom }}</span>
            <span v-if="a.statut" :class="['pill', 'sm', 'pill-' + (STATUT_EXO_TONE[a.statut] || 'gray')]">{{ enumLabel(a.statut) }}</span>
            <span class="faint sm">{{ auditDate(a) || '—' }}</span>
          </li>
        </ul>
        <div v-else class="empty">Aucun audit pour cette organisation pour l'instant.</div>
        <div v-if="totals.audits > MAX_ROWS" class="more faint sm">
          + {{ totals.audits - MAX_ROWS }} audit(s) plus ancien(s)
        </div>
      </section>

      <!-- Dernières vulnérabilités -->
      <section class="sec">
        <div class="sec-t">Dernières vulnérabilités ({{ totals.vulns }})</div>
        <ul v-if="vulnerabilities.length" class="list">
          <li v-for="v in vulnerabilities.slice(0, MAX_ROWS)" :key="v.id" class="clickable" @click="openCompanion('vuln', { id: v.id })">
            <span class="rn link">{{ v.titre || v.cve || '—' }}</span>
            <span v-if="v.severite" :class="['pill', 'sm', 'pill-' + (SEVERITE_TONE[v.severite] || 'gray')]">{{ enumLabel(v.severite) }}</span>
            <span class="faint sm">{{ v.statut ? enumLabel(v.statut) : '—' }}</span>
          </li>
        </ul>
        <div v-else class="empty">Aucune vulnérabilité pour cette organisation pour l'instant.</div>
        <div v-if="totals.vulns > MAX_ROWS" class="more faint sm">
          + {{ totals.vulns - MAX_ROWS }} vulnérabilité(s) plus ancienne(s)
        </div>
        <!-- Seule navigation conservée : la liste exhaustive, pré-filtrée sur cette
             organisation (VulnerabilitiesView amorce fClients depuis ?client_id). -->
        <RouterLink :to="{ path: '/vulnerabilities', query: { client_id: o.id } }" class="more-link">
          Voir toutes les vulnérabilités de {{ o.nom }} →
        </RouterLink>
      </section>
    </template>
  </DetailDrawer>

  <!-- Panneau compagnon, monté en frère : son teleport le sort du DOM de ce tiroir, mais
       il reste un descendant de composant, ce qui lui fait hériter du registre d'appairage. -->
  <CompanionPanel
    v-if="companion"
    :companion="companion"
    @open="companion = $event"
    @close="companion = null"
  />
</template>

<style scoped>
.slim{padding:3px 9px;font-size:11.5px}
.badges{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px}
/* Bande de tuiles chiffrées — même géométrie que le tiroir Personne. */
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:10px}
.tile{background:var(--surface-2);border:1px solid var(--border);border-radius:var(--r-card);padding:10px 12px}
.tile b{display:block;font-family:var(--font-data);font-size:24px;font-weight:600;color:var(--heading);line-height:1.15}
.tile span{font-size:11px;color:var(--muted)}
.tiles-note{margin:6px 0 18px;font-size:11px;color:var(--faint);line-height:1.45}
.sec{margin-bottom:18px}
.sec-t{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.05em;font-size:10.5px;color:var(--faint);font-weight:var(--eyebrow-weight);margin-bottom:8px;padding-bottom:5px;border-bottom:1px solid var(--border-2)}
.dl{display:grid;grid-template-columns:150px 1fr;gap:8px 14px;margin:0 0 8px;font-size:13px}
.dl dt{color:var(--muted)} .dl dd{margin:0;color:var(--text);word-break:break-word}
.tags{display:flex;flex-wrap:wrap;gap:5px}
/* Géométrie du .chip normatif (base.css §0.3) : centre le texte quels que soient les jambages. */
.chip{display:inline-flex;align-items:center;height:22px;padding:0 9px;line-height:1;white-space:nowrap;
  background:var(--surface-3);border:1px solid var(--border-2);border-radius:var(--r-pill);font-size:11.5px}
.empty{font-size:12px;color:var(--muted);background:var(--surface-2);border:1px solid var(--border);border-radius:var(--r-mini);padding:9px 12px}
.list{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:6px}
.list li{display:flex;align-items:center;gap:8px;font-size:12.5px;padding:6px 8px;border:1px solid var(--border);border-radius:var(--r-mini);background:var(--surface-2);box-shadow:var(--shadow)}
.rn{flex:1;color:var(--heading);font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
/* Toute la ligne ouvre le tiroir appairé — cible de clic plus large qu'un simple lien. */
.list li.clickable{cursor:pointer;transition:border-color var(--t) var(--ease)}
.list li.clickable:hover{border-color:var(--violet)}
.list li.clickable:hover .rn.link{color:var(--violet-accent)}
.sm{font-size:10.5px;flex:0 0 auto}
.faint{color:var(--faint)}
.more{margin-top:6px}
.more-link{display:inline-block;margin-top:8px;font-size:12px;color:var(--violet-accent);text-decoration:none}
.more-link:hover{text-decoration:underline}
</style>
