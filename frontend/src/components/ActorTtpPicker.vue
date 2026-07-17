<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../api/client'

// Champ « Acteur émulé » : sélecteur unique à autocomplétion (même ergonomie que le
// sélecteur de scénario du Nouveau audit — RefacSelect). La valeur (v-model) est le NOM
// de l'acteur émulé, stocké tel quel dans `acteur_emule` (chaîne libre).
//   - Recherche par nom OU alias ; correspondance par alias affichée « Alias (Nom officiel) ».
//   - Acteur du référentiel choisi → panneau de revue de ses TTPs sous le champ (décochées) ;
//     « Ajouter » émet les techniques cochées comme étapes : emit('import', { steps }).
//   - Repli en saisie libre : un nom absent du référentiel est accepté (sans import de TTPs).
const props = defineProps({
  modelValue: { type: [String, null], default: '' },
})
const emit = defineEmits(['update:modelValue', 'import'])

const actors = ref([])
const loaded = ref(false)
const q = ref('')
const open = ref(false)
const hi = ref(0)

// Panneau de revue (acteur catalogué sélectionné).
const active = ref(null)          // { key, name, source }
const techs = ref([])             // [{ ext_id, name, tactic }]
const checked = ref(new Set())    // ext_id cochés
const loadingTechs = ref(false)
const techErr = ref(null)

const TACTICS = [
  'reconnaissance', 'resource-development', 'initial-access', 'execution', 'persistence',
  'privilege-escalation', 'defense-evasion', 'credential-access', 'discovery',
  'lateral-movement', 'collection', 'command-and-control', 'exfiltration', 'impact',
]
const SOURCE_LABEL = { attack: 'ATT&CK', misp: 'MISP' }

// Normalisation insensible à la casse et aux accents (recherche par alias), par code de point.
function norm(s) {
  const decomposed = (s || '').normalize('NFD')
  let out = ''
  for (const ch of decomposed) {
    const c = ch.codePointAt(0)
    if (c >= 0x0300 && c <= 0x036f) continue
    out += ch
  }
  return out.toLowerCase()
}

onMounted(async () => {
  try { actors.value = (await api.get('/reference/actors')).actors || [] }
  catch { actors.value = [] }
  finally { loaded.value = true }
})

// Acteur catalogué correspondant à la valeur courante (par nom ou alias) — pour afficher le
// badge de source et proposer la (ré)ouverture du panneau en édition.
const chosenActor = computed(() => {
  const v = norm(props.modelValue)
  if (!v) return null
  return actors.value.find((a) => norm(a.name) === v
    || (a.aliases || []).some((x) => norm(x) === v)) || null
})

// Suggestions : acteurs (nom OU alias) + option « acteur libre » quand la saisie ne matche rien.
const suggestions = computed(() => {
  const needle = norm(q.value.trim())
  const out = []
  for (const a of actors.value) {
    if (!needle || norm(a.name).includes(needle)) { out.push({ actor: a, display: a.name }); continue }
    const alias = (a.aliases || []).find((x) => norm(x).includes(needle))
    if (alias) out.push({ actor: a, display: `${alias} (${a.name})` })
  }
  return out.slice(0, 30)
})
const rawQuery = computed(() => q.value.trim())
const exactMatch = computed(() => {
  const n = norm(rawQuery.value)
  return !!n && actors.value.some((a) => norm(a.name) === n
    || (a.aliases || []).some((x) => norm(x) === n))
})
watch(q, () => { hi.value = 0; open.value = true })

async function selectActor(a) {
  q.value = ''
  open.value = false
  emit('update:modelValue', a.name)
  active.value = a
  techs.value = []
  checked.value = new Set()
  techErr.value = null
  loadingTechs.value = true
  try {
    const d = await api.get(`/reference/actors/${encodeURIComponent(a.key)}/techniques`)
    techs.value = d.techniques || []
  } catch (e) {
    techErr.value = e.message || 'Impossible de charger les techniques.'
  } finally {
    loadingTechs.value = false
  }
}
function selectFree(text) {
  const v = (text || '').trim()
  if (!v) return
  q.value = ''
  open.value = false
  active.value = null
  emit('update:modelValue', v)
}
function clear() {
  emit('update:modelValue', '')
  q.value = ''
  active.value = null
  techs.value = []
  checked.value = new Set()
  open.value = true
}
// (Ré)ouvre le panneau de revue pour la valeur courante si elle est cataloguée (édition).
async function reopenReview() {
  const a = chosenActor.value
  if (!a) return
  active.value = a
  techs.value = []
  checked.value = new Set()
  techErr.value = null
  loadingTechs.value = true
  try {
    const d = await api.get(`/reference/actors/${encodeURIComponent(a.key)}/techniques`)
    techs.value = d.techniques || []
  } catch (e) {
    techErr.value = e.message || 'Impossible de charger les techniques.'
  } finally {
    loadingTechs.value = false
  }
}

