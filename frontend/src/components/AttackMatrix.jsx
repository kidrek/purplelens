import { fmtMin } from "../lib/format";

// Légende des niveaux de capacité
const CAP = {
  full: { label: "Détecté + Réagi", cls: "cap-full" },
  detect: { label: "Détecté seul", cls: "cap-detect" },
  none: { label: "Non détecté", cls: "cap-none" },
};

export function CapabilityLegend() {
  return (
    <div className="cap-legend">
      {Object.entries(CAP).map(([k, v]) => (
        <span key={k} className="cap-legend-item">
          <span className={`cap-swatch ${v.cls}`} />
          {v.label}
        </span>
      ))}
    </div>
  );
}

export function AttackMatrix({ matrix }) {
  if (!matrix || matrix.counts.total === 0) {
    return (
      <div className="card faint" style={{ fontSize: 13 }}>
        Aucune technique testée pour cette application. Lancez un audit et
        renseignez l'exécution ATT&CK.
      </div>
    );
  }

  return (
    <div className="matrix-wrap">
      <div className="matrix-grid">
        {matrix.tactics.map((col) => (
          <div className="matrix-col" key={col.tactic}>
            <div className="matrix-col-head" title={col.tactic}>
              {col.tactic}
            </div>
            <div className="matrix-cells">
              {col.techniques.map((c) => {
                const cap = CAP[c.capability];
                const tip = [
                  `${c.mitre_id} — ${c.name}`,
                  cap.label,
                  c.detection_time_min != null
                    ? `MTTD ${fmtMin(c.detection_time_min)} min`
                    : null,
                  c.response_time_min != null
                    ? `MTTR ${fmtMin(c.response_time_min)} min`
                    : null,
                  `Source : ${c.source_audit_name}`,
                ]
                  .filter(Boolean)
                  .join("\n");
                return (
                  <div className={`matrix-cell ${cap.cls}`} key={c.mitre_id} title={tip}>
                    <span className="matrix-ttp">{c.mitre_id}</span>
                    <span className="matrix-tname">{c.name}</span>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
