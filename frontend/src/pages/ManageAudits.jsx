import { useState, useEffect, useRef, useCallback } from "react";

const API = "/api";

// ── Constantes ──────────────────────────────────────────────────────────────
const MONTH_NAMES = ["Jan","Fév","Mar","Avr","Mai","Jun","Jul","Aoû","Sep","Oct","Nov","Déc"];
const DAY_LABELS  = ["Lun","","Mer","","Ven","",""];
const PERIODS     = [
  { key: "1m",  label: "1 mois"  },
  { key: "6m",  label: "6 mois"  },
  { key: "1a",  label: "1 an"    },
  { key: "all", label: "Toute la période" },
];
const TYPES   = ["Red Team", "Purple Team", "Pentest", "BAS"];
const STATUTS = ["In Progress", "Completed", "Closed", "Draft", "Scoping", "Review"];

const TYPE_COLORS = {
  "Red Team":    { bg: "rgba(224,60,82,.18)",   color: "#e03c52" },
  "Purple Team": { bg: "rgba(139,92,246,.16)",  color: "#a78bfa" },
  "Pentest":     { bg: "rgba(74,222,128,.12)",  color: "#4ade80" },
  "BAS":         { bg: "rgba(251,191,36,.12)",  color: "#fbbf24" },
};

const SEVERITY_COLORS = {
  Critical: { bg: "rgba(224,60,82,.18)",  color: "#e03c52" },
  High:     { bg: "rgba(251,146,60,.14)", color: "#fb923c" },
  Medium:   { bg: "rgba(155,151,184,.14)",color: "#9b97b8" },
  Low:      { bg: "rgba(107,103,136,.14)",color: "#6b6788" },
  Info:     { bg: "rgba(107,103,136,.14)",color: "#6b6788" },
};

