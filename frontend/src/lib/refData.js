/**
 * Référentiels de sécurité locaux — données de fallback.
 *
 * Ces données sont utilisées si le backend ne dispose pas encore d'entrées
 * synchronisées (premier démarrage, mode offline strict).
 * La mise à jour via la page Paramètres remplace ces données par celles
 * stockées en base, plus complètes.
 */

// ── OWASP Top 10 (2021) ──────────────────────────────────────────────────────
export const OWASP_FALLBACK = [
  { ref_id: "A01:2021", name: "Broken Access Control",
    description: "Les restrictions sur ce que les utilisateurs peuvent faire ne sont pas appliquées." },
  { ref_id: "A02:2021", name: "Cryptographic Failures",
    description: "Données sensibles exposées par chiffrement insuffisant ou absent." },
  { ref_id: "A03:2021", name: "Injection",
    description: "SQL, NoSQL, OS, LDAP injection via données non fiables envoyées à un interpréteur." },
  { ref_id: "A04:2021", name: "Insecure Design",
    description: "Défauts de conception et d'architecture présentant des risques de sécurité." },
  { ref_id: "A05:2021", name: "Security Misconfiguration",
    description: "Configurations de sécurité manquantes, incorrectes ou par défaut." },
  { ref_id: "A06:2021", name: "Vulnerable and Outdated Components",
    description: "Composants présentant des vulnérabilités connues ou non maintenus." },
  { ref_id: "A07:2021", name: "Identification and Authentication Failures",
    description: "Failles dans la gestion de l'identité, de l'authentification et des sessions." },
  { ref_id: "A08:2021", name: "Software and Data Integrity Failures",
    description: "Code et infrastructure sans vérification d'intégrité." },
  { ref_id: "A09:2021", name: "Security Logging and Monitoring Failures",
    description: "Journalisation insuffisante pour détecter et réagir aux incidents." },
  { ref_id: "A10:2021", name: "Server-Side Request Forgery",
    description: "Requêtes forgées côté serveur vers des ressources internes ou arbitraires." },
];

// ── CWE — Common Weakness Enumeration (sélection des plus fréquentes) ────────
export const CWE_FALLBACK = [
  { ref_id: "CWE-20",  name: "Improper Input Validation",
    description: "L'entrée n'est pas validée correctement, permettant des opérations non prévues." },
  { ref_id: "CWE-22",  name: "Path Traversal",
    description: "Chemin de fichier contenant des séquences \"../\" non nettoyées." },
  { ref_id: "CWE-78",  name: "OS Command Injection",
    description: "Commandes OS construites depuis des entrées utilisateur non sécurisées." },
  { ref_id: "CWE-79",  name: "Cross-site Scripting (XSS)",
    description: "Scripts injectés dans des pages web vus par d'autres utilisateurs." },
  { ref_id: "CWE-89",  name: "SQL Injection",
    description: "Requêtes SQL construites depuis des entrées utilisateur non filtrées." },
  { ref_id: "CWE-94",  name: "Code Injection",
    description: "Exécution de code non prévu injecté par l'attaquant." },
  { ref_id: "CWE-119", name: "Buffer Overflow",
    description: "Opérations mémoire effectuées hors des limites allouées du buffer." },
  { ref_id: "CWE-200", name: "Exposure of Sensitive Information",
    description: "Divulgation involontaire d'informations sensibles à un acteur non autorisé." },
  { ref_id: "CWE-276", name: "Incorrect Default Permissions",
    description: "Permissions par défaut trop permissives accordées aux ressources." },
  { ref_id: "CWE-287", name: "Improper Authentication",
    description: "L'identité de l'acteur n'est pas correctement vérifiée." },
  { ref_id: "CWE-306", name: "Missing Authentication for Critical Function",
    description: "Fonction critique accessible sans contrôle d'identité." },
  { ref_id: "CWE-352", name: "Cross-Site Request Forgery (CSRF)",
    description: "Requêtes non autorisées transmises depuis un site de confiance." },
  { ref_id: "CWE-434", name: "Unrestricted Upload of File with Dangerous Type",
    description: "Upload de fichiers sans restriction suffisante sur le type." },
  { ref_id: "CWE-502", name: "Deserialization of Untrusted Data",
    description: "Désérialisation de données provenant d'une source non fiable." },
  { ref_id: "CWE-611", name: "XML External Entity (XXE)",
    description: "Traitement XML acceptant des entités externes non contrôlées." },
  { ref_id: "CWE-798", name: "Use of Hard-coded Credentials",
    description: "Identifiants codés en dur dans le code source ou la configuration." },
  { ref_id: "CWE-862", name: "Missing Authorization",
    description: "Contrôle d'accès absent pour accéder à une ressource ou fonction." },
  { ref_id: "CWE-918", name: "Server-Side Request Forgery (SSRF)",
    description: "Le serveur est amené à effectuer des requêtes vers des ressources arbitraires." },
];

