/**
 * D3fendAccordion — section contre-mesures D3FEND avec accordéon par technique ATT&CK.
 *
 * Props :
 *   steps  {array}  — étapes du scénario (ordre déjà trié), chaque étape a mitre_id,
 *                     technique_name, order
 *
 * Utilise getD3fendMeasures() depuis d3fendData.js pour récupérer les mesures.
 * Le premier groupe est déplié par défaut, les autres repliés.
 */
import { useState } from "react";
import {
  getD3fendMeasures, D3FEND_CATEGORIES, d3fendUrl,
} from "../lib/d3fendData";

// Ordre canonique des catégories : durcissement → détection → confinement → éradication → leurre → restauration
const CAT_ORDER = ["harden", "detect", "isolate", "evict", "deceive", "restore"];
const catRank = (cat) => {
  const r = CAT_ORDER.indexOf(cat);
  return r === -1 ? CAT_ORDER.length : r;
};

export function D3fendAccordion({ steps }) {
  // Grouper les mesures par étape, triées par ordre canonique de catégorie
  const groups = steps
    .filter(st => st.mitre_id)
    .map((st, idx) => ({
      stepNum:   st.order ?? idx + 1,
      mitre_id:  st.mitre_id,
      techName:  st.technique_name,
      measures:  [...getD3fendMeasures(st.mitre_id)].sort(
        (a, b) => catRank(a.cat) - catRank(b.cat)
      ),
    }))
    .filter(g => g.measures.length > 0);

  // État accordéon : index 0 ouvert par défaut
  const [open, setOpen] = useState(() => new Set([0]));

  const toggle = (i) =>
    setOpen(prev => {
      const next = new Set(prev);
      next.has(i) ? next.delete(i) : next.add(i);
      return next;
    });

  if (groups.length === 0) return null;

  const totalMeasures = groups.reduce((s, g) => s + g.measures.length, 0);

  return (
    <>
      {/* Header séparateur */}
      <div className="d3f-section-head">
        <span className="scen-badge scen-badge-d3f">D3FEND</span>
        <span className="scen-section-title">Contre-mesures défensives</span>
        <span className="scen-section-count">
          {totalMeasures} mesure{totalMeasures > 1 ? "s" : ""} · {groups.length} technique{groups.length > 1 ? "s" : ""}
        </span>
      </div>

      {/* Corps accordéon */}
      <div className="d3f-section-body">
        {groups.map((g, i) => {
          const isOpen = open.has(i);
          const isLast = i === groups.length - 1;
          return (
            <div key={g.mitre_id + i}>
              <div className="d3f-acc-item">
                {/* Connecteur vertical vert (sauf dernier) */}
                {!isLast && <div className="d3f-acc-connector" />}

                {/* Cercle numéro — même style que kill-chain mais vert */}
                <div className="d3f-acc-circle">{g.stepNum}</div>

                {/* Header cliquable */}
                <div
                  className="d3f-acc-header"
                  onClick={() => toggle(i)}
                  role="button"
                  aria-expanded={isOpen}
                >
                  <div className="d3f-acc-header-row">
                    <span className="ttp" style={{ fontSize: 11 }}>{g.mitre_id}</span>
                    <span className="d3f-acc-name">{g.techName}</span>
                    <span className="d3f-acc-pill">{g.measures.length} mesure{g.measures.length > 1 ? "s" : ""}</span>
                    <button
                      className="d3f-acc-toggle"
                      tabIndex={-1}
                      onClick={e => { e.stopPropagation(); toggle(i); }}
                    >
                      <span
                        className={`d3f-acc-chevron${isOpen ? "" : " closed"}`}
                      >▾</span>
                      {isOpen ? "Replier" : "Déplier"}
                    </button>
                  </div>

                  {/* Mesures */}
                  {isOpen && (
                    <div className="d3f-acc-measures">
                      {g.measures.map((m, mi) => {
                        const cat = D3FEND_CATEGORIES[m.cat] || { label: m.cat, css: "" };
                        return (
                          <div className="d3f-measure-card" key={mi}>
                            <span className={`d3cat ${cat.css}`}>{cat.label}</span>
                            <span className="d3f-measure-name">{m.name}</span>
                            <a
                              className="d3f-measure-link"
                              href={d3fendUrl(m.d3f_id)}
                              target="_blank"
                              rel="noopener noreferrer"
                              title={`Voir ${m.name} sur d3fend.mitre.org`}
                              onClick={e => e.stopPropagation()}
                            >
                              ⓘ {m.d3f_id.replace(/([A-Z])/g, c => c).slice(0, 12)}
                            </a>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>

              {/* Séparateur entre groupes */}
              {!isLast && <div className="d3f-sep" />}
            </div>
          );
        })}
      </div>
    </>
  );
}