const grouped = computed(() => {
  // Chaque technique atterrit dans un groupe : les couvertes par tactique (repli 'autre'
  // pour toute tactique hors liste blanche), les non couvertes dans une section dédiée.
  // Le compteur (techs.length) reste ainsi toujours cohérent avec l'affichage.
  const by = {}
  const uncovered = []
  for (const t of techs.value) {
    if (t.covered === false) { uncovered.push(t); continue }
    const k = TACTICS.includes(t.tactic) ? t.tactic : 'autre'
    ;(by[k] ||= []).push(t)
  }
  // Tri secondaire par ID de technique au sein de chaque tactique (ordre naturel :
  // les ext_id ATT&CK ont la forme T####[.###], `numeric` gère les largeurs variables).
  const cmp = (a, b) => a.ext_id.localeCompare(b.ext_id, undefined, { numeric: true })
  const groups = [...TACTICS, 'autre']
    .filter((k) => by[k]).map((k) => ({ tactic: k, items: by[k].sort(cmp) }))
  if (uncovered.length) groups.push({ tactic: 'non-couvertes', items: uncovered.sort(cmp), uncovered: true })
  return groups
})
const checkedCount = computed(() => checked.value.size)
const uncoveredCount = computed(() => techs.value.filter((t) => t.covered === false).length)

function toggle(id) {
  const s = new Set(checked.value)
  s.has(id) ? s.delete(id) : s.add(id)
  checked.value = s
}
function toggleGroup(items) {
  const s = new Set(checked.value)
  const allOn = items.every((t) => s.has(t.ext_id))
  for (const t of items) allOn ? s.delete(t.ext_id) : s.add(t.ext_id)
  checked.value = s
}
function onKey(e) {
  if (!open.value && (e.key === 'ArrowDown' || e.key === 'Enter')) { open.value = true; return }
  const n = suggestions.value.length + (rawQuery.value && !exactMatch.value ? 1 : 0)
  if (e.key === 'ArrowDown') { e.preventDefault(); hi.value = (hi.value + 1) % Math.max(1, n) }
  else if (e.key === 'ArrowUp') { e.preventDefault(); hi.value = (hi.value - 1 + n) % Math.max(1, n) }
  else if (e.key === 'Enter') {
    e.preventDefault()
    if (hi.value < suggestions.value.length && suggestions.value[hi.value]) selectActor(suggestions.value[hi.value].actor)
    else if (rawQuery.value) selectFree(rawQuery.value)
  } else if (e.key === 'Escape') { open.value = false }
}

function doImport() {
  // Ordre kill chain : on parcourt `grouped` (tactiques dans l'ordre TACTICS, puis
  // 'autre', puis non-couvertes) plutôt que l'ordre brut de l'API, pour que les étapes
  // créées suivent la chaîne d'attaque — identique à l'ordre du panneau de revue.
  const ordered = grouped.value.flatMap((g) => g.items)
  const chosen = ordered.filter((t) => checked.value.has(t.ext_id))
  const steps = chosen.map((t) => ({
    id: `tmp-${t.ext_id}-${Math.random().toString(36).slice(2, 7)}`,
    technique: t.ext_id, tactique: t.tactic || '', commande: '', description: t.description || '',
  }))
  emit('import', { steps })
  // Replie le panneau ; la valeur (acteur) reste posée.
  active.value = null
  techs.value = []
  checked.value = new Set()
}
</script>

