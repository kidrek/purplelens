<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { useAuthStore } from './stores/auth'
import { useUiStore } from './stores/ui'
import { useI18n } from 'vue-i18n'
import { api } from './api/client'
import { icons } from './icons'
import { NAV_GROUPS } from './nav'
import CommandPalette from './components/CommandPalette.vue'
import CorpusArticleDrawer from './components/CorpusArticleDrawer.vue'

const auth = useAuthStore()
const ui = useUiStore()
const route = useRoute()
const { t, locale } = useI18n()

const palette = ref(null)
const counts = ref({})
const navOpen = ref(false) // sidebar mobile (< 860px), cf. DA §6 responsive

onMounted(async () => {
  ui.setTheme(ui.theme)
  // Compteurs de nav (badges) : total par entité via ?limit=1 (léger). Silencieux si échec.
  const wanted = NAV_GROUPS.flatMap((g) => g.items).filter((i) => i.count)
  await Promise.all(wanted.map(async (i) => {
    try {
      const d = await api.list(i.count, '?limit=1')
      if (d && typeof d.total === 'number') counts.value[i.id] = d.total
    } catch { /* non bloquant */ }
  }))
  // Clients accessibles (pour le filtre multi-clients) — silencieux si non autorisé.
  try {
    const d = await api.list('organisations')
    const orgs = Array.isArray(d) ? d : (d?.items ?? [])
    ui.setClients(orgs.filter((o) => o.role === 'client').map((o) => ({ id: o.id, nom: o.nom })))
  } catch { /* non bloquant */ }
})

const showShell = computed(() => auth.isAuthenticated && route.name !== 'login')
const isAdmin = computed(() => auth.role === 'admin')

// Groupes visibles selon le rôle (admin masqué hors admin).
const groups = computed(() =>
  NAV_GROUPS.map((g) => ({
    ...g,
    items: g.items.filter((it) => !it.adminOnly || isAdmin.value),
  })).filter((g) => g.items.length)
)

function isActive(to) {
  return to === '/' ? route.path === '/' : route.path.startsWith(to)
}

async function doLogout() {
  await auth.logout()
  window.location.assign('/login')
}
</script>

<template>
  <div v-if="showShell" class="shell">
    <header class="topbar">
      <button class="hamburger" @click="navOpen = !navOpen"
              :aria-label="t('common.menu')" :aria-expanded="navOpen">
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M4 7h16M4 12h16M4 17h16" />
        </svg>
      </button>
      <div class="brand">
        <span class="dot"></span>
        <span class="brand-name">{{ t('app.title') }}</span>
      </div>

      <!-- Déclencheur de la palette ⌘K -->
      <button class="search-trigger" @click="palette?.show()" :aria-label="t('search.placeholder')">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="7" /><path d="m20 20-3-3" />
        </svg>
        <span>{{ t('search.placeholder') }}</span>
        <span class="kbd">⌘K</span>
      </button>

      <div class="spacer"></div>
      <select v-if="ui.clients.length > 1" class="client-filter"
              :value="ui.activeClient || ''" @change="ui.setActiveClient($event.target.value)"
              title="Filtrer par client">
        <option value="">{{ t('common.all_clients') }}</option>
        <option v-for="c in ui.clients" :key="c.id" :value="c.id">{{ c.nom }}</option>
      </select>
      <!-- Toggles langue + thème — contrôles de la maquette (lang-toggle / icon-btn) -->
      <div class="lang-toggle" role="group" :aria-label="t('common.lang')">
        <button :class="{ on: locale === 'fr' }" @click="locale = 'fr'">FR</button>
        <button :class="{ on: locale === 'en' }" @click="locale = 'en'">EN</button>
      </div>
      <button class="icon-btn" @click="ui.toggleTheme()" :aria-label="t('common.theme_toggle')" :title="t('common.theme_toggle')">
        <svg v-if="ui.theme === 'dark'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="4.5"/><path d="M12 2v2.5M12 19.5V22M4.2 4.2l1.8 1.8M18 18l1.8 1.8M2 12h2.5M19.5 12H22M4.2 19.8 6 18M18 6l1.8-1.8"/></svg>
        <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 14.5A8 8 0 0 1 9.5 4 8.5 8.5 0 1 0 20 14.5Z"/></svg>
      </button>
      <RouterLink class="who" to="/account" title="Mon compte (MFA)">
        {{ auth.user?.display_name }} · <span class="pill pill-violet">{{ auth.role }}</span>
        <span v-if="!auth.user?.mfa" class="pill pill-amber">MFA</span>
      </RouterLink>
      <button class="btn" @click="doLogout">{{ t('common.logout') }}</button>
    </header>

    <div class="body">
      <aside class="sidebar" :class="{ open: navOpen }">
        <nav v-for="g in groups" :key="g.id" class="nav-group">
          <div class="nav-group-title">{{ t('navgroup.' + g.id) }}</div>
          <RouterLink
            v-for="it in g.items" :key="it.id" :to="it.to"
            class="nav-item" :class="{ on: isActive(it.to) }"
            @click="navOpen = false"
          >
            <span class="nav-ico" v-html="icons[it.icon]"></span>
            <span class="nav-label">{{ t('nav.' + it.id) }}</span>
            <span v-if="counts[it.id] != null" class="nav-count">{{ counts[it.id] }}</span>
          </RouterLink>
        </nav>
        <p class="side-note">{{ t('side.note') }}</p>
      </aside>

      <main class="content">
        <RouterView />
      </main>
    </div>

    <CommandPalette
      ref="palette" :is-admin="isAdmin"
      :on-toggle-theme="() => ui.toggleTheme()" :on-logout="doLogout"
    />

    <!-- Drawer d'article corpus global (⌘K) : superposé à la page courante, sans navigation -->
    <CorpusArticleDrawer v-if="ui.articleSlug" :slug="ui.articleSlug" @close="ui.closeArticle()" />
  </div>

  <RouterView v-else />
