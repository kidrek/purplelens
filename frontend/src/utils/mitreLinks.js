// URLs de référence vers les sites officiels MITRE, pour rendre les chips ATT&CK/D3FEND
// cliquables. Pas d'appel réseau ici : construction déterministe à partir des données déjà
// résolues localement (ext_id / nom via les référentiels embarqués ou synchronisés).

// ATT&CK : ext_id "T1190" -> /techniques/T1190/ ; sous-technique "T1566.001" -> le site
// MITRE utilise un slash dans l'URL (/techniques/T1566/001/), pas le point d'affichage.
export function attackUrl(extId) {
  if (!extId) return null
  const [base, sub] = String(extId).split('.')
  return sub
    ? `https://attack.mitre.org/techniques/${base}/${sub}/`
    : `https://attack.mitre.org/techniques/${base}/`
}

// D3FEND : le site identifie chaque technique par un slug CamelCase dérivé de son nom
// (ex. "Network Traffic Analysis" -> d3f:NetworkTrafficAnalysis), pas par le code court
// (D3-NTA) porté par notre référentiel. On dérive donc le slug depuis le nom résolu.
export function d3fendUrl(name) {
  if (!name) return null
  const slug = String(name).replace(/[^A-Za-z0-9]+/g, '')
  return slug ? `https://d3fend.mitre.org/technique/d3f:${slug}/` : null
}
