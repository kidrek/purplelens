import { useState, useEffect, useRef, useCallback } from "react";
import { api } from "../api/client";

// Fallback local — utilisé si le catalogue n'est pas encore synchronisé
const FALLBACK = [
  { mitre_id: "T1059",   name: "Command and Scripting Interpreter", tactic: "Execution" },
  { mitre_id: "T1059.001", name: "PowerShell",                     tactic: "Execution" },
  { mitre_id: "T1059.003", name: "Windows Command Shell",          tactic: "Execution" },
  { mitre_id: "T1078",   name: "Valid Accounts",                   tactic: "Defense Evasion" },
  { mitre_id: "T1190",   name: "Exploit Public-Facing Application",tactic: "Initial Access" },
  { mitre_id: "T1566",   name: "Phishing",                        tactic: "Initial Access" },
  { mitre_id: "T1566.001", name: "Spearphishing Attachment",      tactic: "Initial Access" },
  { mitre_id: "T1003",   name: "OS Credential Dumping",           tactic: "Credential Access" },
  { mitre_id: "T1003.001", name: "LSASS Memory",                  tactic: "Credential Access" },
  { mitre_id: "T1021",   name: "Remote Services",                 tactic: "Lateral Movement" },
  { mitre_id: "T1041",   name: "Exfiltration Over C2 Channel",    tactic: "Exfiltration" },
  { mitre_id: "T1486",   name: "Data Encrypted for Impact",       tactic: "Impact" },
  { mitre_id: "T1490",   name: "Inhibit System Recovery",         tactic: "Impact" },
  { mitre_id: "T1071",   name: "Application Layer Protocol",      tactic: "Command and Control" },
  { mitre_id: "T1110",   name: "Brute Force",                     tactic: "Credential Access" },
  { mitre_id: "T1055",   name: "Process Injection",               tactic: "Defense Evasion" },
  { mitre_id: "T1053",   name: "Scheduled Task/Job",              tactic: "Persistence" },
  { mitre_id: "T1547",   name: "Boot or Logon Autostart Execution", tactic: "Persistence" },
  { mitre_id: "T1068",   name: "Exploitation for Privilege Escalation", tactic: "Privilege Escalation" },
  { mitre_id: "T1083",   name: "File and Directory Discovery",    tactic: "Discovery" },
];

function searchFallback(q) {
  const lq = q.toLowerCase().trim();
  return FALLBACK.filter(t =>
    t.mitre_id.toLowerCase().includes(lq) ||
    t.name.toLowerCase().includes(lq) ||
    t.tactic.toLowerCase().includes(lq)
  ).slice(0, 12);
}

/**
 * MitreTechniquePicker — champ de recherche ATT&CK avec sélection automatique de la tactique.
 *
 * Props :
 *   value      {{ mitre_id, name, tactic } | null} — technique sélectionnée
 *   onChange   {fn}  — callback(technique | null)
 *   placeholder {string}
 */
export function MitreTechniquePicker({ value, onChange, placeholder }) {
  const [query, setQuery]     = useState("");
  const [results, setResults] = useState([]);
  const [open, setOpen]       = useState(false);
  const [loading, setLoading] = useState(false);
  const inputRef   = useRef(null);
  const wrapRef    = useRef(null);
  const debounceRef = useRef(null);

  // Ferme le dropdown au clic extérieur
  useEffect(() => {
    function onDown(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, []);

  const search = useCallback(async (q) => {
    if (!q || q.trim().length < 1) { setResults([]); setOpen(false); return; }
    setLoading(true);
    try {
      const data = await api.mitreTechniqueSearch(q);
      if (Array.isArray(data) && data.length > 0) {
        setResults(data);
        setOpen(true);
        setLoading(false);
        return;
      }
    } catch (_) { /* fallback */ }
    // Fallback local si catalogue non synchronisé
    const local = searchFallback(q);
    setResults(local);
    setOpen(local.length > 0);
    setLoading(false);
  }, []);

  function handleInput(v) {
    setQuery(v);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(v), 200);
  }

  function select(tech) {
    onChange(tech);
    setQuery("");
    setOpen(false);
    inputRef.current?.focus();
  }

  function clear() {
    onChange(null);
    setQuery("");
    setResults([]);
    setOpen(false);
    inputRef.current?.focus();
  }

  return (
    <div className="mtp-wrap" ref={wrapRef}>
      {/* Technique sélectionnée */}
      {value ? (
        <div className="mtp-selected">
          <div className="mtp-selected-info">
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span className="mtp-selected-id">{value.mitre_id}</span>
              <span className="mtp-selected-name">{value.name}</span>
            </div>
            <div className="mtp-selected-tactic">
              Tactique :
              <span className="mtp-tactic-pill">{value.tactic}</span>
            </div>
          </div>
          <button className="mtp-clear" onClick={clear} title="Changer de technique">×</button>
        </div>
      ) : (
        <>
          {/* Champ de recherche */}
          <div className="mtp-search-wrap">
            <span className="mtp-search-icon">{loading ? "…" : "⌕"}</span>
            <input
              ref={inputRef}
              type="text"
              className="input mtp-input"
              value={query}
              onChange={e => handleInput(e.target.value)}
              onFocus={() => query.trim().length >= 1 && setOpen(true)}
              placeholder={placeholder || "Rechercher une technique ATT&CK… ex: T1059, phishing, credential"}
              autoComplete="off"
            />
          </div>

          {/* Dropdown résultats */}
          {open && results.length > 0 && (
            <div className="mtp-dropdown">
              <div className="mtp-dd-head">
                Catalogue ATT&CK — {results.length} résultat{results.length > 1 ? "s" : ""}
              </div>
              {results.map(t => (
                <div
                  key={t.mitre_id}
                  className="mtp-dd-item"
                  onMouseDown={e => { e.preventDefault(); select(t); }}
                >
                  <span className="mtp-dd-id">{t.mitre_id}</span>
                  <span className="mtp-dd-body">
                    <span className="mtp-dd-name">{t.name}</span>
                    <span className="mtp-dd-tactic">{t.tactic}</span>
                  </span>
                </div>
              ))}
            </div>
          )}
          {open && query.trim().length >= 1 && results.length === 0 && (
            <div className="mtp-dropdown">
              <div className="mtp-dd-item" style={{ pointerEvents: "none", color: "var(--text-faint)" }}>
                Aucun résultat — synchronisez le catalogue dans Paramètres
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
