import { useState, useEffect, useRef } from "react";
import { searchCPE, parseTechnologiesCpe, serializeTechnologiesCpe, cpeToReadable } from "../lib/cpeData";

/**
 * CpePicker — champ de sélection de technologies via le référentiel CPE local.
 *
 * Props :
 *   valueRaw   {string}  — valeur JSON stockée en base (technologies_cpe)
 *   onChange   {fn}      — callback(rawJson, readableString)
 *
 * Le composant gère en interne un tableau d'objets { cpe, vendor, product }.
 * À chaque modification il appelle onChange avec :
 *   - le JSON sérialisé pour technologies_cpe (stockage backend)
 *   - la chaîne lisible pour technologies (affichage)
 */
export function CpePicker({ valueRaw, onChange }) {
  const [selected, setSelected] = useState([]);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const inputRef = useRef(null);
  const dropdownRef = useRef(null);

  // Initialise depuis la valeur JSON stockée
  useEffect(() => {
    setSelected(parseTechnologiesCpe(valueRaw));
  }, [valueRaw]);

  // Recherche CPE dès 2 caractères
  useEffect(() => {
    if (query.trim().length >= 2) {
      setResults(searchCPE(query, 10));
      setOpen(true);
    } else {
      setResults([]);
      setOpen(false);
    }
  }, [query]);

  // Ferme le dropdown au clic extérieur
  useEffect(() => {
    function handleClick(e) {
      if (
        dropdownRef.current && !dropdownRef.current.contains(e.target) &&
        inputRef.current && !inputRef.current.contains(e.target)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  function isSelected(cpe) {
    return selected.some((s) => s.cpe === cpe);
  }

  function add(item) {
    if (isSelected(item.cpe)) return;
    const next = [...selected, { cpe: item.cpe, vendor: item.vendor, product: item.product }];
    commit(next);
    setQuery("");
    setOpen(false);
    inputRef.current?.focus();
  }

  function remove(cpe) {
    const next = selected.filter((s) => s.cpe !== cpe);
    commit(next);
  }

  function commit(next) {
    setSelected(next);
    onChange(serializeTechnologiesCpe(next), cpeToReadable(next));
  }

  return (
    <div className="cpe-picker">
      {/* Chips des technologies sélectionnées */}
      {selected.length > 0 && (
        <div className="cpe-chips">
          {selected.map((t) => (
            <span key={t.cpe} className="cpe-chip" title={t.cpe}>
              {t.vendor} {t.product}
              <button
                type="button"
                className="cpe-chip-remove"
                onClick={() => remove(t.cpe)}
                aria-label={`Retirer ${t.vendor} ${t.product}`}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Input de recherche */}
      <div className="cpe-search-wrap">
        <span className="cpe-search-icon">⌕</span>
        <input
          ref={inputRef}
          type="text"
          className="input cpe-input"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => query.trim().length >= 2 && setOpen(true)}
          placeholder={selected.length === 0 ? "Rechercher un produit CPE… ex: nginx, postgres, tomcat" : "Ajouter une technologie…"}
          autoComplete="off"
        />
      </div>

      {/* Dropdown de résultats */}
      {open && results.length > 0 && (
        <div className="cpe-dropdown" ref={dropdownRef}>
          <div className="cpe-dropdown-header">Référentiel CPE — {results.length} résultat{results.length > 1 ? "s" : ""}</div>
          {results.map((r) => {
            const sel = isSelected(r.cpe);
            return (
              <div
                key={r.cpe}
                className={`cpe-result-item${sel ? " cpe-result-added" : ""}`}
                onClick={() => !sel && add(r)}
              >
                <span className="cpe-result-icon">⬡</span>
                <span className="cpe-result-label">
                  <span className="cpe-result-vendor">{r.vendor}</span>
                  {" "}{r.product}
                </span>
                <span className="cpe-result-id">{r.cpe.replace("cpe:2.3:", "")}</span>
                {sel && <span className="cpe-result-check">✓</span>}
              </div>
            );
          })}
        </div>
      )}

      {open && query.trim().length >= 2 && results.length === 0 && (
        <div className="cpe-dropdown" ref={dropdownRef}>
          <div className="cpe-no-result">Aucun résultat dans le référentiel CPE local</div>
        </div>
      )}

      <div className="hint">
        Référentiel CPE local · {" "}
        <span style={{ opacity: 0.7 }}>
          La liste peut être mise à jour depuis les Paramètres
        </span>
      </div>
    </div>
  );
}
