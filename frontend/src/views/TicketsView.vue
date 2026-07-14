<script setup>
import EntityTable from '../components/EntityTable.vue'
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
const prio = (v) => ({ P1: 'red', P2: 'amber', P3: 'cyan', P4: 'gray' }[v] || 'gray')
const cols = [
  { key: 'reference', label: 'Référence' },
  { key: 'technique_attack', label: 'Technique ATT&CK' },
  { key: 'mesure_d3fend', label: 'Mesure D3FEND' },
  { key: 'priorite', label: 'Priorité', pill: prio },
  { key: 'statut', label: 'Statut', pill: () => 'cyan' },
  { key: 'regle_sigma', label: 'Règle Sigma' },
]
</script>
<template>
  <div><div class="eyebrow">{{ t('views.tickets.eyebrow') }}</div><h1>{{ t('views.tickets.title') }}</h1>
    <!-- Pas de création directe : un ticket doit être rattaché à une étape en angle mort
         (créé depuis la page Exercices Purple). Édition/suppression conservées. -->
    <EntityTable entity="tickets" :columns="cols" title="ticket" :allow-create="false" /></div>
</template>
