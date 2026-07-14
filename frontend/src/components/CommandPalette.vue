<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { NAV_FLAT } from '../nav'
import { useCorpus } from '../composables/useCorpus'
import { useUiStore } from '../stores/ui'

// Palette de commandes globale (⌘K / Ctrl+K). Recherche floue sur les destinations de
// navigation + quelques actions + les articles du corpus (DA §4.6 : "les articles de
// corpus apparaissent comme résultats, icône livre, groupe navigation ; libellé =
// titre résolu par langue"). Navigation clavier : ↑/↓, Entrée, Échap.
const props = defineProps({
  isAdmin: { type: Boolean, default: false },
  onToggleTheme: { type: Function, default: null },
  onLogout: { type: Function, default: null },
})

const router = useRouter()
const ui = useUiStore()
const { t, locale } = useI18n()
const { corpusRows, preloadCorpus } = useCorpus()

const open = ref(false)
const q = ref('')
const idx = ref(0)
const inputEl = ref(null)

// Commandes = destinations de nav (respectant adminOnly) + actions + articles corpus.
const commands = computed(() => {
  const nav = NAV_FLAT
    .filter((it) => !it.adminOnly || props.isAdmin)
    .map((it) => ({
      group: 'nav', label: t('nav.' + it.id), hint: t('cmd.go'),
      run: () => router.push(it.to),
    }))
  const acts = []
  if (props.onToggleTheme) acts.push({ group: 'act', label: t('cmd.toggleTheme'), hint: t('cmd.action'), run: props.onToggleTheme })
  acts.push({ group: 'act', label: t('nav.account'), hint: t('cmd.go'), run: () => router.push('/account') })
  if (props.onLogout) acts.push({ group: 'act', label: t('common.logout'), hint: t('cmd.action'), run: props.onLogout })
  const corp = corpusRows.value.map((r) => ({
    group: 'corp',
    label: locale.value === 'en' && r.titre_en ? r.titre_en : r.titre_fr,
    hint: t('corpus.cmdHint'),
    // Ouvre le drawer d'article global (App.vue) sur la page courante, sans navigation.
    run: () => ui.openArticle(r.slug),
  }))
  return [...nav, ...acts, ...corp]
})

const results = computed(() => {
  const needle = q.value.trim().toLowerCase()
  if (!needle) return commands.value
  return commands.value.filter((c) => c.label.toLowerCase().includes(needle))
})

watch(q, () => { idx.value = 0 })
watch(results, (r) => { if (idx.value >= r.length) idx.value = Math.max(0, r.length - 1) })

function show() {
  open.value = true; q.value = ''; idx.value = 0
  nextTick(() => inputEl.value?.focus())
}
function hide() { open.value = false }
function move(d) {
  const n = results.value.length
  if (!n) return
  idx.value = (idx.value + d + n) % n
}
function run(item) {
  const it = item || results.value[idx.value]
  if (!it) return
  hide()
  it.run()
}

function onKeydown(e) {
  // Ouverture globale : Cmd/Ctrl + K
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    open.value ? hide() : show()
    return
  }
  if (!open.value) return
  if (e.key === 'Escape') { e.preventDefault(); hide() }
  else if (e.key === 'ArrowDown') { e.preventDefault(); move(1) }
  else if (e.key === 'ArrowUp') { e.preventDefault(); move(-1) }
  else if (e.key === 'Enter') { e.preventDefault(); run() }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onMounted(preloadCorpus)
onUnmounted(() => window.removeEventListener('keydown', onKeydown))

// Exposé pour permettre au bouton de recherche de la topbar d'ouvrir la palette.
defineExpose({ show })
</script>

<template>
  <teleport to="body">
    <div v-if="open">
      <div class="drawer-scrim" @click="hide"></div>
      <div class="cmdk" role="dialog" aria-modal="true" :aria-label="t('search.placeholder')">
        <div class="cmd-head">
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="var(--caret)" stroke-width="2">
            <circle cx="11" cy="11" r="7" /><path d="m20 20-3-3" />
          </svg>
          <input ref="inputEl" type="text" v-model="q" :placeholder="t('cmd.placeholder')" />
          <span class="kbd">esc</span>
        </div>
        <div class="cmd-list" role="listbox">
          <button
            v-for="(it, i) in results" :key="it.group + '-' + it.label"
            class="cmd-item" :class="{ sel: i === idx }"
            role="option" :aria-selected="i === idx"
            @click="run(it)" @mouseenter="idx = i"
          >
            <span class="cmd-dot" :class="it.group"></span>
            <span class="cmd-label">{{ it.label }}</span>
            <span class="cmd-hint">{{ it.hint }}</span>
          </button>
          <div v-if="!results.length" class="cmd-empty">{{ t('cmd.none') }}</div>
        </div>
        <div class="cmd-foot">
          <span class="kbd">↑</span><span class="kbd">↓</span>{{ t('cmd.navigate') }}
          <span class="kbd">↵</span>{{ t('cmd.select') }}
        </div>
      </div>
    </div>
  </teleport>
</template>

<style scoped>
.drawer-scrim{position:fixed;inset:0;background:var(--scrim);z-index:40;backdrop-filter:blur(1.5px)}
.cmdk{position:fixed;left:50%;top:14vh;transform:translateX(-50%);width:min(660px,92vw);z-index:42;
  background:var(--modal);border:1px solid var(--modal-border);border-radius:16px;
  box-shadow:0 24px 70px rgba(0,0,0,.4);overflow:hidden}
.cmd-head{display:flex;align-items:center;gap:10px;padding:14px 16px;border-bottom:1px solid var(--border-2)}
.cmd-head input{flex:1;border:0;background:transparent;outline:none;font-size:15px;color:var(--text);
  caret-color:var(--caret);font-family:var(--font-body)}
.cmd-list{max-height:46vh;overflow-y:auto;padding:6px}
.cmd-item{display:flex;align-items:center;gap:11px;width:100%;text-align:left;border:0;background:transparent;
  border-radius:9px;padding:9px 11px;cursor:pointer;color:var(--text);font:inherit}
.cmd-item.sel{background:var(--surface-2)}
.cmd-dot{width:7px;height:7px;border-radius:50%;flex:0 0 auto}
.cmd-dot.nav{background:var(--violet)}
.cmd-dot.act{background:var(--c-cyan-tx)}
.cmd-dot.corp{background:var(--c-violet-tx)}
.cmd-label{flex:1;font-size:13.5px;color:var(--heading)}
.cmd-hint{font-size:11px;color:var(--faint);text-transform:uppercase;letter-spacing:.03em}
.cmd-empty{padding:22px;text-align:center;color:var(--muted);font-size:13px}
.cmd-foot{display:flex;align-items:center;gap:7px;padding:9px 14px;border-top:1px solid var(--border-2);
  font-size:11px;color:var(--faint)}
.kbd{font-family:var(--font-data);font-size:10.5px;color:var(--muted);border:1px solid var(--border);
  border-radius:5px;padding:1px 5px;background:var(--surface-2)}
</style>
