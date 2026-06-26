# Direction artistique — Module 3 · Gestion des audits

**PurpleLens · Security Validation · v1.0**

---

## 1. Philosophie de design

**Interface sombre à haute densité d'information.**
Le fond principal est `#0F0E1A`, les cartes sont légèrement relevées à `#12111F`. La hiérarchie visuelle repose sur la luminosité des surfaces, sans ombres portées ni dégradés.

**Couleur = signal, pas décoration.**
Les couleurs sont exclusivement sémantiques. Le type d'audit (Red Team, Pentest, BAS...) s'affiche en texte violet sans badge coloré pour ne pas parasiter la lecture des métriques de performance.

**Glow sur les graphiques uniquement.**
L'effet néon (`box-shadow` coloré) est appliqué aux barres de progression et aux points de statut actif. Le texte reste net — aucun `text-shadow`.

**Cohérence avec le code existant.**
Les `border-radius`, conventions de badge et styles de chip s'alignent sur le `styles.css` du projet : `6px` pour les pills de sévérité, `7px` pour les chips de filtre.

---

## 2. Palette de couleurs

| Rôle | Nom | Hex |
|------|-----|-----|
| Fond principal | bg | `#0F0E1A` |
| Surface / carte | surface | `#12111F` |
| Bordure | border | `#2A2840` |
| Texte primaire | textPrim | `#E0DFF8` |
| Texte secondaire / muted | textSec | `#6B6788` |
| Violet — accent, métriques neutres | purple | `#A78BFA` |
| Violet foncé — UI, boutons | purpleDark | `#7C70D8` |
| Vert — détection, succès | green | `#4ADE80` |
| Amber — avertissement, MTTD | amber | `#FBBF24` |
| Rouge — critique, alerte | red | `#E03C52` |
| Bleu — score global, statut actif | blue | `#60A5FA` |
| Orange — sévérité High | orange | `#FB923C` |

---

## 3. Typographie

Police unique : **Arial**. Deux graisses seulement : `400` (regular) et `500`–`600` (medium/semi-bold). Jamais de `700` sur fond sombre.

| Élément | Taille | Graisse | Couleur | Contexte |
|---------|--------|---------|---------|----------|
| Titre de page | 28px | 500 | `#FFFFFF` | Nom du module |
| Module tag | 12px | 500 | `#7C70D8` | Uppercase, `letter-spacing: 0.08em` |
| Sous-titre | 14px | 400 | `#6B6788` | Description de la page |
| KPI — valeur | 32px | 500 | Couleur sémantique | Grande métrique |
| KPI — label | 11px | 500 | `#6B6788` | Uppercase, `letter-spacing: 0.08em` |
| KPI — delta | 12px | 400 | Vert / Rouge | Variation vs période précédente |
| En-tête de colonne | 10px | 500 | `#6B6788` | Uppercase, `letter-spacing: 0.08em` |
| Nom d'audit | 13px | 500 | `#E0DFF8` | Ligne principale du tableau |
| App / scénario | 11px | 400 | `#6B6788` | Sous-ligne du tableau |
| Type d'audit | 12px | 600 | `#A78BFA` | Texte seul — aucun fond, aucune bordure |
| Statut | 12px | 400 | `#6B6788` | Avec point coloré |
| Score / % | 14px | 500 | Couleur sémantique | Valeur dans le tableau |
| Pill sévérité | 11px | 600 | Couleur sémantique | `border-radius: 5px` |
| Label graphique | 10px | 500 | `#6B6788` | Uppercase, mini-charts |

---

## 4. Niveaux de sévérité

`border-radius: 5px` — conforme au `.badge` défini dans `styles.css`.
Le fond des pills est la couleur texte à **18% d'opacité**.

| Niveau | Couleur texte | Fond pill | Usage |
|--------|--------------|-----------|-------|
| Critical | `#E03C52` | `rgba(224, 60, 82, 0.18)` | Vulnérabilités critiques, findings bloquants |
| High | `#FB923C` | `rgba(251, 146, 60, 0.14)` | Sévérité haute, action rapide requise |
| Medium | `#9B97B8` | `rgba(155, 151, 184, 0.14)` | Sévérité intermédiaire |
| Low | `#6B6788` | `rgba(107, 103, 136, 0.14)` | Sévérité faible, gris neutre |
| Info | `#6B6788` | — | Note contextuelle, sans pill |

