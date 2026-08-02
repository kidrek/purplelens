<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api/client'
import DetailDrawer from './DetailDrawer.vue'
import CompanionPanel from './CompanionPanel.vue'
import { useLabels } from '../composables/useLabels'
import { useOrgNames } from '../composables/useOrgNames'
import { provideDrawerPair } from '../composables/useDrawerPair'
import { competencesForRole } from '../fields'
import { SEVERITE_TONE, STATUT_EXO_TONE } from '../tones'

// Drawer de détail d'une Personne (ressource humaine), en remplacement d'EntityDrawer
// générique sur la page /ressources : le rendu à plat du schéma fields.js ne hiérarchisait
// rien et n'exposait aucun des liens qui font l'intérêt d'une fiche — sur quoi la personne
// intervient et ce qu'elle a trouvé.
//
// Le registre (registry.py) ne propose pas de filtre serveur « par personne » : audits et
// vulnérabilités sont rapatriés à l'échelle de l'organisation puis filtrés côté client,
// comme le fait déjà OrganisationDrawer. Le cloisonnement reste garanti serveur (RLS +
// porte 4).
//
// Cliquer un audit / exercice / vulnérabilité n'entraîne AUCUNE navigation : le tiroir de
// l'élément s'ouvre en panneau appairé, à gauche de cette fiche (cf. useDrawerPair.js).
//
// Fiche bi-rôle :
//   - HÔTE sur /ressources — elle ouvre ses propres compagnons à gauche ;
//   - COMPAGNON quand on l'ouvre depuis une organisation (`readonly`) — elle n'a plus de
//     bouton d'en-tête et fait remonter ses liens à l'hôte, qui la remplace en place.
const props = defineProps({
  record: { type: Object, required: true },
  readonly: { type: Boolean, default: false },
})
const emit = defineEmits(['close', 'edit', 'open-entity'])

const { t } = useI18n()
const { enumLabel } = useLabels()
const { preload: preloadOrgs, orgName } = useOrgNames()

// Doit être appelé pendant le setup, avant celui des DetailDrawer descendants — mais
// SEULEMENT en hôte. En compagnon, créer un registre local ferait s'enregistrer notre
// propre DetailDrawer à l'index 0 : il se superposerait au tiroir hôte au lieu de se
// placer à sa gauche. Sans provider ici, l'injection remonte au registre de l'hôte.
if (!props.readonly) provideDrawerPair()

const r = computed(() => props.record)
const audits = ref([])
const vulnerabilities = ref([])
const exercices = ref([])
const loading = ref(true)

// Panneau compagnon ouvert à gauche : { kind: 'audit'|'exercice'|'vuln', record }.
// En compagnon, on ne gère pas d'état local : on demande à l'hôte de nous remplacer.
const companion = ref(null)
function openCompanion(kind, record) {
  if (props.readonly) emit('open-entity', { kind, record })
  else companion.value = { kind, record }
}

// Fermeture : le ✕ et le voile de cette fiche referment TOUTE la paire (le compagnon est
// monté dans ce template, il disparaît avec elle). Pour ne refermer que le compagnon,
// l'utilisateur dispose de son propre ✕ et d'Échap — que le drawerStack de DetailDrawer
// donne déjà au dernier tiroir monté.

const MAX_ROWS = 10
// Les compteurs affichent un total : la pagination par défaut (50) les tronquerait
// silencieusement. 200 couvre largement le volume par personne et reste sous le
// plafond serveur (limit ≤ 500, cf. routes/entities.py).
const PAGE = 200
const unwrap = (d) => (Array.isArray(d) ? d : (d?.items ?? []))
const safeList = (entity, q = '') =>
  api.list(entity, `${q}${q ? '&' : '?'}limit=${PAGE}`).then(unwrap).catch(() => [])

