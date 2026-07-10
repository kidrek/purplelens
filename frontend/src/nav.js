// Navigation groupée, partagée entre le menu latéral et la palette ⌘K.
// Reproduit les groupes de la maquette : Pilotage / Connaissance / Livrables / Système.
// `count` = nom d'entité pour le badge de dénombrement (via /{entity}?limit=1 → total).
// `adminOnly` masque l'entrée hors rôle admin.
export const NAV_GROUPS = [
  {
    id: 'pilotage',
    items: [
      { id: 'cockpit', icon: 'gauge', to: '/' },
      { id: 'exercices', icon: 'loop', to: '/exercices', count: 'exercices' },
      { id: 'audits', icon: 'clipboard', to: '/audits', count: 'audits' },
      { id: 'vulnerabilities', icon: 'bug', to: '/vulnerabilities', count: 'vulnerabilities' },
      { id: 'tickets', icon: 'ticket', to: '/tickets', count: 'tickets' },
    ],
  },
  {
    id: 'connaissance',
    items: [
      { id: 'attack-matrix', icon: 'grid', to: '/attack-matrix' },
      { id: 'scenarios', icon: 'target', to: '/scenarios', count: 'scenarios' },
      { id: 'applications', icon: 'app', to: '/applications', count: 'applications' },
      { id: 'organisations', icon: 'building', to: '/organisations', count: 'organisations' },
      { id: 'ressources', icon: 'users', to: '/ressources', count: 'ressources' },
    ],
  },
  {
    id: 'livrables',
    items: [
      { id: 'deliverables', icon: 'doc', to: '/deliverables', count: 'deliverables' },
      { id: 'journal', icon: 'shield', to: '/journal' },
      { id: 'evidence', icon: 'folder', to: '/evidence' },
    ],
  },
  {
    id: 'systeme',
    items: [
      { id: 'bibliotheque', icon: 'book', to: '/bibliotheque', count: 'corpus' },
      { id: 'parametres', icon: 'gear', to: '/parametres' },
      { id: 'admin', icon: 'users', to: '/admin', adminOnly: true },
    ],
  },
]

// Liste à plat (pour la palette de commandes).
export const NAV_FLAT = NAV_GROUPS.flatMap((g) => g.items)