<template>
  <div class="actor-pick">
    <!-- Valeur posée : chip compact (comme RefacSelect) -->
    <div v-if="modelValue" class="chosen">
      <span class="lbl">{{ modelValue }}</span>
      <span v-if="chosenActor" class="src" :class="'src-' + chosenActor.source">
        {{ SOURCE_LABEL[chosenActor.source] || chosenActor.source }}
      </span>
      <span v-else class="src src-free">libre</span>
      <button v-if="chosenActor && !active" type="button" class="mini-btn" @click="reopenReview">
        Importer les TTPs
      </button>
      <button type="button" class="x" title="Changer" @click="clear">✕</button>
    </div>

    <!-- Saisie / recherche -->
    <div v-else class="box" @focusout="open = false" tabindex="-1">
      <input
        class="field" v-model="q"
        :placeholder="loaded ? 'Rechercher un acteur ou un alias (APT29, Cozy Bear, FIN7…)' : 'Chargement des acteurs…'"
        @focus="open = true" @keydown="onKey" autocomplete="off"
      />
      <div v-if="open && (suggestions.length || (rawQuery && !exactMatch))" class="menu">
        <button
          v-for="(s, i) in suggestions" :key="s.actor.key" type="button"
          class="opt" :class="{ hi: i === hi }"
          @mousedown.prevent="selectActor(s.actor)" @mouseenter="hi = i"
        >
          <span class="nm">{{ s.display }}</span>
          <span class="src" :class="'src-' + s.actor.source">{{ SOURCE_LABEL[s.actor.source] || s.actor.source }}</span>
          <span class="cnt">{{ s.actor.technique_count }} TTP</span>
        </button>
        <!-- Repli saisie libre -->
        <button
          v-if="rawQuery && !exactMatch" type="button"
          class="opt free" :class="{ hi: hi === suggestions.length }"
          @mousedown.prevent="selectFree(rawQuery)" @mouseenter="hi = suggestions.length"
        >
          Utiliser « <b>{{ rawQuery }}</b> » <span class="cnt">acteur libre</span>
        </button>
      </div>
    </div>

    <!-- Panneau de revue des techniques (acteur catalogué) -->
    <div v-if="active" class="review">
      <div class="review-head">
        <span class="rh-lbl">TTPs connues de <b>{{ active.name }}</b></span>
        <button type="button" class="x" title="Fermer" @click="active = null">×</button>
      </div>

      <div v-if="loadingTechs" class="muted">Chargement des techniques…</div>
      <div v-else-if="techErr" class="err">{{ techErr }}</div>
      <div v-else-if="!techs.length" class="muted">
        Aucune technique connue pour cet acteur dans le référentiel importé
        (synchronisez « ATT&CK Groups » dans Paramètres pour la couverture complète).
      </div>

      <template v-else>
        <p class="hint">
          {{ techs.length }} technique(s) connue(s) — cochez celles à ajouter comme étapes.
          <span class="faint">La couverture dépend du référentiel importé (socle vs. sync MITRE).</span>
        </p>
        <div v-for="g in grouped" :key="g.tactic" class="tac-group" :class="{ uncov: g.uncovered }">
          <div class="tac-head">
            <button type="button" class="tac-toggle" @click="toggleGroup(g.items)">
              {{ g.items.every((t) => checked.has(t.ext_id)) ? '☑' : '☐' }}
            </button>
            <span class="tac-name">{{ g.uncovered ? 'Non couvertes — hors référentiel importé' : g.tactic }}</span>
            <span class="tac-count">{{ g.items.length }}</span>
          </div>
          <label v-for="t in g.items" :key="t.ext_id" class="tech" :class="{ on: checked.has(t.ext_id) }">
            <input type="checkbox" :checked="checked.has(t.ext_id)" @change="toggle(t.ext_id)" />
            <span class="code">{{ t.ext_id }}</span>
            <span class="tn">{{ g.uncovered ? '— hors socle' : t.name }}</span>
          </label>
        </div>

        <p v-if="uncoveredCount" class="uncov-note">
          {{ uncoveredCount }} technique(s) hors du référentiel importé. Demandez à votre
          administrateur de synchroniser le référentiel ATT&CK complet (Paramètres → Référentiels)
          pour couvrir tout le scénario de cet acteur.
        </p>

        <div class="review-foot">
          <span class="sel-count">{{ checkedCount }} / {{ techs.length }} sélectionnée(s)</span>
          <button type="button" class="btn btn-primary slim" :disabled="!checkedCount" @click="doImport">
            Ajouter {{ checkedCount }} technique(s) comme étapes
          </button>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.actor-pick{display:flex;flex-direction:column;gap:10px}
