import { useEffect, useRef, useState } from "react";
import { api, ENUMS } from "../api/client";
import {
  Modal, Field, Input, NumberInput, Select,
  Textarea, ConfirmDialog, EmptyState,
} from "../components/Form";
import { CpePicker } from "../components/CpePicker";
import { DIC } from "../components/Shared";
import { useToast } from "../lib/useToast";
import { searchCPE, parseTechnologiesCpe } from "../lib/cpeData";

// ── Constantes ────────────────────────────────────────────────────────────────

const EMPTY = {
  name: "", description: "", owner: "", team: "", email: "", phone: "",
  exposure: "Interne", technologies: "", technologies_cpe: "", url: "",
  scope_red_team: "", scope_pentest: "",
  dic_availability: 3, dic_integrity: 3, dic_confidentiality: 3,
};

const AUDIT_TYPES = [
  { key: "BAS",         label: "BAS", color: "#1D9E75" },
  { key: "Pentest",     label: "PEN", color: "#1D9E75" },
  { key: "Red Team",    label: "RED", color: "#1D9E75" },
  { key: "Purple Team", label: "PUR", color: "#1D9E75" },
];

const EXPO_COLORS = {
  Internet: "#EF9F27", Interne: "#888780",
  Partenaire: "#1D9E75", Cloud: "#378ADD",
};

// ── Sous-composants ───────────────────────────────────────────────────────────

function CoverageBlocks({ coverage }) {
  if (!coverage) return <span className="faint" style={{ fontSize: 13 }}>—</span>;
  return (
    <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
      {AUDIT_TYPES.map(({ key, label, color }) => {
        const status = coverage[key];
        return (
          <div key={key} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 3 }}
            title={status === "done" ? `${key} — réalisé` : status === "in_progress" ? `${key} — en cours` : `${key} — jamais réalisé`}>
            <div style={{ width: 22, height: 10, borderRadius: 3,
              background: status ? color : "var(--line)",
              opacity: status === "in_progress" ? 0.5 : 1 }} />
            <span style={{ fontSize: 9, fontFamily: "var(--mono)", fontWeight: 600,
              textTransform: "uppercase", color: "var(--text-faint)" }}>{label}</span>
          </div>
        );
      })}
    </div>
  );
}

/** Champ avec chips multi-sélection + dropdown de suggestions */
function ChipFilter({ label, items, onAdd, onRemove, inputId, placeholder, children, ddId }) {
  return (
    <div className="adv-frow">
      <span className="adv-flabel">{label}</span>
      <div className="adv-fcontent" id={`${inputId}-wrap`}>
        <div style={{ display: "flex", gap: 5, flexWrap: "wrap", alignItems: "center" }}>
          {items.map(v => (
            <span key={v} className="adv-chip-sel">
              {v}
              <button className="adv-chip-rm" onMouseDown={() => onRemove(v)}>×</button>
            </span>
          ))}
        </div>
        <input id={inputId} className="adv-finput" placeholder={placeholder} autoComplete="off" />
        <div className="adv-fdd" id={ddId}>
          {children}
        </div>
      </div>
    </div>
  );
}

// ── Logique de filtrage ───────────────────────────────────────────────────────

function applyFilters(items, coverage, filters) {
  const { q, expos, owners, dicA, dicI, dicC, audits, techs } = filters;
  return items.filter(a => {
    if (q && !a.name.toLowerCase().includes(q.toLowerCase())) return false;
    if (expos.length && !expos.includes(a.exposure)) return false;
    if (owners.length && !owners.includes(a.owner)) return false;
    if (dicA !== null && a.dic_availability < dicA) return false;
    if (dicI !== null && a.dic_integrity < dicI) return false;
    if (dicC !== null && a.dic_confidentiality < dicC) return false;
    if (audits.length) {
      const cov = coverage[a.id] || {};
      if (!audits.every(type => cov[type] === "done" || cov[type] === "in_progress")) return false;
    }
    if (techs.length) {
      const appCpes = parseTechnologiesCpe(a.technologies_cpe).map(t => t.cpe);
      if (!techs.every(cpe => appCpes.includes(cpe))) return false;
    }
    return true;
  });
}