// ── CAPEC — Common Attack Pattern Enumeration ─────────────────────────────────
export const CAPEC_FALLBACK = [
  { ref_id: "CAPEC-7",   name: "Blind SQL Injection",
    description: "Injection SQL sans retour d'erreur visible, basée sur des réponses conditionnelles." },
  { ref_id: "CAPEC-17",  name: "XSS Using HTTP Query Strings",
    description: "Injection de script malveillant via les paramètres de l'URL." },
  { ref_id: "CAPEC-28",  name: "XSS Targeting HTML Attributes",
    description: "Script injecté dans des attributs HTML pour contourner les filtres." },
  { ref_id: "CAPEC-62",  name: "Cross-Site Request Forgery",
    description: "Exploitation de la confiance d'un site envers le navigateur d'un utilisateur." },
  { ref_id: "CAPEC-66",  name: "SQL Injection",
    description: "Requêtes SQL forgées via des entrées utilisateur non filtrées." },
  { ref_id: "CAPEC-86",  name: "XSS Through HTTP Headers",
    description: "Script injecté dans les en-têtes HTTP reflétés dans la réponse." },
  { ref_id: "CAPEC-98",  name: "Phishing",
    description: "Tromperie d'un utilisateur pour obtenir des informations sensibles." },
  { ref_id: "CAPEC-112", name: "Brute Force",
    description: "Essais exhaustifs de combinaisons pour deviner un secret (mot de passe, clé)." },
  { ref_id: "CAPEC-116", name: "Excavation",
    description: "Collecte d'informations via des canaux de communication non intentionnels." },
  { ref_id: "CAPEC-122", name: "Privilege Abuse",
    description: "Abus de privilèges légitimes pour effectuer des accès non autorisés." },
  { ref_id: "CAPEC-193", name: "PHP Remote File Inclusion",
    description: "Inclusion distante de fichiers PHP malveillants via paramètre non filtré." },
  { ref_id: "CAPEC-209", name: "XSS Using MIME Type Mismatch",
    description: "Exploitation des incohérences de types MIME pour déclencher un XSS." },
  { ref_id: "CAPEC-438", name: "Padding Oracle Cryptanalysis",
    description: "Exploitation des messages d'erreur de padding pour décrypter des données." },
  { ref_id: "CAPEC-664", name: "Server Side Request Forgery",
    description: "Forçage du serveur à effectuer des requêtes vers des ressources internes." },
];

// Mapping nom → fallback local
const FALLBACKS = {
  owasp: OWASP_FALLBACK,
  cwe:   CWE_FALLBACK,
  capec: CAPEC_FALLBACK,
};

/**
 * Recherche dans le fallback local (utilisée quand le backend n'a pas d'entrées).
 */
export function searchLocal(referential, query, limit = 15) {
  if (!query || query.trim().length < 1) return [];
  const q = query.toLowerCase().trim();
  const data = FALLBACKS[referential] || [];
  return data
    .filter(e =>
      e.ref_id.toLowerCase().includes(q) ||
      e.name.toLowerCase().includes(q) ||
      e.description.toLowerCase().includes(q)
    )
    .slice(0, limit);
}

/**
 * Parse la valeur JSON stockée en base pour un champ de référentiel.
 * Format stocké : JSON array de { ref_id, name }
 */
export function parseRefValue(raw) {
  if (!raw) return [];
  try { return JSON.parse(raw); } catch { return []; }
}

/**
 * Sérialise le tableau de références pour stockage backend.
 */
export function serializeRefValue(items) {
  return JSON.stringify(items.map(({ ref_id, name }) => ({ ref_id, name })));
}

/**
 * Génère la chaîne lisible (ex: "A03:2021, CWE-89") depuis le tableau.
 */
export function refToReadable(items) {
  return items.map(i => i.ref_id).join(", ");
}
