import { useState, useEffect, useRef, useCallback } from "react";
import { createPortal } from "react-dom";
import { searchLocal, parseRefValue, serializeRefValue, refToReadable } from "../lib/refData";

const CONFIG = {
  owasp: {
    label: "OWASP Top 10",
    placeholder: "Rechercher… ex: injection, access control, logging",
    chipClass: "ref-chip ref-chip-owasp",
    badgeClass: "ref-badge ref-badge-owasp",
    accentColor: "#854F0B",
  },
  cwe: {
    label: "CWE",
    placeholder: "Rechercher… ex: CWE-89, injection, buffer, auth",
    chipClass: "ref-chip ref-chip-cwe",
    badgeClass: "ref-badge ref-badge-cwe",
    accentColor: "#0F6E56",
  },
  capec: {
    label: "CAPEC",
    placeholder: "Rechercher… ex: CAPEC-66, sql, brute force, xss",
    chipClass: "ref-chip ref-chip-capec",
    badgeClass: "ref-badge ref-badge-capec",
    accentColor: "#534AB7",
  },
};

export function RefPicker({ referential, valueRaw, onChange }) {
  const [selected, setSelected] = useState([]);
  const [query, setQuery]       = useState("");
  const [results, setResults]   = useState([]);
  const [open, setOpen]         = useState(false);
  const [loading, setLoading]   = useState(false);
  const [dropPos, setDropPos]   = useState({ top: 0, left: 0, width: 0 });

  const inputRef    = useRef(null);
  const debounceRef = useRef(null);
  const cfg = CONFIG[referential] || CONFIG.owasp;

  useEffect(() => {
    setSelected(parseRefValue(valueRaw));
  }, [valueRaw]);

  // Ferme le dropdown au clic extérieur (attaché au document)
  useEffect(() => {
    if (!open) return;
    function onMouseDown(e) {
      if (inputRef.current && !inputRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onMouseDown);
    return () => document.removeEventListener("mousedown", onMouseDown);
  }, [open]);

  /**
   * Calcule la position du dropdown par rapport au document entier
   * (getBoundingClientRect + scrollY/scrollX) pour être indépendant
   * de tout contexte de rendu composite (backdrop-filter, transform…).
   * Le dropdown est rendu via createPortal directement dans <body>,
   * donc position:absolute par rapport à document, pas au viewport.
   */
  function computeDropPos() {
    if (!inputRef.current) return;
    const r = inputRef.current.getBoundingClientRect();
    setDropPos({
      top:   r.bottom + window.scrollY + 2,
      left:  r.left   + window.scrollX,
      width: r.width,
    });
  }

  const search = useCallback(async (q) => {
    if (!q || q.trim().length < 1) { setResults([]); setOpen(false); return; }
    setLoading(true);
    try {
      const res = await fetch(
        `/api/referentials/${referential}/entries?q=${encodeURIComponent(q)}&limit=12`
      );
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) {
          setResults(data);
          computeDropPos();
          setOpen(true);
          setLoading(false);
          return;
        }
      }
      console.warn(`[RefPicker] ${referential}: HTTP ${res.status} — bascule sur fallback local`);
    } catch (err) {
      console.warn(`[RefPicker] ${referential}: erreur réseau (${err.message}) — bascule sur fallback local`);
    }
    const local = searchLocal(referential, q, 12);
    setResults(local);
    computeDropPos();
    setOpen(local.length > 0);
    setLoading(false);
  }, [referential]);

  function handleInput(v) {
    setQuery(v);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(v), 200);
  }

  function isSelected(ref_id) {
    return selected.some(s => s.ref_id === ref_id);
  }

  function add(item) {
    if (isSelected(item.ref_id)) return;
    commit([...selected, { ref_id: item.ref_id, name: item.name }]);
    setQuery("");
    setOpen(false);
    inputRef.current?.focus();
  }

  function remove(ref_id) {
    commit(selected.filter(s => s.ref_id !== ref_id));
  }

  function commit(next) {
    setSelected(next);
    onChange(serializeRefValue(next), refToReadable(next));
  }

  const count = selected.length;

  // Dropdown rendu via portal dans <body> — complètement hors de tout
  // contexte de stacking/overflow/backdrop-filter
  const dropdown = open ? createPortal(
    <div
      className="ref-dropdown"
      style={{
        position: "absolute",
        top:   dropPos.top,
        left:  dropPos.left,
        width: dropPos.width,
        zIndex: 9999,
      }}
    >
      <div className="ref-dropdown-head">
        {results.length} résultat{results.length > 1 ? "s" : ""}
      </div>
      {results.map(r => {
        const sel = isSelected(r.ref_id);
        return (
          <div
            key={r.ref_id}
            className={`ref-result-item${sel ? " ref-result-added" : ""}`}
            onMouseDown={e => { e.preventDefault(); if (!sel) add(r); }}
          >
            <span className="ref-result-id" style={{ color: cfg.accentColor }}>
              {r.ref_id}
            </span>
            <span className="ref-result-body">
              <span className="ref-result-name">{r.name}</span>
              {r.description && (
                <span className="ref-result-desc">{r.description}</span>
              )}
            </span>
            {sel && <span className="ref-result-check">✓</span>}
          </div>
        );
      })}
      {results.length === 0 && (
        <div className="ref-no-result">Aucun résultat</div>
      )}
    </div>,
    document.body
  ) : null;

  return (
    <div className="ref-section">
      <div className="ref-section-head">
        <span className={cfg.badgeClass}>{cfg.label}</span>
        <span className="ref-section-count">
          {count === 0 ? "Aucune référence" : `${count} référence${count > 1 ? "s" : ""}`}
        </span>
      </div>

      <div className="ref-chips-area">
        {selected.length === 0 ? (
          <span className="ref-empty-hint">Aucune référence sélectionnée</span>
        ) : (
          selected.map(item => (
            <span key={item.ref_id} className={cfg.chipClass} title={item.name}>
              <span className="ref-chip-id">{item.ref_id}</span>
              <span className="ref-chip-name">{item.name}</span>
              <button
                type="button"
                className="ref-chip-remove"
                onClick={() => remove(item.ref_id)}
                aria-label={`Retirer ${item.ref_id}`}
              >×</button>
            </span>
          ))
        )}
      </div>

      <div className="ref-search-area">
        <div className="ref-search-wrap">
          <span className="ref-search-icon">{loading ? "…" : "⌕"}</span>
          <input
            ref={inputRef}
            type="text"
            className="input ref-input"
            value={query}
            onChange={e => handleInput(e.target.value)}
            onFocus={() => { if (query.trim().length >= 1) { computeDropPos(); setOpen(true); } }}
            placeholder={cfg.placeholder}
            autoComplete="off"
          />
        </div>
      </div>

      {dropdown}
    </div>
  );
}

export function RefGroup({ values, onChange }) {
  function handleChange(ref, raw, readable) {
    const next = { ...values, [ref]: raw };
    const readables = {
      owasp: ref === "owasp" ? readable : refToReadable(parseRefValue(values.owasp)),
      cwe:   ref === "cwe"   ? readable : refToReadable(parseRefValue(values.cwe)),
      capec: ref === "capec" ? readable : refToReadable(parseRefValue(values.capec)),
    };
    onChange(next, readables);
  }

  return (
    <div className="ref-group">
      <RefPicker referential="owasp" valueRaw={values.owasp}
        onChange={(raw, readable) => handleChange("owasp", raw, readable)} />
      <RefPicker referential="cwe"   valueRaw={values.cwe}
        onChange={(raw, readable) => handleChange("cwe", raw, readable)} />
      <RefPicker referential="capec" valueRaw={values.capec}
        onChange={(raw, readable) => handleChange("capec", raw, readable)} />
    </div>
  );
}
