/**
 * MitreMatrix — vue synthétique des techniques ATT&CK utilisées dans un scénario.
 *
 * Props :
 *   steps  {array}  — étapes du scénario (ordre trié), chaque étape a :
 *                     { tactic, mitre_id, technique_name, order }
 *
 * Comportement :
 *   - Regroupe les étapes par tactique, dans l'ordre canonique ATT&CK.
 *   - N'affiche que les tactiques présentes dans le scénario.
 *   - Si le nombre max de techniques dans une colonne > COLLAPSE_THRESHOLD,
 *     la matrice démarre repliée (fondu + bouton Déplier).
 *   - Scroll horizontal natif pour les scénarios larges.
 */
import { useState } from "react";
import { ENUMS } from "../api/client";
import { attackUrl } from "../lib/d3fendData";

const COLLAPSE_THRESHOLD = 2; // nb max de techniques/colonne avant repli auto

export function MitreMatrix({ steps }) {
  const validSteps = steps.filter(st => st.mitre_id && st.tactic);
  if (validSteps.length === 0) return null;

  // Ordre canonique des tactiques ATT&CK (depuis ENUMS)
  const tacticOrder = ENUMS.tactics.map(t => t[0]);
  const tacticLabel = (val) => (ENUMS.tactics.find(t => t[0] === val) || [val, val])[1];

  // Grouper par tactique en préservant l'ordre des étapes
  const grouped = {};
  validSteps.forEach(st => {
    if (!grouped[st.tactic]) grouped[st.tactic] = [];
    grouped[st.tactic].push(st);
  });

  // Colonnes triées selon l'ordre canonique
  const columns = tacticOrder
    .filter(t => grouped[t])
    .map(t => ({ tactic: t, label: tacticLabel(t), steps: grouped[t] }));

  // Calcul du seuil de repli
  const maxRows = Math.max(...columns.map(c => c.steps.length));
  const [collapsed, setCollapsed] = useState(maxRows > COLLAPSE_THRESHOLD);

  const totalTech  = validSteps.length;
  const totalTactics = columns.length;

  return (
    <div className="matrix-card">
      {/* Header */}
      <div className="matrix-head">
        <span className="matrix-badge">ATT&amp;CK</span>
        <span className="matrix-title">Matrice MITRE</span>
        <span className="matrix-meta">
          {totalTech} technique{totalTech > 1 ? "s" : ""} · {totalTactics} tactique{totalTactics > 1 ? "s" : ""}
        </span>
        <button
          className="matrix-collapse-btn"
          onClick={() => setCollapsed(c => !c)}
        >
          <span className={`matrix-chv${collapsed ? "" : " up"}`}>▾</span>
          {collapsed ? "Déplier" : "Replier"}
        </button>
      </div>

      {/* Corps */}
      <div className={`matrix-body${collapsed ? " collapsed" : ""}`}>
        <div className="matrix-grid">
          {columns.map(col => (
            <div className="matrix-col" key={col.tactic}>
              <div className="matrix-tactic-header">{col.label}</div>
              {col.steps.map((st, i) => (
                <a
                  key={st.mitre_id + i}
                  className="matrix-tech-cell"
                  href={attackUrl(st.mitre_id)}
                  target="_blank"
                  rel="noopener noreferrer"
                  title={`${st.mitre_id} — ${st.technique_name}\nVoir sur attack.mitre.org`}
                  onClick={e => e.stopPropagation()}
                >
                  <div className="matrix-step-num">{st.order}</div>
                  <div className="matrix-tech-id">{st.mitre_id}</div>
                  <div className="matrix-tech-name">{st.technique_name}</div>
                </a>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
