<script setup>
import EntityTable from '../components/EntityTable.vue'
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
const cols = [
  { key: 'nom', label: 'Nom' },
  { key: 'type', label: 'Type', pill: () => 'violet' },
  { key: 'role', label: 'Rôle' },
  { key: 'contact', label: 'Contact' },
]
</script>
<template>
  <div><div class="eyebrow">{{ t('views.ressources.eyebrow') }}</div><h1>{{ t('views.ressources.title') }}</h1>
    <EntityTable entity="ressources" :columns="cols" title="ressource" /></div>
</template>
