<script setup>
import EntityTable from '../components/EntityTable.vue'
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
const cols = [
  { key: 'nom', label: 'Réf.' },
  { key: 'equipe', label: 'Équipe' },
  { key: 'statut', label: 'Statut', pill: () => 'cyan' },
  { key: 'run_number', label: 'Run' },
  { key: 'tlp', label: 'TLP', tlp: true },
]
</script>
<template>
  <div><div class="eyebrow">{{ t('views.exercices.eyebrow') }}</div><h1>{{ t('views.exercices.title') }}</h1>
    <EntityTable entity="exercices" :columns="cols" title="exercice" :detail-route="(r) => `/exercices/${r.id}`" /></div>
</template>
