import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

// Les routes sont déclaratives ; la garde vérifie seulement qu'une session existe.
// Toute décision fine (voir/éditer telle entité) est prise par le serveur à
// chaque appel API — le routeur ne fait que de l'aiguillage d'UI.
const routes = [
  { path: '/login', name: 'login', component: () => import('../views/LoginView.vue'), meta: { public: true } },
  { path: '/', name: 'cockpit', component: () => import('../views/CockpitView.vue') },
  { path: '/organisations', name: 'organisations', component: () => import('../views/OrganisationsView.vue') },
  { path: '/applications', name: 'applications', component: () => import('../views/ApplicationsView.vue') },
  { path: '/ressources', name: 'ressources', component: () => import('../views/RessourcesView.vue') },
  { path: '/audits', name: 'audits', component: () => import('../views/AuditsView.vue') },
  { path: '/audits/:id', name: 'audit-detail', component: () => import('../views/AuditDetailView.vue') },
  { path: '/exercices', name: 'exercices', component: () => import('../views/ExercicesView.vue') },
  { path: '/exercices/:id', name: 'exercice-detail', component: () => import('../views/ExerciceDetailView.vue') },
  { path: '/vulnerabilities', name: 'vulnerabilities', component: () => import('../views/VulnerabilitiesView.vue') },
  { path: '/tickets', name: 'tickets', component: () => import('../views/TicketsView.vue') },
  { path: '/parametres', name: 'parametres', component: () => import('../views/ParametresView.vue') },
  { path: '/bibliotheque', name: 'bibliotheque', component: () => import('../views/BibliothequeView.vue') },
  { path: '/deliverables', name: 'deliverables', component: () => import('../views/DeliverablesView.vue') },
  { path: '/attack-matrix', name: 'attack-matrix', component: () => import('../views/AttackMatrixView.vue') },
  { path: '/scenarios', name: 'scenarios', component: () => import('../views/ScenariosView.vue') },
  { path: '/evidence', name: 'evidence', component: () => import('../views/EvidenceView.vue') },
  { path: '/journal', name: 'journal', component: () => import('../views/JournalView.vue') },
  { path: '/account', name: 'account', component: () => import('../views/AccountView.vue') },
  { path: '/admin', name: 'admin', component: () => import('../views/AdminView.vue') },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.ready) await auth.fetchMe()
  if (to.meta.public) return true
  if (!auth.isAuthenticated) return { name: 'login', query: { r: to.fullPath } }
  return true
})

export default router
