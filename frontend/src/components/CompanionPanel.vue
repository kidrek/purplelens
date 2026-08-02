<script setup>
import { defineAsyncComponent } from 'vue'
import AuditDrawer from './AuditDrawer.vue'
import ExerciceDrawer from './ExerciceDrawer.vue'
import VulnDrawer from './VulnDrawer.vue'

// RessourceDrawer nous importe (il est hôte sur /ressources) et nous l'importons (il est
// compagnon depuis une organisation) : import circulaire. Le charger en asynchrone rompt
// le cycle au niveau du graphe de modules, plutôt que de dépendre de l'ordre d'évaluation.
const RessourceDrawer = defineAsyncComponent(() => import('./RessourceDrawer.vue'))

// Panneau compagnon : le tiroir accolé à GAUCHE d'un tiroir hôte (cf. useDrawerPair.js).
// Monté en frère du DetailDrawer de l'hôte — son teleport le sort du DOM, mais il reste
// un descendant de composant, ce qui lui fait hériter du registre d'appairage.
//
// Ce composant concentre les deux règles qui ne se devinent pas :
//   1. quel composant pour quel `kind` ;
//   2. QUELLE FORME d'enregistrement chaque tiroir accepte (voir le tableau ci-dessous).
// Sans ça, chaque hôte les redécouvrirait — et se tromperait.
defineProps({
  companion: { type: Object, required: true }, // { kind, record }
})
// `open` : nouvelle cible demandée par un lien du compagnon, qui le remplace en place.
const emit = defineEmits(['open', 'close'])
</script>

<template>
  <!-- Le `:key` sur l'id est indispensable : un enchaînement de même nature (audit →
       exercice → audit) réutiliserait sinon l'instance sans rejouer onMounted, et le
       panneau afficherait les données de l'entité précédente. -->

  <!-- AuditDrawer se recharge par id : `{ id }` suffit. -->
  <AuditDrawer
    v-if="companion.kind === 'audit'"
    :key="companion.record.id"
    readonly
    :record="{ id: companion.record.id }"
    @open-entity="emit('open', $event)"
    @close="emit('close')"
  />
  <!-- ExerciceDrawer ne recharge pas par id et pivote sur audit_id / client_id :
       il lui faut l'enregistrement complet. -->
  <ExerciceDrawer
    v-else-if="companion.kind === 'exercice'"
    :key="companion.record.id"
    readonly
    :record="companion.record"
    @open-entity="emit('open', $event)"
    @close="emit('close')"
  />
  <!-- VulnDrawer fusionne prop-par-dessus-fetch : ne transmettre QUE l'id, sans quoi une
       ligne de liste périmée écraserait durablement l'enregistrement frais. -->
  <VulnDrawer
    v-else-if="companion.kind === 'vuln'"
    :key="companion.record.id"
    readonly
    :vuln="{ id: companion.record.id }"
    @open-entity="emit('open', $event)"
    @close="emit('close')"
  />
  <!-- RessourceDrawer ne recharge pas la personne par id : enregistrement complet. -->
  <RessourceDrawer
    v-else-if="companion.kind === 'ressource'"
    :key="companion.record.id"
    readonly
    :record="companion.record"
    @open-entity="emit('open', $event)"
    @close="emit('close')"
  />
</template>