// Initiales : deux premiers mots du nom, repli sur la première lettre.
const initials = computed(() => {
  const parts = (r.value.nom || '').trim().split(/\s+/).filter(Boolean)
  if (!parts.length) return '—'
  return (parts[0][0] + (parts[1]?.[0] || '')).toUpperCase()
})

const org = computed(() => orgName(r.value.organisation_id))

// Ligne d'identité sous le nom : « Rôle · Organisation », sans séparateur orphelin.
const identity = computed(() =>
  [r.value.role ? enumLabel(r.value.role) : '', org.value].filter(Boolean).join(' · '))

// Un contact n'est cliquable que s'il ressemble à une adresse e-mail ; les autres formes
// (téléphone, trigramme, nom d'un tiers) restent du texte.
const mailto = computed(() => {
  const c = (r.value.contact || '').trim()
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(c) ? c : null
})

const competences = computed(() => r.value.competences || [])
// Compétences du référentiel de rôle non encore renseignées : transforme une section vide
// en incitation à compléter la fiche plutôt qu'en cul-de-sac.
const suggestions = computed(() => {
  const have = new Set(competences.value.map((c) => c.toLowerCase()))
  return competencesForRole(r.value.role).filter((c) => !have.has(c.toLowerCase()))
})

function auditDate(a) { return a.date_debut || a.created_at || '' }
const byDateDesc = (get) => (a, b) => (get(b) || '').localeCompare(get(a) || '')

async function loadAll() {
  loading.value = true
  const id = r.value.id
  const orgId = r.value.organisation_id
  try {
    const [orgAudits, vulnsRes] = await Promise.all([
      safeList('audits', `?client_id=${orgId}`),
      api.get('/vulnerabilities-enriched').catch(() => ({ items: [] })),
    ])

    const mine = orgAudits.filter((a) => (a.auditeurs || []).includes(id))
    audits.value = [...mine].sort(byDateDesc(auditDate))
    vulnerabilities.value = unwrap(vulnsRes)
      .filter((v) => v.decouvreur_id === id)
      .sort(byDateDesc((v) => v.created_at || ''))

    // Exercices Purple : rattachés aux audits de la personne, donc dérivés de `mine`
    // (aucun lien direct exercice -> personne en base).
    const runs = await Promise.all(mine.map((a) => safeList('exercices', `?audit_id=${a.id}`)))
    exercices.value = runs.flat().sort(byDateDesc((e) => e.date || e.created_at || ''))
  } finally {
    loading.value = false
  }
}

onMounted(() => { preloadOrgs(); loadAll() })
</script>

