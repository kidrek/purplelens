import { scoreColor, scoreBg } from "../lib/format";

export function KpiTile({ name, value, unit, pct, hint }) {
  const showBar = pct != null;
  const color = showBar ? scoreColor(pct) : "var(--violet-bright)";
  return (
    <div className="kpi" title={hint || ""}>
      <div className="kpi-name">{name}</div>
      <div className="kpi-value" style={{ color }}>
        {value}
        {unit && <span className="kpi-unit"> {unit}</span>}
      </div>
      {showBar && (
        <div className="kpi-bar">
          <span style={{ width: `${Math.min(pct, 100)}%`, background: color }} />
        </div>
      )}
      {hint && <div className="kpi-hint">{hint}</div>}
    </div>
  );
}

export function ScorePill({ pct }) {
  if (pct == null) return <span className="faint mono">—</span>;
  return (
    <span
      className="score-pill"
      style={{ color: scoreColor(pct), background: scoreBg(pct) }}
    >
      {pct}%
    </span>
  );
}

export function DIC({ dic }) {
  return (
    <span className="dic">
      D<b>{dic.availability}</b> I<b>{dic.integrity}</b> C<b>{dic.confidentiality}</b>
    </span>
  );
}

export function YesNo({ value }) {
  return (
    <span className={`yn ${value ? "y" : "n"}`}>{value ? "OUI" : "NON"}</span>
  );
}
