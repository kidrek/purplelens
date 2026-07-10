import { useI18n } from 'vue-i18n'

// Traduit les libellés au niveau des données : label d'un champ (par sa clé) et valeur
// d'énumération (par sa valeur brute). Repli gracieux sur la chaîne fournie si aucune
// traduction n'existe — on n'affiche jamais une clé nue.
export function useLabels() {
  const { t, te } = useI18n()

  // Libellé d'un champ : fields.<key>, sinon le label du schéma, sinon la clé.
  function fieldLabel(f) {
    const k = typeof f === 'string' ? f : f.key
    if (te(`fields.${k}`)) return t(`fields.${k}`)
    return (typeof f === 'object' && f.label) || k
  }

  // Valeur d'énumération : enum.<value> si connue, sinon la valeur brute.
  function enumLabel(v) {
    if (typeof v !== 'string' || !v) return v
    return te(`enum.${v}`) ? t(`enum.${v}`) : v
  }

  return { fieldLabel, enumLabel }
}
