<script setup>
import EntityTable from '../components/EntityTable.vue'
import OrganisationDrawer from '../components/OrganisationDrawer.vue'
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
const cols = [
  { key: 'code', label: 'Code' },
  { key: 'nom', label: 'Nom' },
  { key: 'role', label: 'Rôle', pill: () => 'violet' },
  { key: 'secteur', label: 'Secteur' },
  { key: 'tlp_defaut', label: 'TLP', tlp: true },
]
</script>
<template>
  <div><div class="eyebrow">{{ t('views.organisations.eyebrow') }}</div><h1>{{ t('views.organisations.title') }}</h1>
    <EntityTable entity="organisations" :columns="cols" title="organisation" :drawer="OrganisationDrawer" /></div>
</template>
