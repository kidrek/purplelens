import { useEffect, useState, useRef, useCallback } from "react";
import { api, ENUMS } from "../api/client";
import {
  Modal, Field, Input, NumberInput, Select, Textarea, ConfirmDialog, EmptyState,
} from "../components/Form";
import { RefGroup } from "../components/RefPicker";
import { parseRefValue, refToReadable } from "../lib/refData";
import { severityClass } from "../lib/format";
import { useToast } from "../lib/useToast";

// ── Heatmap vulnérabilités ───────────────────────────────────────────────────
const MONTH_NAMES = ["Jan","Fév","Mar","Avr","Mai","Jun","Jul","Aoû","Sep","Oct","Nov","Déc"];
const DAY_LABELS  = ["Lun","","Mer","","Ven","",""];

const VULN_LEVELS = [
  { min: 0, max: 0, bg: "#1a192c", shadow: null },
  { min: 1, max: 2, bg: "#3d1220", shadow: null },
  { min: 3, max: 5, bg: "#7a1e35", shadow: null },
  { min: 6, max: 9, bg: "#b82a48", shadow: null },
  { min: 10, max: Infinity, bg: "#e03c52", shadow: "0 0 5px #e03c5288" },
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
  };
}

function CalendarHeatmap({ dayData, activeRange }) {
  const wrapRef = useRef(null);
  const [cellSize, setCellSize] = useState(11);
  const [weeks, setWeeks] = useState([]);

  const year = new Date().getFullYear();
  const today = new Date(); today.setHours(0, 0, 0, 0);

  useEffect(() => {
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

  const total = Object.entries(dayData)
    .filter(([k]) => { const d = new Date(k); return !activeRange || (d >= activeRange.from && d <= activeRange.to); })
    .reduce((s, [, v]) => s + v, 0);

  return (
    <div style={{ background: "#12111f", border: "0.5px solid #2a2840", borderRadius: 10, padding: "14px 16px", marginBottom: 24 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
        <div style={{ fontSize: 11, color: "#6b6788", textTransform: "uppercase", letterSpacing: "0.07em", display: "flex", alignItems: "center", gap: 6 }}>
          <i className="ti ti-bug" aria-hidden="true" />
          Vulnérabilités détectées sur la période
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ fontSize: 11, color: "#6b6788" }}>
            Total : <span style={{ color: "#e03c52", fontWeight: 600 }}>{total}</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 10, color: "#6b6788" }}>
            <span>Moins</span>
            {["#3d1220", "#7a1e35", "#b82a48", "#e03c52"].map((bg, i) => (
              <div key={i} style={{ width: 10, height: 10, borderRadius: 2, background: bg }} />
            ))}
            <span>Plus</span>
          </div>
        </div>
      </div>
      <div ref={wrapRef}>
        <div style={{ position: "relative", height: 14, marginLeft: DAY_LABEL_W, marginBottom: 4 }}>
          {Object.entries(monthPositions).map(([m, wi]) => (
            <span key={m} style={{ position: "absolute", left: wi * step, fontSize: 10, color: "#6b6788", whiteSpace: "nowrap" }}>
              {MONTH_NAMES[m]}
            </span>
          ))}
        </div>
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
                  <div key={wi} style={getCellStyle(value, VULN_LEVELS, cellSize, dimmed)} title={title} />
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Finding ──────────────────────────────────────────────────────────────────
const EMPTY = {
  title: "", description: "", impact: "", cvss: 0, severity: "Medium",
  status: "Open",
  owasp: "", owasp_refs: "",
  cwe: "",   cwe_refs: "",
  capec: "", capec_refs: "",
  application_id: null, audit_id: null,
};

/**
 * Extrait les identifiants lisibles depuis le JSON stocké (owasp_refs, cwe_refs, capec_refs)
 * ou depuis la chaîne legacy (owasp, cwe, capec) pour les entrées antérieures.
 */
function resolveRefs(finding) {
  return {
    owasp_refs: finding.owasp_refs || (finding.owasp && !finding.owasp.startsWith("[") ? "" : finding.owasp) || "",
    cwe_refs:   finding.cwe_refs   || (finding.cwe   && !finding.cwe.startsWith("[")   ? "" : finding.cwe)   || "",
    capec_refs: finding.capec_refs || (finding.capec && !finding.capec.startsWith("[") ? "" : finding.capec) || "",
    // Libellés lisibles pour affichage (colonne Mapping)
    owasp: finding.owasp_refs
      ? refToReadable(parseRefValue(finding.owasp_refs))
      : finding.owasp || "",
    cwe: finding.cwe_refs
      ? refToReadable(parseRefValue(finding.cwe_refs))
      : finding.cwe || "",
    capec: finding.capec_refs
      ? refToReadable(parseRefValue(finding.capec_refs))
      : finding.capec || "",
  };
}

export default function ManageFindings({ onSelectApp }) {
  const [items, setItems] = useState(null);
  const [apps, setApps] = useState([]);
  const [audits, setAudits] = useState([]);
  const [filterApp, setFilterApp] = useState("");
  const [editing, setEditing] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [err, setErr] = useState(null);
  const [vulnHeatmap, setVulnHeatmap] = useState(null);
  const { show, node } = useToast();

  const load = () => {
    api.findings(filterApp || undefined).then(setItems).catch(() => setItems([]));
    api.applications().then(setApps).catch(() => {});
    api.audits().then(setAudits).catch(() => {});
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [filterApp]);

  useEffect(() => {
    fetch("/api/audits/kpis?period=1a")
      .then(r => r.json())
      .then(d => setVulnHeatmap(d.vuln_heatmap))
      .catch(() => {});
  }, []);

  const appName = (id) => apps.find((a) => a.id === id)?.name || "—";

  function openNew() {
    setErr(null);
    setEditing({ form: { ...EMPTY, application_id: apps[0]?.id ?? null } });
  }
  function openEdit(f) {
    setErr(null);
    setEditing({ id: f.id, form: { ...EMPTY, ...f, ...resolveRefs(f) } });
  }
  const set = (k, v) => setEditing((e) => ({ ...e, form: { ...e.form, [k]: v } }));

  function handleRefChange(refs, readables) {
    setEditing((e) => ({
      ...e,
      form: {
        ...e.form,
        owasp_refs: refs.owasp,
        cwe_refs:   refs.cwe,
        capec_refs: refs.capec,
        owasp: readables.owasp,
        cwe:   readables.cwe,
        capec: readables.capec,
      },
    }));
  }

  async function save() {
    const f = editing.form;
    if (!f.title.trim()) { setErr("Le titre est obligatoire."); return; }
    if (!f.application_id) { setErr("Sélectionnez une application."); return; }
    const payload = { ...f, audit_id: f.audit_id || null };
    try {
      if (editing.id) { await api.updateFinding(editing.id, payload); show("Vulnérabilité mise à jour"); }
      else { await api.createFinding(payload); show("Vulnérabilité créée"); }
      setEditing(null); load();
    } catch (e) { setErr(e.message); }
  }

  async function doDelete() {
    try { await api.deleteFinding(confirm.id); show("Vulnérabilité supprimée"); setConfirm(null); load(); }
    catch (e) { show(e.message, "err"); setConfirm(null); }
  }

  // Construit les chips de mapping pour la colonne tableau
  function mappingChips(f) {
    const refs = resolveRefs(f);
    const chips = [];
    // Depuis les JSON stockés
    for (const r of parseRefValue(refs.owasp_refs)) chips.push({ id: r.ref_id, cls: "ttp ttp-owasp" });
    for (const r of parseRefValue(refs.cwe_refs))   chips.push({ id: r.ref_id, cls: "ttp ttp-cwe" });
    for (const r of parseRefValue(refs.capec_refs)) chips.push({ id: r.ref_id, cls: "ttp ttp-capec" });
    // Fallback legacy (string courte)
    if (!chips.length) {
      [f.owasp, f.cwe, f.capec].filter(Boolean).forEach(m => chips.push({ id: m, cls: "ttp" }));
    }
    return chips;
  }

  const auditsForApp = editing
    ? audits.filter((a) => a.application_id === editing.form.application_id)
    : [];

  return (
    <>
      <div className="page-head">
        <div className="page-eyebrow">Module 5</div>
        <h1 className="page-title">Gestion des vulnérabilités</h1>
        <p className="page-sub">
          Les findings remontés pendant les audits, avec leur mapping OWASP /
          CWE / CAPEC et leur cycle de remédiation.
        </p>
      </div>

      <div className="toolbar" style={{ justifyContent: "space-between" }}>
        <select className="select" style={{ maxWidth: 240 }}
          value={filterApp} onChange={(e) => setFilterApp(e.target.value)}>
          <option value="">Toutes les applications</option>
          {apps.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
        <button className="btn btn-primary" onClick={openNew} disabled={apps.length === 0}>
          + Nouvelle vulnérabilité
        </button>
      </div>

      {vulnHeatmap && (
        <CalendarHeatmap
          dayData={vulnHeatmap}
          activeRange={(() => {
            const today = new Date(); today.setHours(0, 0, 0, 0);
            return { from: new Date(today.getFullYear(), 0, 1), to: today };
          })()}
        />
      )}

      {apps.length === 0 ? (
        <EmptyState title="Aucune application" hint="Créez une application avant d'enregistrer des vulnérabilités." />
      ) : items?.length === 0 ? (
        <EmptyState title="Aucune vulnérabilité" hint="Aucune entrée pour ce filtre." />
      ) : (
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>Titre</th><th>Sévérité</th><th>CVSS</th>
                <th>Application</th><th>Mapping</th><th>Statut</th>
                <th style={{ textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {!items && <tr><td colSpan={7} className="faint">Chargement…</td></tr>}
              {items?.map((f) => (
                <tr key={f.id}>
                  <td style={{ fontWeight: 500 }}>{f.title}</td>
                  <td><span className={`badge ${severityClass(f.severity)}`}>{f.severity}</span></td>
                  <td className="mono">{f.cvss.toFixed(1)}</td>
                  <td className="muted" style={{ fontSize: 13, cursor: "pointer" }}
                      onClick={() => onSelectApp && onSelectApp(f.application_id)}>
                    {appName(f.application_id)}
                  </td>
                  <td>
                    {mappingChips(f).length > 0
                      ? mappingChips(f).map(c => <span className={c.cls} key={c.id}>{c.id}</span>)
                      : <span className="faint">—</span>}
                  </td>
                  <td className="muted" style={{ fontSize: 13 }}>{f.status}</td>
                  <td>
                    <div className="row-actions">
                      <button className="icon-btn" title="Modifier" onClick={() => openEdit(f)}>✎</button>
                      <button className="icon-btn danger" title="Supprimer" onClick={() => setConfirm(f)}>🗑</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editing && (
        <Modal
          title={editing.id ? "Modifier la vulnérabilité" : "Nouvelle vulnérabilité"}
          onClose={() => setEditing(null)}
          error={err}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setEditing(null)}>Annuler</button>
              <button className="btn btn-primary" onClick={save}>Enregistrer</button>
            </>
          }
        >
          <Field label="Titre *">
            <Input value={editing.form.title} onChange={(v) => set("title", v)} placeholder="ex. Injection SQL formulaire de recherche" />
          </Field>
          <Field label="Description">
            <Textarea value={editing.form.description} onChange={(v) => set("description", v)} />
          </Field>
          <Field label="Impact">
            <Textarea value={editing.form.impact} onChange={(v) => set("impact", v)} />
          </Field>
          <div className="field-row-3">
            <Field label="Sévérité">
              <Select value={editing.form.severity} onChange={(v) => set("severity", v)} options={ENUMS.severity} />
            </Field>
            <Field label="CVSS">
              <NumberInput min={0} max={10} step={0.1} value={editing.form.cvss} onChange={(v) => set("cvss", v ?? 0)} />
            </Field>
            <Field label="Statut">
              <Select value={editing.form.status} onChange={(v) => set("status", v)} options={ENUMS.findingStatus} />
            </Field>
          </div>

          <Field label="Références de sécurité">
            <RefGroup
              values={{
                owasp: editing.form.owasp_refs || "",
                cwe:   editing.form.cwe_refs   || "",
                capec: editing.form.capec_refs  || "",
              }}
              onChange={handleRefChange}
            />
          </Field>

          <div className="field-row">
            <Field label="Application *">
              <select className="select"
                value={editing.form.application_id ?? ""}
                onChange={(e) => { set("application_id", Number(e.target.value)); set("audit_id", null); }}>
                {apps.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
              </select>
            </Field>
            <Field label="Audit (optionnel)">
              <select className="select"
                value={editing.form.audit_id ?? ""}
                onChange={(e) => set("audit_id", e.target.value ? Number(e.target.value) : null)}>
                <option value="">Aucun</option>
                {auditsForApp.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
              </select>
            </Field>
          </div>
        </Modal>
      )}

      {confirm && (
        <ConfirmDialog
          message={`Supprimer la vulnérabilité « ${confirm.title} » ?`}
          onConfirm={doDelete}
          onCancel={() => setConfirm(null)}
        />
      )}
      {node}
    </>
  );
}