<template>
  <DetailDrawer :subtitle="t('views.ressources.drawer.subtitle')" wide @close="emit('close')">
    <template v-if="!readonly" #actions>
      <button class="btn slim" @click="emit('edit', r)">{{ t('common.edit') }}</button>
    </template>

    <!-- En-tête d'identité : le nom porte le titre du tiroir, on ne le répète plus en ligne de dl. -->
    <div class="ident">
      <div class="avatar" aria-hidden="true">{{ initials }}</div>
      <div class="ident-t">
        <h2 class="nom">{{ r.nom }}</h2>
        <p v-if="identity" class="sous">{{ identity }}</p>
      </div>
    </div>

    <div class="badges">
      <span v-if="r.role" class="pill pill-violet">{{ enumLabel(r.role) }}</span>
      <span v-if="r.type" class="pill pill-gray">{{ enumLabel(r.type) }}</span>
      <span v-if="r.app_user_id" class="pill pill-cyan">{{ t('views.ressources.drawer.linked_account') }}</span>
    </div>

    <div class="tiles">
      <div class="tile">
        <b>{{ exercices.length }}</b><span>{{ t('views.ressources.drawer.tile_exercices') }}</span>
      </div>
      <div class="tile">
        <b>{{ audits.length }}</b><span>{{ t('views.ressources.drawer.tile_audits') }}</span>
      </div>
      <div class="tile">
        <b>{{ vulnerabilities.length }}</b><span>{{ t('views.ressources.drawer.tile_vulns') }}</span>
      </div>
    </div>

    <!-- Contact : contrairement à EntityDrawer, les lignes vides restent visibles (« non
         renseigné ») pour que la fiche garde une forme stable d'une personne à l'autre. -->
    <section class="sec">
      <div class="sec-t">{{ t('views.ressources.drawer.sec_contact') }}</div>
      <dl class="dl">
        <dt>{{ t('fields.contact') }}</dt>
        <dd>
          <a v-if="mailto" :href="`mailto:${mailto}`">{{ mailto }}</a>
          <span v-else-if="r.contact">{{ r.contact }}</span>
          <span v-else class="unset">{{ t('views.ressources.drawer.unset') }}</span>
        </dd>
        <dt>{{ t('fields.organisation_id') }}</dt>
        <dd>{{ org }}</dd>
        <dt>{{ t('fields.description') }}</dt>
        <dd>
          <span v-if="r.description" class="prose">{{ r.description }}</span>
          <span v-else class="unset">{{ t('views.ressources.drawer.unset') }}</span>
        </dd>
      </dl>
    </section>

    <section class="sec">
      <div class="sec-t">{{ t('views.ressources.drawer.sec_competences') }}</div>
      <div v-if="competences.length" class="tags">
        <span v-for="c in competences" :key="c" class="chip on">{{ c }}</span>
      </div>
      <div v-else class="empty">{{ t('views.ressources.drawer.no_competences') }}</div>
      <div v-if="suggestions.length" class="sugg">
        <span class="sugg-lab">{{ t('views.ressources.drawer.suggested', { role: enumLabel(r.role) }) }}</span>
        <span v-for="c in suggestions" :key="c" class="chip">{{ c }}</span>
      </div>
    </section>

    <p v-if="loading" class="faint">{{ t('common.loading') }}</p>

    <template v-else>
      <section class="sec">
        <div class="sec-t">{{ t('views.ressources.drawer.sec_audits', { n: audits.length }) }}</div>
        <ul v-if="audits.length" class="list">
          <li v-for="a in audits.slice(0, MAX_ROWS)" :key="a.id" class="clickable" @click="openCompanion('audit', a)">
            <span class="rn link">{{ a.nom }}</span>
            <span v-if="a.statut" :class="['pill', 'sm', 'pill-' + (STATUT_EXO_TONE[a.statut] || 'gray')]">{{ enumLabel(a.statut) }}</span>
            <span class="faint sm">{{ auditDate(a) || '—' }}</span>
          </li>
        </ul>
        <div v-else class="empty">{{ t('views.ressources.drawer.no_audits') }}</div>
        <div v-if="audits.length > MAX_ROWS" class="faint sm">
          {{ t('views.ressources.drawer.more_audits', { n: audits.length - MAX_ROWS }) }}
        </div>
      </section>

      <section class="sec">
        <div class="sec-t">{{ t('views.ressources.drawer.sec_vulns', { n: vulnerabilities.length }) }}</div>
        <ul v-if="vulnerabilities.length" class="list">
          <li v-for="v in vulnerabilities.slice(0, MAX_ROWS)" :key="v.id" class="clickable" @click="openCompanion('vuln', v)">
            <span class="rn link">{{ v.titre || v.cve || '—' }}</span>
            <span v-if="v.severite" :class="['pill', 'sm', 'pill-' + (SEVERITE_TONE[v.severite] || 'gray')]">{{ enumLabel(v.severite) }}</span>
            <span class="faint sm">{{ v.statut ? enumLabel(v.statut) : '—' }}</span>
          </li>
        </ul>
        <div v-else class="empty">{{ t('views.ressources.drawer.no_vulns') }}</div>
        <div v-if="vulnerabilities.length > MAX_ROWS" class="faint sm">
          {{ t('views.ressources.drawer.more_vulns', { n: vulnerabilities.length - MAX_ROWS }) }}
        </div>
      </section>

      <section v-if="exercices.length" class="sec">
        <div class="sec-t">{{ t('views.ressources.drawer.sec_exercices', { n: exercices.length }) }}</div>
        <ul class="list">
          <li v-for="e in exercices.slice(0, MAX_ROWS)" :key="e.id" class="clickable" @click="openCompanion('exercice', e)">
            <span class="rn link">{{ e.nom }}</span>
            <span v-if="e.statut" :class="['pill', 'sm', 'pill-' + (STATUT_EXO_TONE[e.statut] || 'gray')]">{{ enumLabel(e.statut) }}</span>
            <span class="faint sm">{{ e.date || '—' }}</span>
          </li>
        </ul>
      </section>
    </template>

    <section v-if="r.tags?.length" class="sec">
      <div class="sec-t">{{ t('fields.tags') }}</div>
      <div class="tags"><span v-for="tg in r.tags" :key="tg" class="chip">{{ tg }}</span></div>
    </section>
  </DetailDrawer>

  <!-- Panneau compagnon, monté en frère : son teleport le sort du DOM de la fiche, mais il
       reste un descendant de composant, ce qui lui fait hériter du registre d'appairage.
       Uniquement en hôte : en compagnon, c'est l'hôte qui nous remplace. -->
  <CompanionPanel
    v-if="companion && !readonly"
    :companion="companion"
    @open="companion = $event"
    @close="companion = null"
  />