// ── Styles inline ────────────────────────────────────────────────────────────
const S = {
  page: { padding: "32px 0 64px" },
  eyebrow: { fontSize: 12, color: "#7c70d8", fontWeight: 500, letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 6 },
  title: { fontSize: 28, fontWeight: 500, color: "#fff", marginBottom: 6 },
  sub: { fontSize: 14, color: "#6b6788", marginBottom: 28, maxWidth: 520, lineHeight: 1.5 },

  kpiGrid: { display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 12 },
  kpiCard: { background: "#12111f", border: "0.5px solid #2a2840", borderRadius: 10, padding: "16px 18px" },
  kpiLabel: { fontSize: 11, color: "#6b6788", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 10 },
  kpiValue: (color) => ({ fontSize: 32, fontWeight: 500, lineHeight: 1, marginBottom: 6, color }),
  kpiDelta: { fontSize: 12, color: "#6b6788", marginBottom: 12 },
  kpiBarWrap: { height: 2, background: "#1e1d30", borderRadius: 2, overflow: "hidden" },
  kpiBar: (color, pct) => ({ height: "100%", borderRadius: 2, width: `${pct}%`, background: color, boxShadow: `0 0 8px ${color}cc`, transition: "width .4s ease" }),

  repCard: { background: "#12111f", border: "0.5px solid #2a2840", borderRadius: 10, padding: "16px 18px", marginBottom: 28 },
  repGrid: { display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 },
  repRow: { display: "flex", alignItems: "center", gap: 7 },
  repLabel: { fontSize: 11, color: "#6b6788", width: 84, flexShrink: 0 },
  repTrack: { flex: 1, height: 4, background: "#1e1d30", borderRadius: 2, overflow: "hidden" },
  repFill: (pct) => ({ height: "100%", borderRadius: 2, background: "#a78bfa", boxShadow: "0 0 6px #a78bfaaa", width: `${pct}%`, transition: "width .4s ease" }),
  repCount: { fontSize: 11, color: "#a78bfa", fontWeight: 600, minWidth: 14, textAlign: "right" },

  sectionHeader: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 },
  sectionTitle: { fontSize: 14, fontWeight: 500, color: "#aaa" },
  newBtn: { background: "#7c70d8", border: "none", borderRadius: 8, color: "#fff", padding: "6px 14px", fontSize: 13, fontWeight: 500, cursor: "pointer" },

  filtersRow: { display: "flex", alignItems: "center", gap: 8, marginBottom: 10, flexWrap: "wrap" },
  filterLabel: { fontSize: 11, color: "#6b6788" },
  chip: (active) => ({
    display: "inline-flex", alignItems: "center", padding: "4px 12px",
    borderRadius: 7, fontSize: 12, fontWeight: 500, cursor: "pointer",
    border: active ? "1px solid #7c70d8" : "1px solid #2a2840",
    background: active ? "#1e1a40" : "#12111f",
    color: active ? "#a89fff" : "#6b6788",
    userSelect: "none", transition: "all .15s",
  }),
  chipBlue: (active) => ({
    display: "inline-flex", alignItems: "center", padding: "4px 12px",
    borderRadius: 7, fontSize: 12, fontWeight: 500, cursor: "pointer",
    border: active ? "1px solid #3b82f6" : "1px solid #2a2840",
    background: active ? "#0d1e30" : "#12111f",
    color: active ? "#60a5fa" : "#6b6788",
    userSelect: "none",
  }),

  heatmapCard: { background: "#12111f", border: "0.5px solid #2a2840", borderRadius: 10, padding: "14px 16px", marginBottom: 12 },
  heatmapHeader: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 },
  heatmapTitle: { fontSize: 11, color: "#6b6788", textTransform: "uppercase", letterSpacing: "0.07em", display: "flex", alignItems: "center", gap: 6 },
  heatmapRight: { display: "flex", alignItems: "center", gap: 16 },
  heatmapMeta: { fontSize: 11, color: "#6b6788" },
  legend: { display: "flex", alignItems: "center", gap: 5, fontSize: 10, color: "#6b6788" },
  legendSwatch: (cls) => ({ width: 10, height: 10, borderRadius: 2, ...cls }),

  tableWrap: { background: "#12111f", border: "0.5px solid #2a2840", borderRadius: 12, overflow: "hidden" },
  th: { padding: "10px 14px", textAlign: "left", fontSize: 10, color: "#6b6788", fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.08em", whiteSpace: "nowrap" },
  td: { padding: "12px 14px", verticalAlign: "middle", color: "#6b6788", fontSize: 13, borderBottom: "0.5px solid #1a192c" },
  auditName: { fontWeight: 500, color: "#e0dff8", fontSize: 13 },
  auditApp: { fontSize: 11, color: "#6b6788", marginTop: 2 },

  scoreWrap: { display: "flex", flexDirection: "column", gap: 5, minWidth: 90 },
  scoreNum: (color) => ({ fontSize: 14, fontWeight: 500, color }),
  scoreTrack: { height: 3, background: "#1e1d30", borderRadius: 2, overflow: "hidden" },
  scoreFill: (color, pct) => ({ height: "100%", borderRadius: 2, background: color, boxShadow: `0 0 6px ${color}cc`, width: `${pct}%` }),

  pill: (sev) => ({
    display: "inline-block", padding: "2px 7px", borderRadius: 5,
    fontSize: 11, fontWeight: 600, marginRight: 3,
    background: SEVERITY_COLORS[sev]?.bg || "rgba(107,103,136,.14)",
    color: SEVERITY_COLORS[sev]?.color || "#6b6788",
  }),
  actionBtn: { width: 28, height: 28, borderRadius: 6, background: "#1a192c", border: "0.5px solid #2a2840", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", color: "#6b6788", fontSize: 13 },
};

// ── Heatmap calendrier ───────────────────────────────────────────────────────
const AUDIT_LEVELS = [
  { min: 0, max: 0, bg: "#1a192c", shadow: null },
  { min: 1, max: 1, bg: "#2e2660", shadow: null },
  { min: 2, max: 2, bg: "#4b3d9e", shadow: null },
  { min: 3, max: 3, bg: "#7c70d8", shadow: null },
  { min: 4, max: Infinity, bg: "#a78bfa", shadow: "0 0 5px #a78bfa88" },
];

function getCellStyle(value, levels, size, dimmed) {
  const lvl = levels.find(l => value >= l.min && value <= l.max) || levels[0];
  return {
    width: size, height: size,
    borderRadius: Math.max(1, Math.round(size * 0.2)),
    flexShrink: 0,
    background: lvl.bg,
    boxShadow: lvl.shadow || undefined,
    opacity: dimmed ? 0.12 : 1,
    cursor: "default",
    transition: "opacity .25s",
    flexShrink: 0,
  };
}

function CalendarHeatmap({ dayData, levels, legendSwatches, activeRange, title, icon, total }) {
  const wrapRef = useRef(null);
  const [cellSize, setCellSize] = useState(11);
  const [weeks, setWeeks] = useState([]);

  const year = new Date().getFullYear();
  const today = new Date(); today.setHours(0, 0, 0, 0);

  useEffect(() => {
    // Construire les semaines de l'année
    const firstDay = new Date(year, 0, 1);
    const startMonday = new Date(firstDay);
    startMonday.setDate(firstDay.getDate() - ((firstDay.getDay() + 6) % 7));
    const lastDay = new Date(year, 11, 31);
    const ws = [];
    for (let cur = new Date(startMonday); cur <= lastDay; cur.setDate(cur.getDate() + 7)) {
      const week = [];
      for (let d = 0; d < 7; d++) {
        const day = new Date(cur); day.setDate(day.getDate() + d);
        week.push({
          date: new Date(day),
          key: day.toISOString().slice(0, 10),
          inYear: day.getFullYear() === year,
          isFuture: day > today,
        });
      }
      ws.push(week);
    }
    setWeeks(ws);
  }, [year]);

  useEffect(() => {
    if (!wrapRef.current || weeks.length === 0) return;
    const DAY_LABEL_W = 28, GAP = 2;
    const available = wrapRef.current.offsetWidth - DAY_LABEL_W;
    const size = Math.max(8, Math.floor((available - (weeks.length - 1) * GAP) / weeks.length));
    setCellSize(size);
  }, [weeks, wrapRef.current?.offsetWidth]);

  const GAP = 2;
  const DAY_LABEL_W = 28;
  const step = cellSize + GAP;

  // Labels de mois
  const monthPositions = {};
  weeks.forEach((week, wi) => {
    week.forEach(({ date, inYear }) => {
      if (!inYear) return;
      const m = date.getMonth();
      if (!(m in monthPositions)) monthPositions[m] = wi;
    });
  });

  function isInRange(key) {
    if (!activeRange) return true;
    const d = new Date(key);
    return d >= activeRange.from && d <= activeRange.to;
  }

  return (
    <div style={S.heatmapCard}>
      <div style={S.heatmapHeader}>
        <div style={S.heatmapTitle}>
          <i className={`ti ${icon}`} aria-hidden="true" />
          {title}
        </div>
        <div style={S.heatmapRight}>
          <div style={S.heatmapMeta}>
            Total : <span style={{ color: "#a78bfa", fontWeight: 600 }}>{total}</span>
          </div>
          <div style={S.legend}>
            <span>Moins</span>
            {legendSwatches.map((bg, i) => (
              <div key={i} style={{ width: 10, height: 10, borderRadius: 2, background: bg }} />
            ))}
            <span>Plus</span>
          </div>
        </div>
      </div>
      <div ref={wrapRef}>
        {/* Labels mois */}
        <div style={{ position: "relative", height: 14, marginLeft: DAY_LABEL_W, marginBottom: 4 }}>
          {Object.entries(monthPositions).map(([m, wi]) => (
            <span key={m} style={{ position: "absolute", left: wi * step, fontSize: 10, color: "#6b6788", whiteSpace: "nowrap" }}>
              {MONTH_NAMES[m]}
            </span>
          ))}
        </div>
        {/* Grille */}
        <div style={{ display: "flex", flexDirection: "column", gap: GAP }}>
          {DAY_LABELS.map((dayLabel, d) => (
            <div key={d} style={{ display: "flex", alignItems: "center", gap: GAP }}>
              <span style={{ fontSize: 10, color: "#6b6788", width: DAY_LABEL_W, flexShrink: 0, textAlign: "right", paddingRight: 6 }}>
                {dayLabel}
              </span>
              {weeks.map((week, wi) => {
                const { date, key, inYear, isFuture } = week[d];
                const value = (inYear && !isFuture) ? (dayData[key] || 0) : 0;
                const dimmed = inYear && !isFuture && !isInRange(key);
                const title = value > 0
                  ? `${value} — ${date.getDate()} ${MONTH_NAMES[date.getMonth()]}`
                  : `${date.getDate()} ${MONTH_NAMES[date.getMonth()]}`;
                return (
                  <div
                    key={wi}
                    style={getCellStyle(value, levels, cellSize, dimmed)}
                    title={title}
                  />
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Score bar ────────────────────────────────────────────────────────────────
function ScoreBar({ value, color }) {
  if (value == null) return <span style={{ color: "#6b6788" }}>N/A</span>;
  return (
    <div style={S.scoreWrap}>
      <div style={S.scoreNum(color)}>{value}%</div>
      <div style={S.scoreTrack}>
        <div style={S.scoreFill(color, value)} />
      </div>
    </div>
  );
}

// ── Composant principal ──────────────────────────────────────────────────────
export default function ManageAudits({ onSelectApp, onOpenAudit }) {
  const [audits, setAudits]       = useState([]);
  const [kpis, setKpis]           = useState(null);
  const [period, setPeriod]       = useState("1a");
  const [typeFilter, setTypeFilter] = useState(null);   // null = tous
  const [statusFilter, setStatusFilter] = useState(null);
  const [loading, setLoading]     = useState(true);

  // ── Fetch données ──────────────────────────────────────────────────────
  const fetchAll = useCallback(async (p) => {
    setLoading(true);
    try {
      const [auditRes, kpiRes] = await Promise.all([
        fetch(`${API}/audits`),
        fetch(`${API}/audits/kpis?period=${p}`),
      ]);
      const [auditData, kpiData] = await Promise.all([auditRes.json(), kpiRes.json()]);
      setAudits(auditData);
      setKpis(kpiData);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(period); }, [period]);

  // ── Suppression ────────────────────────────────────────────────────────
  async function deleteAudit(id) {
    if (!confirm("Supprimer cet audit ?")) return;
    await fetch(`${API}/audits/${id}`, { method: "DELETE" });
    fetchAll(period);
  }

  // ── Filtrage de la table ───────────────────────────────────────────────
  const filteredAudits = audits.filter(a => {
    if (typeFilter && a.audit_type !== typeFilter) return false;
    if (statusFilter && a.status !== statusFilter) return false;
    return true;
  });

  // ── Fenêtre active pour heatmap ────────────────────────────────────────
  function getActiveRange(p) {
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const from = new Date(today);
    const year = today.getFullYear();
    if      (p === "1m")  from.setMonth(from.getMonth() - 1);
    else if (p === "6m")  from.setMonth(from.getMonth() - 6);
    else                  from.setTime(new Date(year, 0, 1).getTime());
    return { from, to: today };
  }
  const activeRange = getActiveRange(period);

  // ── KPI helpers ────────────────────────────────────────────────────────
  const kpiDetectPct  = kpis ? kpis.detection_rate : 0;
  const kpiAuditsPct  = kpis && kpis.total_audits > 0 ? Math.round(kpis.total_audits / (kpis.total_audits * 2) * 100) : 50;
  const kpiAppsPct    = kpis ? Math.round(kpis.audited_apps / (kpis.total_apps || 1) * 100) : 0;
  const kpiVulnsPct   = kpis ? Math.min(100, Math.round(kpis.open_vulns / 30 * 100)) : 0;

  const repTotal = kpis ? Object.values(kpis.repartition).reduce((s, v) => s + v, 0) || 1 : 1;

  // ── Calcul findings par audit ──────────────────────────────────────────
  function findingsForAudit(audit) {
    // Les findings sont attachés à l'audit via audit.findings (relation chargée côté API)
    // On regroupe par sévérité
    const groups = {};
    (audit.findings || []).forEach(f => {
      groups[f.severity] = (groups[f.severity] || 0) + 1;
    });
    return groups;
  }

  function scoreColor(pct) {
    if (pct === null || pct === undefined) return "#6b6788";
    if (pct >= 70) return "#4ade80";
    if (pct >= 40) return "#fbbf24";
    return "#e03c52";
  }

  function mttdColor(min) {
    if (!min) return "#6b6788";
    if (min <= 30) return "#4ade80";
    if (min <= 60) return "#fbbf24";
    return "#e03c52";
  }

  // ── Calcul taux détection / réaction par audit (depuis assessments) ────
  function auditScores(audit) {
    const assessments = audit.assessments || [];
    if (!assessments.length) return { detect: null, react: null, mttd: null };
    const detected   = assessments.filter(a => a.detected).length;
    const responded  = assessments.filter(a => a.responded).length;
    const times      = assessments.filter(a => a.detected && a.detection_time_min).map(a => a.detection_time_min);
    return {
      detect: Math.round(detected / assessments.length * 100),
      react:  Math.round(responded / assessments.length * 100),
      mttd:   times.length ? Math.round(times.reduce((s, v) => s + v, 0) / times.length) : null,
    };
  }

  function progressPct(audit) {
    const assessments = audit.assessments || [];
    if (!assessments.length) return 0;
    const filled = assessments.filter(a => a.detected || a.responded || a.notes).length;
    return Math.round(filled / assessments.length * 100);
  }

  // ── Render ─────────────────────────────────────────────────────────────
  return (
    <div style={S.page}>
      {/* En-tête */}
      <div className="page-eyebrow">Module 3</div>
      <div style={S.title}>Gestion des audits</div>
      <div style={S.sub}>
        Suivi opérationnel et stratégique des audits. KPI calculés en temps réel à partir des évaluations ATT&amp;CK, findings et détections.
      </div>

      {/* KPI row 1 */}
      <div style={S.kpiGrid}>
        <div style={S.kpiCard}>
          <div style={S.kpiLabel}>Audits réalisés</div>
          <div style={S.kpiValue("#a78bfa")}>{kpis?.total_audits ?? "—"}</div>
          <div style={S.kpiDelta}>{period === "1m" ? "ce mois" : period === "6m" ? "sur 6 mois" : period === "1a" ? "cette année" : "depuis le début"}</div>
          <div style={S.kpiBarWrap}><div style={S.kpiBar("#a78bfa", kpiAuditsPct)} /></div>
        </div>
        <div style={S.kpiCard}>
          <div style={S.kpiLabel}>Applications auditées</div>
          <div style={S.kpiValue("#a78bfa")}>
            {kpis?.audited_apps ?? "—"}
            <span style={{ fontSize: 15, fontWeight: 400, opacity: 0.5 }}> / {kpis?.total_apps ?? "—"}</span>
          </div>
          <div style={S.kpiDelta}>{period === "1a" ? "cette année" : "sur la période"}</div>
          <div style={S.kpiBarWrap}><div style={S.kpiBar("#a78bfa", kpiAppsPct)} /></div>
        </div>
        <div style={S.kpiCard}>
          <div style={S.kpiLabel}>Taux détection moy.</div>
          <div style={S.kpiValue("#4ade80")}>
            {kpis?.detection_rate ?? "—"}
            <span style={{ fontSize: 15, fontWeight: 400, opacity: 0.5 }}> %</span>
          </div>
          <div style={S.kpiDelta}>{period === "1a" ? "cette année" : "sur la période"}</div>
          <div style={S.kpiBarWrap}><div style={S.kpiBar("#4ade80", kpiDetectPct)} /></div>
        </div>
        <div style={S.kpiCard}>
          <div style={S.kpiLabel}>Vulnérabilités ouvertes</div>
          <div style={S.kpiValue("#e03c52")}>{kpis?.open_vulns ?? "—"}</div>
          <div style={S.kpiDelta}>{period === "1a" ? "cette année" : "sur la période"}</div>
          <div style={S.kpiBarWrap}><div style={S.kpiBar("#e03c52", kpiVulnsPct)} /></div>
        </div>
      </div>

      {/* KPI répartition */}
      <div style={S.repCard}>
        <div style={{ ...S.kpiLabel, marginBottom: 12 }}>Répartition par type</div>
        <div style={S.repGrid}>
          {["Purple Team", "Red Team", "Pentest", "BAS"].map(type => {
            const count = kpis?.repartition?.[type] || 0;
            const pct = Math.round(count / repTotal * 100);
            return (
              <div key={type} style={S.repRow}>
                <span style={S.repLabel}>{type}</span>
                <div style={S.repTrack}><div style={S.repFill(pct)} /></div>
                <span style={S.repCount}>{count}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* En-tête section */}
      <div style={S.sectionHeader}>
        <div style={S.sectionTitle}>Liste des audits</div>
        <button style={S.newBtn} onClick={() => alert("Ouvrir le drawer de création d'audit")}>
          + Nouvel audit
        </button>
      </div>

      {/* Filtres type */}
      <div style={S.filtersRow}>
        <span style={S.filterLabel}>Type :</span>
        <span style={S.chip(!typeFilter)} onClick={() => setTypeFilter(null)}>Tous</span>
        {TYPES.map(t => (
          <span key={t} style={S.chip(typeFilter === t)} onClick={() => setTypeFilter(typeFilter === t ? null : t)}>{t}</span>
        ))}
        <div style={{ flex: 1 }} />
        {["In Progress", "Completed"].map(st => (
          <span key={st} style={S.chipBlue(statusFilter === st)} onClick={() => setStatusFilter(statusFilter === st ? null : st)}>{st}</span>
        ))}
      </div>

      {/* Filtres période */}
      <div style={{ ...S.filtersRow, marginBottom: 16 }}>
        <span style={S.filterLabel}>Période :</span>
        {PERIODS.map(p => (
          <span key={p.key} style={S.chip(period === p.key)} onClick={() => setPeriod(p.key)}>{p.label}</span>
        ))}
      </div>

      {/* Heatmaps */}
      {kpis && (
        <>
          <CalendarHeatmap
            dayData={kpis.audit_heatmap}
            levels={AUDIT_LEVELS}
            legendSwatches={["#2e2660", "#4b3d9e", "#7c70d8", "#a78bfa"]}
            activeRange={activeRange}
            title="Audits réalisés sur la période"
            icon="ti-clipboard-check"
            total={Object.entries(kpis.audit_heatmap)
              .filter(([k]) => {
                const d = new Date(k);
                return d >= activeRange.from && d <= activeRange.to;
              })
              .reduce((s, [, v]) => s + v, 0)}
          />

        </>
      )}

      {/* Table */}
      <div style={S.tableWrap}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "0.5px solid #2a2840" }}>
              {["Audit / Application", "Type", "Statut", "Techniques", "Détection", "Réaction", "MTTD", "Vulnérabilités", "Progression", "Actions"].map((h, i) => (
                <th key={i} style={{ ...S.th, textAlign: i === 3 ? "center" : "left" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={10} style={{ ...S.td, textAlign: "center", color: "#6b6788" }}>Chargement…</td></tr>
            )}
            {!loading && filteredAudits.length === 0 && (
              <tr><td colSpan={10} style={{ ...S.td, textAlign: "center", color: "#6b6788" }}>Aucun audit</td></tr>
            )}
            {!loading && filteredAudits.map(audit => {
              const { detect, react, mttd } = auditScores(audit);
              const prog = progressPct(audit);
              const findings = findingsForAudit(audit);
              const scenarioName = audit.scenarios?.[0]?.threat_actor || audit.scenarios?.[0]?.name || "—";
              const techCount = audit.assessments?.length || 0;
              const typeStyle = TYPE_COLORS[audit.audit_type] || {};

              return (
                <tr
                  key={audit.id}
                  style={{ borderBottom: "0.5px solid #1a192c", cursor: "pointer" }}
                  onMouseEnter={e => e.currentTarget.style.background = "#17162a"}
                  onMouseLeave={e => e.currentTarget.style.background = "transparent"}
                >
                  {/* Nom */}
                  <td style={S.td} onClick={() => onOpenAudit(audit.id)}>
                    <div style={S.auditName}>{audit.name}</div>
                    <div style={S.auditApp}>{audit.application?.name || "—"} · {scenarioName}</div>
                  </td>

                  {/* Type */}
                  <td style={S.td}>
                    <span style={{ fontSize: 12, fontWeight: 600, color: typeStyle.color || "#a78bfa" }}>
                      {audit.audit_type}
                    </span>
                  </td>

                  {/* Statut */}
                  <td style={S.td}>
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12, color: "#6b6788" }}>
                      <span style={{
                        width: 6, height: 6, borderRadius: "50%", flexShrink: 0,
                        background: audit.status === "In Progress" ? "#60a5fa" : "#6b6788",
                        boxShadow: audit.status === "In Progress" ? "0 0 6px #60a5facc" : undefined,
                      }} />
                      {audit.status}
                    </span>
                  </td>

                  {/* Techniques */}
                  <td style={{ ...S.td, textAlign: "center" }}>
                    <span style={{ color: "#a78bfa", fontSize: 13 }}>{techCount || "—"}</span>
                  </td>

                  {/* Détection */}
                  <td style={S.td}>
                    {detect != null
                      ? <ScoreBar value={detect} color={scoreColor(detect)} />
                      : <span style={{ color: "#6b6788" }}>N/A</span>
                    }
                  </td>

                  {/* Réaction */}
                  <td style={S.td}>
                    {react != null
                      ? <ScoreBar value={react} color={scoreColor(react)} />
                      : <span style={{ color: "#6b6788" }}>N/A</span>
                    }
                  </td>

                  {/* MTTD */}
                  <td style={S.td}>
                    {mttd != null
                      ? <span style={{ color: mttdColor(mttd) }}>{mttd} min</span>
                      : <span style={{ color: "#6b6788" }}>—</span>
                    }
                  </td>

                  {/* Vulnérabilités */}
                  <td style={S.td}>
                    {Object.entries(findings).map(([sev, count]) => (
                      <span key={sev} style={S.pill(sev)}>{count} {sev.slice(0, 4).toLowerCase()}</span>
                    ))}
                    {Object.keys(findings).length === 0 && <span style={{ color: "#6b6788" }}>—</span>}
                  </td>

                  {/* Progression */}
                  <td style={S.td}>
                    <ScoreBar value={prog} color="#a78bfa" />
                  </td>

                  {/* Actions */}
                  <td style={S.td}>
                    <div style={{ display: "flex", gap: 6 }}>
                      <button style={S.actionBtn} title="Voir" onClick={() => onOpenAudit(audit.id)}
                        onMouseEnter={e => { e.currentTarget.style.borderColor = "#7c70d8"; e.currentTarget.style.color = "#a89fff"; }}
                        onMouseLeave={e => { e.currentTarget.style.borderColor = "#2a2840"; e.currentTarget.style.color = "#6b6788"; }}>
                        <i className="ti ti-eye" aria-hidden="true" />
                      </button>
                      <button style={S.actionBtn} title="Rapport"
                        onMouseEnter={e => { e.currentTarget.style.borderColor = "#7c70d8"; e.currentTarget.style.color = "#a89fff"; }}
                        onMouseLeave={e => { e.currentTarget.style.borderColor = "#2a2840"; e.currentTarget.style.color = "#6b6788"; }}>
                        <i className="ti ti-file-text" aria-hidden="true" />
                      </button>
                      <button style={S.actionBtn} title="Supprimer" onClick={() => deleteAudit(audit.id)}
                        onMouseEnter={e => { e.currentTarget.style.borderColor = "#e03c52"; e.currentTarget.style.color = "#e03c52"; }}
                        onMouseLeave={e => { e.currentTarget.style.borderColor = "#2a2840"; e.currentTarget.style.color = "#6b6788"; }}>
                        <i className="ti ti-trash" aria-hidden="true" />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
