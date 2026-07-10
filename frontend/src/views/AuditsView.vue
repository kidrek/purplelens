<script setup>
import EntityTable from '../components/EntityTable.vue'
import AuditDrawer from '../components/AuditDrawer.vue'
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
const cols = [
  { key: 'nom', label: 'Réf.' },
  { key: 'categorie', label: 'Catégorie' },
  { key: 'type_test', label: 'Type' },
  { key: 'statut', label: 'Statut', pill: () => 'cyan' },
  { key: 'priorite', label: 'Priorité' },
  { key: 'tlp', label: 'TLP', tlp: true },
]
</script>
<template>
  <div><div class="eyebrow">{{ t('views.audits.eyebrow') }}</div><h1>{{ t('views.audits.title') }}</h1>
    <EntityTable entity="audits" :columns="cols" title="audit" :detail-route="(r) => `/audits/${r.id}`" :drawer="AuditDrawer" /></div>
</template>