</template>

<style scoped>
.slim{padding:3px 9px;font-size:11.5px}
.ident{display:flex;align-items:center;gap:12px;margin-bottom:12px}
.avatar{flex:0 0 auto;width:44px;height:44px;border-radius:50%;background:var(--c-violet-bg);
  border:1px solid var(--c-violet-bd);color:var(--c-violet-tx);display:flex;align-items:center;
  justify-content:center;font-family:var(--font-data);font-size:15px;font-weight:600}
.ident-t{min-width:0}
.nom{font-family:var(--font-display);font-size:19px;color:var(--heading);margin:0;line-height:1.2}
.sous{margin:3px 0 0;font-size:13px;color:var(--muted)}
.badges{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:10px;margin-bottom:18px}
.tile{background:var(--surface-2);border:1px solid var(--border);border-radius:var(--r-card);padding:10px 12px}
.tile b{display:block;font-family:var(--font-data);font-size:24px;font-weight:600;color:var(--heading);line-height:1.15}
.tile span{font-size:11px;color:var(--muted)}
.sec{margin-bottom:18px}
.sec-t{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.05em;font-size:10.5px;color:var(--faint);font-weight:var(--eyebrow-weight);margin-bottom:8px;padding-bottom:5px;border-bottom:1px solid var(--border-2)}
.dl{display:grid;grid-template-columns:150px 1fr;gap:8px 14px;margin:0;font-size:13px}
.dl dt{color:var(--muted)} .dl dd{margin:0;color:var(--text);word-break:break-word}
.dl a{color:var(--violet-accent);text-decoration:none}
.dl a:hover{text-decoration:underline}
.unset{color:var(--faint)}
.prose{white-space:pre-wrap;line-height:1.5}
.tags{display:flex;flex-wrap:wrap;gap:5px}
/* Géométrie du .chip normatif (base.css §0.3) : sans align-items ni line-height propre,
   le texte reposerait sur sa ligne de base et paraîtrait décentré vers le haut. */
.chip{display:inline-flex;align-items:center;height:22px;padding:0 9px;line-height:1;white-space:nowrap;
  background:var(--surface-3);border:1px solid var(--border-2);border-radius:var(--r-pill);font-size:11.5px}
.chip.on{background:var(--c-violet-bg);border-color:var(--c-violet-bd);color:var(--c-violet-tx)}
.sugg{display:flex;flex-wrap:wrap;align-items:center;gap:5px;margin-top:8px}
.sugg-lab{font-size:11px;color:var(--faint);margin-right:2px}
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
</style>
