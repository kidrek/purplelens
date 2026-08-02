// Tons (pills) partagés entre la liste des scénarios et leur drawer — une seule
// source de vérité pour la correspondance valeur -> couleur (classes .pill-*).
export const ENGAGEMENT_LABEL = { 'red-team': 'Red', 'purple-team': 'Purple', 'tabletop': 'Tabletop', 'assumed-breach': 'Assumed Breach' }
export const ENGAGEMENT_TONE = { 'red-team': 'red', 'purple-team': 'violet', 'tabletop': 'cyan', 'assumed-breach': 'amber' }
export const TLP_TONE = { RED: 'red', AMBER: 'amber', GREEN: 'green', WHITE: 'gray', CLEAR: 'gray' }
// Gradation de sophistication : neutre -> alerte à mesure que le niveau requis monte.
export const SOPH_TONE = { basique: 'gray', intermediaire: 'cyan', avancee: 'amber', apt: 'red' }
// Crédibilité Admiralty (1..6) : 1-2 fiable, 3 possible, 4 douteuse, 5-6 faible.
export const credTone = (v) => (v <= 2 ? 'green' : v === 3 ? 'cyan' : v === 4 ? 'amber' : 'gray')

// Statut d'un exercice Purple (= statut d'audit) -> ton de pill. Progression neutre :
// planifié (à venir) -> en cours (actif, violet) -> terminé (vert), suspendu (alerte),
// annulé (neutre). Source unique partagée liste + tiroir.
export const STATUT_EXO_TONE = { planifie: 'blue', en_cours: 'violet', termine: 'green', suspendu: 'amber', annule: 'gray' }

// Sévérité d'une vulnérabilité -> ton de pill. `elevee` est un synonyme historique de
// `haute` présent dans d'anciens imports. Source unique partagée par les tiroirs qui
// listent des vulnérabilités (Organisation, Personne).
export const SEVERITE_TONE = { critique: 'red', haute: 'amber', elevee: 'amber', moyenne: 'cyan', basse: 'green' }

// Verdict défensif d'une étape (spec §2) -> ton de pill. Source unique partagée entre le
// tiroir d'exercice et la page de détail /exercices/:id. « prévenu » et « alerté » comptent
// tous deux comme une détection réussie (vert) — cohérent avec l'agrégation `detected` et la
// barre de posture ; « journalisé » = signal capté mais non alerté (ambre) ; « sans
// télémétrie » = angle mort (rouge) ; « non testé » = neutre.
export const VERDICT_TONE = { prevented: 'green', alerted: 'green', logged: 'amber', no_telemetry: 'red', not_tested: 'gray' }