</template>

<style scoped>
.shell{display:flex;flex-direction:column;height:100%}
/* Sélecteur de client (multi-clients) */
.client-filter{background:var(--surface-2);border:1px solid var(--border);color:var(--text);
  border-radius:var(--r-pill);padding:5px 10px;font-size:12.5px;max-width:180px}
.topbar{
  height:var(--topbar-h);display:flex;align-items:center;gap:14px;
  padding:0 18px;background:var(--surface);border-bottom:1px solid var(--border);
}
.brand{display:flex;align-items:center;gap:9px}
.brand .dot{width:11px;height:11px;border-radius:50%;background:var(--violet);box-shadow:0 0 12px var(--violet)}
.brand-name{font-family:var(--font-display);font-weight:600;font-size:14.5px;color:var(--heading);letter-spacing:.01em}
.spacer{flex:1}
.who{color:var(--muted);font-size:12px;display:flex;align-items:center;gap:6px}
.btn.ghost{background:transparent;border-color:var(--border-2)}

/* Toggles langue + thème (maquette, DA §0.3) */
.icon-btn{width:34px;height:34px;display:inline-flex;align-items:center;justify-content:center;
  border:1px solid var(--border-field);border-radius:8px;background:var(--field);color:var(--muted);
  cursor:pointer;transition:border-color var(--t),color var(--t)}
.icon-btn:hover{border-color:var(--violet);color:var(--violet-accent,var(--violet))}
.icon-btn svg{width:17px;height:17px}
.lang-toggle{height:34px;display:inline-flex;align-items:center;border:1px solid var(--border-field);
  border-radius:8px;background:var(--field);overflow:hidden}
.lang-toggle button{padding:0 10px;height:100%;font-size:11.5px;font-weight:600;color:var(--faint);
  background:transparent;border:0;cursor:pointer;font-family:inherit;
  transition:background var(--t-fast),color var(--t-fast)}
.lang-toggle button.on{background:var(--violet-soft);color:var(--nav-active-text)}

/* Déclencheur de recherche (topbar) */
.search-trigger{
  display:flex;align-items:center;gap:8px;height:34px;width:min(420px,40vw);
  padding:0 10px;border:1px solid var(--border-field);border-radius:9px;background:var(--field);
  color:var(--faint);font-size:12.5px;cursor:pointer;transition:border-color var(--t) var(--ease);
}
.search-trigger:hover{border-color:var(--violet)}
.search-trigger .kbd{margin-left:auto}
.kbd{font-family:var(--font-data);font-size:10.5px;color:var(--muted);
  border:1px solid var(--border);border-radius:5px;padding:1px 5px;background:var(--surface-2)}

.body{flex:1;display:flex;min-height:0}
.sidebar{
  width:var(--sidebar-w);flex-shrink:0;padding:14px 10px;background:var(--surface);
  border-right:1px solid var(--border);overflow-y:auto;
}
.nav-group{margin-bottom:16px}
.nav-group-title{padding:0 8px 7px;font-family:var(--font-eyebrow);font-size:10px;
  font-weight:var(--eyebrow-weight);letter-spacing:.1em;text-transform:uppercase;color:var(--faint)}
.nav-item{
  width:100%;display:flex;align-items:center;gap:9px;padding:7px 8px;border-radius:9px;
  color:var(--muted);font-size:12.5px;text-align:left;position:relative;
  transition:background var(--t-fast),color var(--t-fast);text-decoration:none;
}
.nav-item:hover{background:var(--surface-2);color:var(--text)}
.nav-item.on{background:var(--nav-active-bg);color:var(--nav-active-text);font-weight:600}
.nav-item.on::before{content:"";position:absolute;left:0;top:6px;bottom:6px;width:3px;
  border-radius:3px;background:var(--nav-active-border)}
.nav-ico{display:inline-flex}
.nav-ico :deep(svg){width:16px;height:16px;flex:0 0 auto;opacity:.9}
.nav-label{flex:1 1 auto;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.nav-count{font-family:var(--font-data);font-size:10.5px;color:var(--faint);
  background:var(--surface-2);border:1px solid var(--border-2);border-radius:6px;padding:0 5px;min-width:20px;text-align:center}
.nav-item.on .nav-count{color:var(--nav-active-text);border-color:var(--nav-active-border)}
.side-note{padding:0 8px;font-size:10.5px;color:var(--faint);line-height:1.4}

.content{flex:1;overflow:auto;padding:18px 22px 40px}

/* Hamburger — masqué par défaut, visible seulement en dessous de 860px.
   (style autonome, historiquement antérieur au .icon-btn local ci-dessus ;
   il diffère par le display:none par défaut.) */
.hamburger{
  display:none;flex:0 0 auto;width:34px;height:34px;align-items:center;justify-content:center;
  border:1px solid var(--border-field);border-radius:8px;background:var(--field);color:var(--muted);
  transition:border-color var(--t),color var(--t);
}
.hamburger:hover{border-color:var(--violet);color:var(--violet-accent,var(--violet))}

/* Responsive (DA §6) : sidebar en panneau glissant sous 860px */
@media(max-width:860px){
  .hamburger{display:inline-flex}
  .sidebar{
    position:fixed;top:var(--topbar-h);left:0;bottom:0;z-index:35;
    transform:translateX(-100%);transition:transform var(--t) var(--ease);
    box-shadow:8px 0 40px rgba(0,0,0,.28);
  }
  .sidebar.open{transform:none}
  .search-trigger{width:auto;flex:1 1 auto}
}
@media(max-width:520px){
  .search-trigger span:not(.kbd){display:none}
}
</style>
