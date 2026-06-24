export function scoreColor(pct) {
  if (pct >= 80) return "var(--mint)";
  if (pct >= 50) return "var(--amber)";
  return "var(--coral)";
}

export function scoreBg(pct) {
  if (pct >= 80) return "rgba(52,216,164,.16)";
  if (pct >= 50) return "rgba(245,166,35,.16)";
  return "rgba(255,93,115,.16)";
}

export function severityClass(sev) {
  return (
    { Critical: "crit", High: "high", Medium: "med", Low: "med", Info: "med" }[sev] ||
    "med"
  );
}

export function fmtMin(v) {
  if (v == null) return "—";
  return `${v}`;
}

// jj/mm/aa
export function fmtDate(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  if (isNaN(d)) return null;
  const p = (n) => String(n).padStart(2, "0");
  return `${p(d.getDate())}/${p(d.getMonth() + 1)}/${String(d.getFullYear()).slice(2)}`;
}

// "01/06/26 → 10/06/26" ou "13/06/26 → Continu" ou "— → —"
export function fmtMilestones(start, end) {
  const s = fmtDate(start) || "—";
  const e = fmtDate(end) || "Continu";
  return `${s} → ${e}`;
}

// classe de badge selon le statut d'audit
export function auditStatusClass(status) {
  return (
    {
      "In Progress": "ok",
      Completed: "med",
      Closed: "med",
      Draft: "med",
      Scoping: "high",
      Review: "high",
    }[status] || "med"
  );
}
