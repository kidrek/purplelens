<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api } from '../api/client'
import DetailDrawer from './DetailDrawer.vue'
import { useLabels } from '../composables/useLabels'

// Drawer de détail d'une Organisation (60 %, cf. correctif largeur EntityDrawer).
// En plus des méta-données, affiche en lecture seule (cahier « constats » Organisations) :
//   - la liste des ressources rattachées,
//   - les 10 derniers audits (les plus récents en premier),
//   - les 10 dernières vulnérabilités (avec renvoi vers la page dédiée pour l'exhaustivité).
// Prop nommée "record" : contrat générique utilisé par EntityTable pour tout composant
// passé via :drawer="..." (cf. AuditDrawer / ScenarioDrawer).
const props = defineProps({ record: { type: Object, required: true } })
const emit = defineEmits(['close', 'edit'])
const { fieldLabel, enumLabel } = useLabels()

const o = computed(() => props.record)
const ressources = ref([])
const audits = ref([])
const vulnerabilities = ref([])
const loading = ref(true)

const SEV_TONE = { critique: 'red', haute: 'amber', elevee: 'amber', moyenne: 'cyan', basse: 'green' }
const AUDIT_TONE = { planifie: 'gray', en_cours: 'cyan', termine: 'green', suspendu: 'amber', annule: 'red' }

const unwrap = (d) => (Array.isArray(d) ? d : (d?.items ?? []))
const safeList = (entity, q = '') => api.list(entity, q).then(unwrap).catch(() => [])

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

async function loadAll() {
  loading.value = true
  const id = o.value.id
  try {
    const [ress, auds, vulnsRes] = await Promise.all([
      safeList('ressources', `?organisation_id=${id}`),
      safeList('audits', `?client_id=${id}`),
      api.get('/vulnerabilities-enriched').catch(() => ({ items: [] })),
    ])
    ressources.value = ress
    audits.value = [...auds]
      .sort((a, b) => (auditDate(b) || '').localeCompare(auditDate(a) || ''))
      .slice(0, 10)
    vulnerabilities.value = (vulnsRes.items || [])
      .filter((v) => v.client_id === id)
      .sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''))
      .slice(0, 10)
  } finally {
    loading.value = false
  }
}
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
      <!-- Ressources de l'organisation -->
      <section class="sec">
        <div class="sec-t">Ressources ({{ ressources.length }})</div>
        <ul v-if="ressources.length" class="list">
          <li v-for="r in ressources" :key="r.id">
            <span class="rn">{{ r.nom }}</span>
            <span v-if="r.role" class="pill pill-violet sm">{{ enumLabel(r.role) }}</span>
            <span class="faint sm">{{ r.contact || '—' }}</span>
          </li>
        </ul>
        <div v-else class="empty">Aucune ressource rattachée pour l'instant.</div>
      </section>

      <!-- 10 derniers audits -->
      <section class="sec">
        <div class="sec-t">Derniers audits ({{ audits.length }}{{ audits.length === 10 ? '+' : '' }})</div>
        <ul v-if="audits.length" class="list">
          <li v-for="a in audits" :key="a.id">
            <RouterLink :to="`/audits/${a.id}`" class="rn link">{{ a.nom }}</RouterLink>
            <span v-if="a.statut" :class="['pill', 'sm', 'pill-' + (AUDIT_TONE[a.statut] || 'gray')]">{{ enumLabel(a.statut) }}</span>
            <span class="faint sm">{{ auditDate(a) || '—' }}</span>
          </li>
        </ul>
        <div v-else class="empty">Aucun audit pour cette organisation pour l'instant.</div>
      </section>

      <!-- 10 dernières vulnérabilités -->
      <section class="sec">
        <div class="sec-t">Dernières vulnérabilités ({{ vulnerabilities.length }}{{ vulnerabilities.length === 10 ? '+' : '' }})</div>
        <ul v-if="vulnerabilities.length" class="list">
          <li v-for="v in vulnerabilities" :key="v.id">
            <span class="rn">{{ v.titre || v.cve || '—' }}</span>
            <span v-if="v.severite" :class="['pill', 'sm', 'pill-' + (SEV_TONE[v.severite] || 'gray')]">{{ enumLabel(v.severite) }}</span>
            <span class="faint sm">{{ v.statut ? enumLabel(v.statut) : '—' }}</span>
          </li>
        </ul>
        <div v-else class="empty">Aucune vulnérabilité pour cette organisation pour l'instant.</div>
        <RouterLink to="/vulnerabilities" class="more-link">
          Voir la page Vulnérabilités pour la liste exhaustive et les filtres →
        </RouterLink>
      </section>
    </template>
  </DetailDrawer>
</template>

<style scoped>
.slim{padding:3px 9px;font-size:11.5px}
.badges{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px}
.sec{margin-bottom:18px}
.sec-t{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.05em;font-size:10.5px;color:var(--faint);font-weight:var(--eyebrow-weight);margin-bottom:8px;padding-bottom:5px;border-bottom:1px solid var(--border-2)}
.dl{display:grid;grid-template-columns:150px 1fr;gap:8px 14px;margin:0 0 8px;font-size:13px}
.dl dt{color:var(--muted)} .dl dd{margin:0;color:var(--text);word-break:break-word}
.tags{display:flex;flex-wrap:wrap;gap:5px}
.chip{display:inline-block;background:var(--surface-3);border:1px solid var(--border-2);border-radius:var(--r-pill);padding:1px 8px;font-size:11.5px}
.empty{font-size:12px;color:var(--muted);background:var(--surface-2);border:1px solid var(--border);border-radius:var(--r-mini);padding:9px 12px}
.list{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:6px}
.list li{display:flex;align-items:center;gap:8px;font-size:12.5px;padding:6px 8px;border:1px solid var(--border);border-radius:var(--r-mini);background:var(--surface-2);box-shadow:var(--shadow)}
.rn{flex:1;color:var(--heading);font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.rn.link{cursor:pointer;text-decoration:none}
.rn.link:hover{color:var(--violet-accent);text-decoration:underline}
.sm{font-size:10.5px;flex:0 0 auto}
.more-link{display:inline-block;margin-top:8px;font-size:12px;color:var(--violet-accent);text-decoration:none}
.more-link:hover{text-decoration:underline}
</style>