.box{position:relative}
.chosen{display:flex;align-items:center;gap:8px;border:1px solid var(--border);
  background:var(--surface);border-radius:var(--r-mini);padding:7px 10px}
.chosen .lbl{font-size:13px;color:var(--heading);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.chosen .x{border:0;background:transparent;color:var(--muted);cursor:pointer;font-size:13px;flex:0 0 auto}
.mini-btn{flex:0 0 auto;border:1px solid var(--violet);color:var(--violet-accent);background:transparent;
  border-radius:var(--r-pill);padding:2px 9px;font-size:11px;cursor:pointer}
.mini-btn:hover{background:var(--c-violet-bg)}
.menu{position:absolute;left:0;right:0;top:calc(100% + 4px);z-index:20;background:var(--surface);
  border:1px solid var(--border);border-radius:var(--r-mini);box-shadow:var(--shadow);max-height:260px;overflow-y:auto;padding:4px}
.opt{display:flex;align-items:center;gap:9px;width:100%;text-align:left;border:0;background:transparent;
  border-radius:var(--r-mini);padding:6px 9px;cursor:pointer;color:var(--text);font:inherit}
.opt.hi{background:var(--surface-2)}
.opt .nm{flex:1;font-size:12.5px;color:var(--heading);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.opt .cnt{font-size:10.5px;color:var(--faint);font-family:var(--font-data)}
.opt.free{color:var(--muted);font-size:12.5px;border-top:1px solid var(--border-2);margin-top:2px}
.src{flex:0 0 auto;font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;
  border-radius:var(--r-pill);padding:1px 6px;border:1px solid transparent}
.src-attack{background:var(--c-violet-bg);color:var(--c-violet-tx);border-color:var(--c-violet-bd)}
.src-misp{background:var(--surface-3);color:var(--muted)}
.src-free{background:var(--surface-3);color:var(--faint)}
.review{border:1px solid var(--border);border-radius:var(--r-card);background:var(--surface-2);padding:12px}
.review-head{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:8px}
.rh-lbl{font-size:12.5px;color:var(--muted)}
.rh-lbl b{color:var(--heading)}
.x{border:0;background:transparent;color:var(--muted);cursor:pointer;font-size:16px;line-height:1}
.hint{font-size:12px;color:var(--muted);margin:0 0 10px}
.hint .faint{color:var(--faint);display:block;font-size:11px;margin-top:2px}
.tac-group{margin-bottom:8px}
.tac-head{display:flex;align-items:center;gap:8px;margin:6px 0 3px}
.tac-toggle{border:0;background:transparent;cursor:pointer;font-size:14px;color:var(--violet-accent);padding:0;line-height:1}
.tac-name{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.04em;font-size:10.5px;color:var(--faint)}
.tac-count{font-size:10px;color:var(--faint);font-family:var(--font-data)}
.tac-group.uncov{opacity:.72}
.tac-group.uncov .tac-name{color:var(--muted)}
.tac-group.uncov .tech .tn{color:var(--faint);font-style:italic}
.uncov-note{font-size:11px;color:var(--faint);margin:8px 0 0;line-height:1.4}
.tech{display:flex;align-items:center;gap:8px;padding:4px 6px;border-radius:var(--r-mini);cursor:pointer;font-size:12.5px}
.tech:hover{background:var(--surface-3)}
.tech.on{background:var(--c-violet-bg)}
.tech .code{font-family:var(--font-data);font-size:11.5px;font-weight:600;color:var(--heading);min-width:74px}
.tech .tn{color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.review-foot{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:10px;
  padding-top:10px;border-top:1px solid var(--border-2)}
.sel-count{font-size:12px;color:var(--muted);font-family:var(--font-data)}
.slim{padding:6px 12px;font-size:12.5px}
.muted{color:var(--muted);font-size:12.5px}
.err{color:var(--red);font-size:12.5px}
</style>
