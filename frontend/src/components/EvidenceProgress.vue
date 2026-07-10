<script setup>
// Progression du sas d'ingestion d'une preuve (cahier §6quater). Le backend ne
// persiste que 3 statuts (workers/tasks.py) : quarantined (défaut) → stored (succès)
// ou rejected (échec AV / type / taille) — le sas interne (AV, type réel, chiffrement,
// WORM, journal) est atomique côté worker et n'est pas exposé étape par étape.
// Couleur par état : DA §5.2/§0.5 — quarantined = neutre, stored = vert, rejected = rouge
// (réemploi strict, aucun token nouveau). La couleur n'est jamais seule porteuse : le
// libellé d'état reste toujours affiché à côté (DA §6).
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  status: { type: String, default: 'quarantined' },
})
const { t } = useI18n()

const TONE = {
  quarantined: { pct: 33, cls: 'neutral', label: () => t('evidence.quarantine') },
  stored: { pct: 100, cls: 'ok', label: () => t('evidence.stored') },
  rejected: { pct: 100, cls: 'ko', label: () => t('evidence.rejected') },
}
const tone = computed(() => TONE[props.status] || TONE.quarantined)
</script>

<template>
  <div class="evi-progress" :class="tone.cls">
    <div class="track">
      <div class="fill" :style="{ width: tone.pct + '%' }"></div>
    </div>
    <div class="label">{{ tone.label() }}</div>
  </div>
</template>

<style scoped>
.evi-progress{margin:8px 0}
.track{height:6px;border-radius:99px;background:var(--surface-3);overflow:hidden;border:1px solid var(--border-2)}
.fill{height:100%;transition:width var(--t) var(--ease);background:var(--faint)}
.label{margin-top:5px;font-size:10px;color:var(--faint);font-family:var(--font-data);text-transform:uppercase;letter-spacing:.03em}
/* quarantined : neutre */
.evi-progress.neutral .fill{background:var(--faint)}
/* stored : vert */
.evi-progress.ok .fill{background:var(--c-green-tx)}
.evi-progress.ok .label{color:var(--c-green-tx)}
/* rejected : rouge */
.evi-progress.ko .fill{background:var(--c-red-tx)}
.evi-progress.ko .label{color:var(--c-red-tx)}
</style>