---

## 5. Composants

| Composant | Propriétés CSS clés | Notes |
|-----------|---------------------|-------|
| KPI card | `bg: #12111F` · `border: 0.5px #2A2840` · `border-radius: 10px` · `padding: 16px 18px` | Barre de progression en bas (`height: 2px`) |
| Table | `bg: #12111F` · `border: 0.5px #2A2840` · `border-radius: 12px` · `overflow: hidden` | Séparateurs de lignes : `0.5px #1A192C` |
| Badge type d'audit | `color: #A78BFA` · `font-weight: 600` · `font-size: 12px` | Texte seul — aucun fond, aucune bordure |
| Pill sévérité | `border-radius: 5px` · `padding: 2px 7px` · fond à 18% opacité | Issu du `styles.css` existant |
| Chip filtre | `border-radius: 7px` · `border: 1px solid` · `padding: 4px 12px` | Actif : `bg #1E1A40` · `border #7C70D8` |
| Barre de score | `height: 3px` · `border-radius: 2px` · `bg: #1E1D30` | Fill coloré avec `box-shadow` glow |
| Effet glow | `box-shadow: 0 0 8px {couleur}CC` | Barres et points uniquement — jamais sur le texte |
| Bouton action | `width/height: 28px` · `border-radius: 6px` · `bg: #1A192C` · `border: 0.5px #2A2840` | Hover : `border #7C70D8`, `color #A89FFF` |
| Bouton primaire | `bg: #7C70D8` · `border-radius: 8px` · `color: #FFF` · `padding: 6px 14px` | « + Nouvel audit » |
| Point de statut | `width/height: 6px` · `border-radius: 50%` | In Progress : `#60A5FA` avec glow · Autres : `#6B6788` |

---

## 6. KPI opérationnels & stratégiques

| KPI | Couleur | Source de données | Signification |
|-----|---------|-------------------|---------------|
| Audits actifs | Violet `#A78BFA` | `audits.status` | Audits en cours vs total |
| Taux détection moy. | Vert `#4ADE80` | `detection_assessments.detected` | Ratio détection sur toutes les techniques évaluées |
| MTTD moyen | Amber `#FBBF24` | `detection_assessments.detection_time_min` | Mean Time To Detect — réactivité SOC |
| Findings ouverts | Rouge `#E03C52` | `findings.status = open` | Vulnérabilités non résolues, focus critiques |
| Score global | Bleu `#60A5FA` | Calcul composite | Indicateur stratégique agrégé sur 100 |

---

## 7. Mini-graphiques analytiques

Deux widgets en bas de page, en grille `1fr 1fr`.

**Détection par tactique ATT&CK**
Barres horizontales colorées selon le taux : vert ≥ 70%, amber entre 40–69%, rouge < 40%. Labels et valeurs en `#6B6788`.

**Findings par sévérité**
Compteurs numériques (32px, couleur sémantique) + barres de statut (Open / In Progress / Fixed). Même logique de couleur que les pills.

---

## 8. Règles à respecter

### À ne jamais faire

- Utiliser `text-shadow` / halo sur le texte — le glow est réservé aux éléments graphiques
- Donner une couleur différente par type d'audit (Red Team, Pentest...) — tous en violet neutre
- Dépasser `border-radius: 7px` sur les chips ou `6px` sur les pills
- Utiliser des emojis — remplacés par des icônes Tabler outline uniquement
- Appliquer un fond ou une bordure colorée sur les badges de type d'audit
- Déroger au gris `#6B6788` pour les textes secondaires et la sévérité Low

### À toujours faire

- Réserver les couleurs sémantiques (vert, amber, rouge) aux métriques de performance
- Appliquer le glow (`box-shadow`) sur les barres de score et les points de statut actif
- Utiliser Arial en graisses `400` et `500`/`600` uniquement
- Aligner les `border-radius` sur le `styles.css` existant : `6px` pills, `7px` chips, `10–12px` cartes
- Maintenir `#6B6788` pour tous les textes secondaires, labels muted et sévérité Low
- Conserver `#0F0E1A` pour le fond de page, `#12111F` pour les cartes

---

*PurpleLens · Direction Artistique · Module 3 · v1.0*