function countAdvFilters(filters) {
  const { expos, owners, dicA, dicI, dicC, audits, techs } = filters;
  return expos.length + owners.length + audits.length + techs.length
    + (dicA !== null ? 1 : 0) + (dicI !== null ? 1 : 0) + (dicC !== null ? 1 : 0);
}

// ── Composant principal ───────────────────────────────────────────────────────

const AUDIT_TYPE_LABELS = {
  "BAS": "BAS", "Pentest": "PEN", "Red Team": "RED", "Purple Team": "PUR",
};

function KpiBar({ pct, color }) {
  return (
    <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: 3, background: "var(--line)" }}>
      <div style={{ height: "100%", width: `${pct}%`, background: color, borderRadius: 0 }} />
    </div>
  );
}

function ApplicationsKpis({ kpis }) {
  if (!kpis) return null;
  const auditTypes = ["BAS", "Pentest", "Red Team", "Purple Team"];
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 10, marginBottom: 16 }}>

      {/* 1. Total applications */}
      <div className="app-kpi">
        <span className="app-kpi-label">Applications</span>
        <span className="app-kpi-value">{kpis.total}</span>
        <span className="app-kpi-sub">dans le référentiel</span>
      </div>

      {/* 2. Exposées Internet */}
      <div className="app-kpi">
        <span className="app-kpi-label">Exposées Internet</span>
        <span className="app-kpi-value" style={{ color: "#EF9F27" }}>{kpis.internet_count}</span>
        <span className="app-kpi-sub">
          <strong>{kpis.internet_pct} %</strong> du périmètre
        </span>
      </div>

      {/* 3. Couverture audit — 4 mini-barres */}
      <div className="app-kpi">
        <span className="app-kpi-label">Couverture audit</span>
        <div style={{ display: "flex", gap: 8, marginTop: 6, alignItems: "flex-end" }}>
          {auditTypes.map(type => {
            const pct = kpis.audit_coverage?.[type] ?? 0;
            return (
              <div key={type} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 3, flex: 1 }}>
                <span style={{ fontFamily: "var(--mono)", fontSize: 12, fontWeight: 700, color: "var(--text)" }}>
                  {pct}<span style={{ fontSize: 10, opacity: .6 }}>%</span>
                </span>
                <div style={{ width: "100%", height: 5, background: "var(--line)", borderRadius: 3, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${pct}%`, background: "#1D9E75", borderRadius: 3 }} />
                </div>
                <span style={{ fontSize: 9, fontFamily: "var(--mono)", fontWeight: 600, textTransform: "uppercase", color: "var(--text-faint)", letterSpacing: ".04em" }}>
                  {AUDIT_TYPE_LABELS[type]}
                </span>
              </div>
            );
          })}
        </div>
        <span className="app-kpi-sub" style={{ marginTop: 4 }}>% d'apps couvertes par type</span>
      </div>

      {/* 4. Détection */}
      <div className="app-kpi" style={{ position: "relative", overflow: "hidden" }}>
        <span className="app-kpi-label">Couverture détection</span>
        <span className="app-kpi-value" style={{ color: "#1D9E75" }}>
          {kpis.detection_pct}<span style={{ fontSize: 18, opacity: .55, fontWeight: 500 }}>%</span>
        </span>
        <span className="app-kpi-sub">des techniques testées</span>
        <KpiBar pct={kpis.detection_pct} color="#1D9E75" />
      </div>

      {/* 5. Réaction */}
      <div className="app-kpi" style={{ position: "relative", overflow: "hidden" }}>
        <span className="app-kpi-label">Couverture réaction</span>
        <span className="app-kpi-value" style={{ color: "#534AB7" }}>
          {kpis.reaction_pct}<span style={{ fontSize: 18, opacity: .55, fontWeight: 500 }}>%</span>
        </span>
        <span className="app-kpi-sub">des techniques testées</span>
        <KpiBar pct={kpis.reaction_pct} color="#534AB7" />
      </div>

    </div>
  );
}

export default function ManageApplications({ onSelectApp }) {
  const [items, setItems]       = useState(null);
  const [coverage, setCoverage] = useState({});
  const [kpis, setKpis]         = useState(null);
  const [editing, setEditing]   = useState(null);
  const [confirm, setConfirm]   = useState(null);
  const [err, setErr]           = useState(null);
  const { show, node }          = useToast();

  // État des filtres
  const [advOpen, setAdvOpen] = useState(false);
  const [filters, setFilters] = useState({
    q: "", expos: [], owners: [], dicA: null, dicI: null, dicC: null,
    audits: [], techs: [],   // techs = [{cpe, vendor, product}]
  });

  // Autocomplete
  const [techQuery, setTechQuery] = useState("");
  const [techSuggs, setTechSuggs] = useState([]);
  const [showTechDd, setShowTechDd] = useState(false);
  const [showExpoDd, setShowExpoDd] = useState(false);
  const [showOwnerDd, setShowOwnerDd] = useState(false);
  const [expoQuery, setExpoQuery] = useState("");
  const [ownerQuery, setOwnerQuery] = useState("");

  const techWrapRef  = useRef(null);
  const expoWrapRef  = useRef(null);
  const ownerWrapRef = useRef(null);

  const load = () => {
    api.applications().then(setItems).catch(() => setItems([]));
    api.applicationsCoverage().then(setCoverage).catch(() => setCoverage({}));
    api.applicationsKpis().then(setKpis).catch(() => setKpis(null));
  };
  useEffect(() => { load(); }, []);

  // Ferme dropdowns au clic extérieur
  useEffect(() => {
    function onDown(e) {
      if (techWrapRef.current  && !techWrapRef.current.contains(e.target))  setShowTechDd(false);
      if (expoWrapRef.current  && !expoWrapRef.current.contains(e.target))  setShowExpoDd(false);
      if (ownerWrapRef.current && !ownerWrapRef.current.contains(e.target)) setShowOwnerDd(false);
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, []);

  // Suggestions CPE
  useEffect(() => {
    setTechSuggs(techQuery.length >= 1 ? searchCPE(techQuery, 8) : []);
  }, [techQuery]);

  // Responsables uniques depuis la liste
  const uniqueOwners = [...new Set((items || []).map(a => a.owner).filter(Boolean))].sort();
  const filteredOwners = uniqueOwners.filter(o =>
    o.toLowerCase().includes(ownerQuery.toLowerCase()) && !filters.owners.includes(o)
  );
  const filteredExpos = ENUMS.exposure.filter(e =>
    e.toLowerCase().includes(expoQuery.toLowerCase()) && !filters.expos.includes(e)
  );

  // Helpers filtres
  const setF = (key, val) => setFilters(f => ({ ...f, [key]: val }));

  function toggleList(key, val) {
    setFilters(f => {
      const cur = f[key];
      return { ...f, [key]: cur.includes(val) ? cur.filter(v => v !== val) : [...cur, val] };
    });
  }
  function toggleDic(dim, val) {
    const key = `dic${dim}`;
    setFilters(f => ({ ...f, [key]: f[key] === val ? null : val }));
  }
  function addTech(item) {
    if (!filters.techs.find(t => t.cpe === item.cpe)) {
      setF("techs", [...filters.techs, item]);
    }
    setTechQuery(""); setShowTechDd(false);
  }
  function removeTech(cpe) { setF("techs", filters.techs.filter(t => t.cpe !== cpe)); }

  function resetAdv() {
    setFilters(f => ({ ...f, expos: [], owners: [], dicA: null, dicI: null, dicC: null, audits: [], techs: [] }));
    setExpoQuery(""); setOwnerQuery(""); setTechQuery("");
  }

  // Données filtrées
  const filtered = items ? applyFilters(items, coverage, filters) : [];
  const advCount  = countAdvFilters(filters);

  // CRUD
  function openNew()  { setErr(null); setEditing({ form: { ...EMPTY } }); }
  function openEdit(a) { setErr(null); setEditing({ id: a.id, form: { ...EMPTY, ...a } }); }
  const set = (k, v) => setEditing(e => ({ ...e, form: { ...e.form, [k]: v } }));

  async function save() {
    const f = editing.form;
    if (!f.name.trim()) { setErr("Le nom est obligatoire."); return; }
    try {
      if (editing.id) { await api.updateApplication(editing.id, f); show("Application mise à jour"); }
      else            { await api.createApplication(f);             show("Application créée"); }
      setEditing(null); load();
    } catch (e) { setErr(e.message); }
  }
  async function doDelete() {
    try { await api.deleteApplication(confirm.id); show("Application supprimée"); setConfirm(null); load(); }
    catch (e) { show(e.message, "err"); setConfirm(null); }
  }

  return (
    <>
      <div className="page-head">
        <div className="page-eyebrow">Module 1</div>
        <h1 className="page-title">Gestion des applications</h1>
        <p className="page-sub">Le référentiel central. Toutes les métriques sont calculées par application.</p>
      </div>

      <div className="toolbar">
        <button className="btn btn-primary" onClick={openNew}>+ Nouvelle application</button>
      </div>

      <ApplicationsKpis kpis={kpis} />

      {/* ── Barre de filtres ── */}
      <div className="adv-filters-bar">

        {/* Ligne principale */}
        <div className="adv-main-row">
          <div style={{ position: "relative", flex: 1 }}>
            <i className="ti ti-search" style={{ position: "absolute", left: 13, top: "50%",
              transform: "translateY(-50%)", fontSize: 16, color: "var(--text-faint)",
              pointerEvents: "none" }} aria-hidden="true" />
            <input
              className="adv-search-input"
              type="text"
              placeholder="Rechercher une application…"
              value={filters.q}
              onChange={e => setF("q", e.target.value)}
            />
          </div>
          <button
            className={`adv-toggle-btn${advOpen ? " open" : ""}`}
            onClick={() => setAdvOpen(o => !o)}
          >
            <i className="ti ti-adjustments-horizontal" style={{ fontSize: 15 }} aria-hidden="true" />
            Filtres avancés
            {advCount > 0 && <span className="adv-count-badge">{advCount}</span>}
            <i className={`ti ti-chevron-down adv-chevron${advOpen ? " open" : ""}`} aria-hidden="true" />
          </button>
        </div>

        {/* Section avancée */}
        {advOpen && (
          <div className="adv-advanced">

            {/* Exposition */}
            <div className="adv-frow">
              <span className="adv-flabel">Exposition</span>
              <div className="adv-fcontent" ref={expoWrapRef}>
                {filters.expos.map(v => (
                  <span key={v} className="adv-chip-sel">
                    <span style={{ width: 7, height: 7, borderRadius: "50%", background: EXPO_COLORS[v] || "var(--text-dim)", display: "inline-block", flexShrink: 0 }} />
                    {v}
                    <button className="adv-chip-rm" onMouseDown={() => toggleList("expos", v)}>×</button>
                  </span>
                ))}
                <input
                  className="adv-finput"
                  placeholder={filters.expos.length ? "Ajouter…" : "Internet, Interne, Partenaire, Cloud…"}
                  value={expoQuery}
                  onChange={e => setExpoQuery(e.target.value)}
                  onFocus={() => setShowExpoDd(true)}
                  autoComplete="off"
                />
                {showExpoDd && filteredExpos.length > 0 && (
                  <div className="adv-fdd">
                    <div className="adv-fdd-head">Type d'exposition</div>
                    {filteredExpos.map(e => (
                      <div key={e} className="adv-fdd-item" onMouseDown={() => { toggleList("expos", e); setExpoQuery(""); setShowExpoDd(false); }}>
                        <span style={{ width: 8, height: 8, borderRadius: "50%", background: EXPO_COLORS[e] || "var(--text-dim)", flexShrink: 0 }} />
                        {e}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Responsable */}
            <div className="adv-frow">
              <span className="adv-flabel">Responsable</span>
              <div className="adv-fcontent" ref={ownerWrapRef}>
                {filters.owners.map(v => (
                  <span key={v} className="adv-chip-sel">
                    {v}
                    <button className="adv-chip-rm" onMouseDown={() => toggleList("owners", v)}>×</button>
                  </span>
                ))}
                <input
                  className="adv-finput"
                  placeholder={filters.owners.length ? "Ajouter…" : "Rechercher un responsable…"}
                  value={ownerQuery}
                  onChange={e => setOwnerQuery(e.target.value)}
                  onFocus={() => setShowOwnerDd(true)}
                  autoComplete="off"
                />
                {showOwnerDd && filteredOwners.length > 0 && (
                  <div className="adv-fdd">
                    <div className="adv-fdd-head">Responsables</div>
                    {filteredOwners.map(o => (
                      <div key={o} className="adv-fdd-item" onMouseDown={() => { toggleList("owners", o); setOwnerQuery(""); setShowOwnerDd(false); }}>
                        {o}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* DIC */}
            <div className="adv-frow">
              <span className="adv-flabel">DIC minimum</span>
              <div className="adv-fcontent" style={{ gap: 4 }}>
                {[["A", "Disponibilité", filters.dicA], ["I", "Intégrité", filters.dicI], ["C", "Confidentialité", filters.dicC]].map(([dim, lbl, cur], idx) => (
                  <span key={dim} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                    {idx > 0 && <span style={{ color: "var(--text-faint)", margin: "0 6px", fontSize: 11 }}>·</span>}
                    <span style={{ fontSize: 12, color: "var(--text-dim)", marginRight: 3 }}>{lbl}</span>
                    {[1, 2, 3, 4, 5].map(v => (
                      <button
                        key={v}
                        className={`adv-dic-tog${cur === v ? " on" : ""}`}
                        onClick={() => toggleDic(dim, v)}
                      >≥ {v}</button>
                    ))}
                  </span>
                ))}
              </div>
            </div>

            {/* Audit réalisé */}
            <div className="adv-frow">
              <span className="adv-flabel">Audit réalisé</span>
              <div className="adv-fcontent">
                {AUDIT_TYPES.map(({ key, color }) => {
                  const on = filters.audits.includes(key);
                  return (
                    <button
                      key={key}
                      className={`adv-audit-tog${on ? " on" : ""}`}
                      style={on ? { borderColor: color, background: `${color}18`, color } : {}}
                      onClick={() => toggleList("audits", key)}
                    >
                      <span style={{ width: 8, height: 8, borderRadius: 2, background: color, opacity: on ? 1 : 0.35, flexShrink: 0 }} />
                      {key}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Technologie */}
            <div className="adv-frow" style={{ borderBottom: "none" }}>
              <span className="adv-flabel">Technologie</span>
              <div className="adv-fcontent" ref={techWrapRef}>
                {filters.techs.map(t => (
                  <span key={t.cpe} className="adv-chip-sel adv-chip-cpe" title={t.cpe}>
                    <span style={{ fontSize: 10, opacity: .7, fontFamily: "var(--mono)" }}>{t.vendor}</span>
                    {t.product}
                    <button className="adv-chip-rm" onMouseDown={() => removeTech(t.cpe)}>×</button>
                  </span>
                ))}
                <input
                  className="adv-finput"
                  placeholder={filters.techs.length ? "Ajouter…" : "Filtrer par technologie CPE…"}
                  value={techQuery}
                  onChange={e => { setTechQuery(e.target.value); setShowTechDd(true); }}
                  onFocus={() => techQuery.length >= 1 && setShowTechDd(true)}
                  autoComplete="off"
                />
                {showTechDd && techSuggs.length > 0 && (
                  <div className="adv-fdd">
                    <div className="adv-fdd-head">Référentiel CPE</div>
                    {techSuggs.filter(s => !filters.techs.find(t => t.cpe === s.cpe)).map(s => (
                      <div key={s.cpe} className="adv-fdd-item" onMouseDown={() => addTech(s)}>
                        <span className="adv-fdd-vendor">{s.vendor.toLowerCase()}</span>
                        {s.product}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Footer */}
            <div className="adv-footer">
              {advCount > 0 ? (
                <>
                  <span className="adv-active-badge">{advCount} filtre{advCount > 1 ? "s" : ""} actif{advCount > 1 ? "s" : ""}</span>
                  <button className="adv-reset-btn" onClick={resetAdv}>
                    <i className="ti ti-x" style={{ fontSize: 11 }} aria-hidden="true" /> Réinitialiser
                  </button>
                </>
              ) : (
                <span style={{ fontSize: 12, color: "var(--text-faint)" }}>Aucun filtre avancé actif</span>
              )}
              <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--text-faint)" }}>
                {filtered.length} / {items?.length ?? 0} application{filtered.length > 1 ? "s" : ""}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* ── Table ── */}
      {items?.length === 0 ? (
        <EmptyState title="Aucune application" hint="Créez votre première application pour commencer." />
      ) : filtered.length === 0 && items?.length > 0 ? (
        <EmptyState title="Aucun résultat" hint="Aucune application ne correspond aux filtres actifs." />
      ) : (
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>Nom</th>
                <th>Exposition</th>
                <th>Responsable</th>
                <th>DIC</th>
                <th>Couverture</th>
                <th style={{ textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {!items && <tr><td colSpan={6} className="faint">Chargement…</td></tr>}
              {filtered.map(a => (
                <tr key={a.id}>
                  <td style={{ fontWeight: 600, cursor: "pointer" }} onClick={() => onSelectApp && onSelectApp(a.id)}>
                    {a.name}
                  </td>
                  <td><span className="badge violet">{a.exposure}</span></td>
                  <td className="muted">{a.owner || "—"}</td>
                  <td>
                    <DIC dic={{ availability: a.dic_availability, integrity: a.dic_integrity, confidentiality: a.dic_confidentiality }} />
                  </td>
                  <td><CoverageBlocks coverage={coverage[a.id]} /></td>
                  <td>
                    <div className="row-actions">
                      <button className="icon-btn" title="Modifier" onClick={() => openEdit(a)}>✎</button>
                      <button className="icon-btn danger" title="Supprimer" onClick={() => setConfirm(a)}>🗑</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Modal édition ── */}
      {editing && (
        <Modal
          title={editing.id ? "Modifier l'application" : "Nouvelle application"}
          onClose={() => setEditing(null)}
          error={err}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setEditing(null)}>Annuler</button>
              <button className="btn btn-primary" onClick={save}>Enregistrer</button>
            </>
          }
        >
          <Field label="Nom *">
            <Input value={editing.form.name} onChange={v => set("name", v)} placeholder="ex. CRM Clients" />
          </Field>
          <Field label="Description">
            <Textarea value={editing.form.description} onChange={v => set("description", v)} />
          </Field>
          <div className="field-row">
            <Field label="Responsable"><Input value={editing.form.owner} onChange={v => set("owner", v)} /></Field>
            <Field label="Équipe"><Input value={editing.form.team} onChange={v => set("team", v)} /></Field>
          </div>
          <div className="field-row">
            <Field label="Email"><Input value={editing.form.email} onChange={v => set("email", v)} /></Field>
            <Field label="Téléphone"><Input value={editing.form.phone} onChange={v => set("phone", v)} /></Field>
          </div>
          <div className="field-row">
            <Field label="Exposition">
              <Select value={editing.form.exposure} onChange={v => set("exposure", v)} options={ENUMS.exposure} />
            </Field>
            <Field label="URL">
              <Input value={editing.form.url} onChange={v => set("url", v)} placeholder="https://…" />
            </Field>
          </div>
          <Field label="Technologies">
            <CpePicker
              valueRaw={editing.form.technologies_cpe}
              onChange={(raw, readable) => setEditing(e => ({ ...e, form: { ...e.form, technologies_cpe: raw, technologies: readable } }))}
            />
          </Field>
          <Field label="Criticité DIC (1 à 5)">
            <div className="field-row-3">
              <div><span className="hint">Disponibilité</span><NumberInput min={1} max={5} value={editing.form.dic_availability} onChange={v => set("dic_availability", v)} /></div>
              <div><span className="hint">Intégrité</span><NumberInput min={1} max={5} value={editing.form.dic_integrity} onChange={v => set("dic_integrity", v)} /></div>
              <div><span className="hint">Confidentialité</span><NumberInput min={1} max={5} value={editing.form.dic_confidentiality} onChange={v => set("dic_confidentiality", v)} /></div>
            </div>
          </Field>
          <div className="field-row">
            <Field label="Scope Red Team"><Textarea value={editing.form.scope_red_team} onChange={v => set("scope_red_team", v)} /></Field>
            <Field label="Scope Pentest"><Textarea value={editing.form.scope_pentest} onChange={v => set("scope_pentest", v)} /></Field>
          </div>
        </Modal>
      )}

      {confirm && (
        <ConfirmDialog
          message={`Supprimer « ${confirm.name} » ? Les audits et vulnérabilités liés seront aussi affectés. Cette action est irréversible.`}
          onConfirm={doDelete}
          onCancel={() => setConfirm(null)}
        />
      )}
      {node}
    </>
  );
}
