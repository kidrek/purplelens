/**
 * AppDrawerContent — vue détaillée d'une application dans un Drawer.
 *
 * Props :
 *   appId   {number}  — id de l'application
 *   onEdit  {fn}      — ouvre le formulaire d'édition
 *   onClose {fn}      — ferme le drawer
 */
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { AppEditForm } from "./AppEditForm";

// ── Tokens de style ───────────────────────────────────────────────────────────

const AUDIT_TYPE_STYLE = {
  "BAS":         { bg: "rgba(55,138,221,.1)",  border: "rgba(55,138,221,.3)",  text: "#185FA5" },
  "Pentest":     { bg: "rgba(239,159,39,.1)",  border: "rgba(239,159,39,.3)",  text: "#854F0B" },
  "Red Team":    { bg: "rgba(226,75,74,.1)",   border: "rgba(226,75,74,.3)",   text: "#A32D2D" },
  "Purple Team": { bg: "rgba(83,74,183,.1)",   border: "rgba(83,74,183,.3)",   text: "#534AB7" },
};

const AUDIT_STATUS_STYLE = {
  "Draft":       { bg: "#2C2C2A", border: "#444441", text: "#B4B2A9", dot: "#B4B2A9", label: "Brouillon"  },
  "Scoping":     { bg: "#042C53", border: "#0C447C", text: "#85B7EB", dot: "#85B7EB", label: "Scoping"    },
  "In Progress": { bg: "#412402", border: "#633806", text: "#FAC775", dot: "#FAC775", label: "En cours"   },
  "Review":      { bg: "#26215C", border: "#3C3489", text: "#AFA9EC", dot: "#AFA9EC", label: "Review"     },
  "Completed":   { bg: "#04342C", border: "#085041", text: "#5DCAA5", dot: "#5DCAA5", label: "Terminé"    },
  "Closed":      { bg: "#501313", border: "#791F1F", text: "#F09595", dot: "#F09595", label: "Clôturé"    },
};
const AUDIT_FILTER_ORDER = ["Draft", "Scoping", "In Progress", "Review", "Completed", "Closed"];

const SEV_ORDER = ["Critical", "High", "Medium", "Low", "Info"];
const SEVERITY_STYLE = {
  "Critical": { bg: "#501313", border: "#791F1F", text: "#F09595", dot: "#F09595", bar: "#E24B4A", label: "Critique" },
  "High":     { bg: "#412402", border: "#633806", text: "#FAC775", dot: "#FAC775", bar: "#EF9F27", label: "Haute"    },
  "Medium":   { bg: "#26215C", border: "#3C3489", text: "#AFA9EC", dot: "#AFA9EC", bar: "#7F77DD", label: "Moyenne"  },
  "Low":      { bg: "#04342C", border: "#085041", text: "#5DCAA5", dot: "#5DCAA5", bar: "#1D9E75", label: "Basse"    },
  "Info":     { bg: "#2C2C2A", border: "#444441", text: "#B4B2A9", dot: "#B4B2A9", bar: "#444441", label: "Info" },
};

const FINDING_STATUS_STYLE = {
  "Open":        { bg: "#501313", border: "#791F1F", text: "#F09595", dot: "#F09595", label: "Open"       },
  "Validated":   { bg: "#412402", border: "#633806", text: "#FAC775", dot: "#FAC775", label: "Validé"     },
  "Assigned":    { bg: "#26215C", border: "#3C3489", text: "#AFA9EC", dot: "#AFA9EC", label: "Assigné"    },
  "In Progress": { bg: "#042C53", border: "#0C447C", text: "#85B7EB", dot: "#85B7EB", label: "En cours"   },
  "Fixed":       { bg: "#04342C", border: "#085041", text: "#5DCAA5", dot: "#5DCAA5", label: "Corrigé"    },
  "Retested":    { bg: "#04342C", border: "#085041", text: "#5DCAA5", dot: "#5DCAA5", label: "Retesté"    },
  "Closed":      { bg: "#2C2C2A", border: "#444441", text: "#B4B2A9", dot: "#B4B2A9", label: "Clôturé" },
};
const FINDING_STATUS_ORDER = ["Open", "Validated", "Assigned", "In Progress", "Fixed", "Retested", "Closed"];

// ── Helpers ───────────────────────────────────────────────────────────────────

const initials = (name = "") =>
  name.split(" ").filter(Boolean).slice(0, 2).map(w => w[0].toUpperCase()).join("");

const fmtDate = (d) =>
  d ? new Date(d).toLocaleDateString("fr-FR", { month: "short", year: "numeric" }) : "—";

// Badge partagé filtre + ligne (all:unset pour les boutons)
function Badge({ as: Tag = "span", style: extraStyle, dot, children, ...rest }) {
  return (
    <Tag
      style={{
        all: Tag === "button" ? "unset" : undefined,
        boxSizing: "border-box", fontFamily: "inherit",
        display: "inline-flex", alignItems: "center", gap: 4,
        fontSize: 10, fontWeight: 500, padding: "3px 9px",
        borderRadius: 10, whiteSpace: "nowrap",
        cursor: Tag === "button" ? "pointer" : "default",
        transition: "opacity .12s",
        ...extraStyle,
      }}
      {...rest}
    >
      {dot && <span style={{ width: 5, height: 5, borderRadius: "50%", background: dot, flexShrink: 0 }} />}
      {children}
    </Tag>
  );
}

function Sep() {
  return <div style={{ height: "0.5px", background: "var(--line)", margin: "0 -20px" }} />;
}

function SectionLabel({ children, right }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
      <span style={{ fontSize: 10, fontWeight: 500, textTransform: "uppercase", letterSpacing: ".08em", color: "var(--text-faint)" }}>
        {children}
      </span>
      {right}
    </div>
  );
}

// ── Composant principal ───────────────────────────────────────────────────────

export function AppDrawerContent({ appId, onEdit }) {
  const [dash,     setDash]     = useState(null);
  const [app,      setApp]      = useState(null);
  const [audits,   setAudits]   = useState([]);
  const [findings, setFindings] = useState([]);
  const [loading,  setLoading]  = useState(true);
  const [editing,  setEditing]  = useState(false);  // mode édition inline
  const [appForm,  setAppForm]  = useState(null);   // données app pour le formulaire

  // Filtres audits
  const [auditFilter, setAuditFilter] = useState("all");

  // Filtres vulnérabilités — sévérité ET statut, cumulables
  const [sevFilter, setSevFilter] = useState(null);
  const [stFilter,  setStFilter]  = useState(null);

  useEffect(() => {
    if (!appId) return;
    setLoading(true);
    setAuditFilter("all");
    setSevFilter(null);
    setStFilter(null);
    setEditing(false);
    setAppForm(null);
    Promise.all([
      api.applicationDashboard(appId),
      api.getApplication ? api.getApplication(appId) : Promise.resolve(null),
      api.audits(),
      api.findings(appId),
    ]).then(([d, a, allAudits, f]) => {
      setDash(d);
      setApp(a);
      setAppForm(a || {});
      setAudits((allAudits || []).filter(au => au.application_id === appId));
      setFindings([...(f || [])].sort((a, b) => SEV_ORDER.indexOf(a.severity) - SEV_ORDER.indexOf(b.severity)));
    }).finally(() => setLoading(false));
  }, [appId]);

  if (loading) return (
    <div style={{ padding: 40, textAlign: "center", color: "var(--text-faint)", fontSize: 13 }}>Chargement…</div>
  );
  if (!dash) return null;

  const kpis    = dash.kpis || {};
  const dic     = dash.dic  || {};
  const covItems = dash.audit_coverage?.items || [];
  const vulns   = dash.vulnerabilities || {};
  const ini     = initials(dash.application_name);

  // Audits filtrés
  const filteredAudits = auditFilter === "all"
    ? audits
    : audits.filter(a => a.status === auditFilter);

  // Findings filtrés (sévérité ET statut)
  const filteredFindings = findings.filter(f =>
    (!sevFilter || f.severity === sevFilter) &&
    (!stFilter  || f.status   === stFilter)
  );

  const toggleSev = (sev) => setSevFilter(v => v === sev ? null : sev);
  const toggleSt  = (st)  => setStFilter(v  => v === st  ? null : st);

  return (
    <div style={{ display: "flex", flexDirection: "column" }}>

      {/* ── En-tête ── */}
      <div style={{
        display: "flex", alignItems: "flex-start", gap: 12,
        padding: "16px 20px 14px", borderBottom: "0.5px solid var(--line)",
      }}>
        <div style={{
          width: 42, height: 42, borderRadius: 10, flexShrink: 0,
          background: "rgba(83,74,183,.12)", border: "1px solid rgba(83,74,183,.3)",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 14, fontWeight: 500, color: "var(--violet-bright)", fontFamily: "var(--mono)",
        }}>{ini || "?"}</div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 17, fontWeight: 500, color: "var(--text)", marginBottom: 4 }}>
            {dash.application_name}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{
              fontSize: 10, fontWeight: 500, padding: "2px 9px", borderRadius: 10,
              background: "rgba(239,159,39,.1)", border: "0.5px solid rgba(239,159,39,.35)", color: "#854F0B",
            }}>{dash.exposure}</span>
            {dash.business_criticality?.label && (
              <span style={{ fontSize: 11, color: "var(--text-faint)" }}>
                Criticité {dash.business_criticality.label}
              </span>
            )}
          </div>
        </div>

        <button className="btn btn-ghost btn-sm" onClick={() => setEditing(true)} style={{ flexShrink: 0 }}>
          <i className="ti ti-edit" style={{ fontSize: 13, marginRight: 4 }} aria-hidden="true" />
          Éditer
        </button>
      </div>

      {/* ── Mode édition inline ── */}
      {editing && appForm != null && (
        <div style={{ padding: "18px 20px" }}>
          {/* Sous-en-tête mode édition */}
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            marginBottom: 16, paddingBottom: 12, borderBottom: "0.5px solid var(--line)",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <button
                onClick={() => setEditing(false)}
                style={{
                  all: "unset", cursor: "pointer", display: "flex", alignItems: "center",
                  gap: 5, fontSize: 12, color: "var(--text-faint)",
                }}
              >
                <i className="ti ti-arrow-left" style={{ fontSize: 14 }} aria-hidden="true" />
                Retour
              </button>
              <span style={{ fontSize: 12, color: "var(--text-faint)" }}>·</span>
              <span style={{ fontSize: 13, fontWeight: 500, color: "var(--text)" }}>
                Modifier {dash.application_name}
              </span>
            </div>
          </div>
          <AppEditForm
            appId={appId}
            initial={appForm}
            onSaved={(updated) => {
              setEditing(false);
              // Recharger les données du drawer
              setLoading(true);
              Promise.all([
                api.applicationDashboard(appId),
                api.getApplication ? api.getApplication(appId) : Promise.resolve(null),
                api.audits(),
                api.findings(appId),
              ]).then(([d, a, allAudits, f]) => {
                setDash(d);
                setApp(a);
                setAppForm(a || {});
                setAudits((allAudits || []).filter(au => au.application_id === appId));
                setFindings([...(f || [])].sort((x, y) => SEV_ORDER.indexOf(x.severity) - SEV_ORDER.indexOf(y.severity)));
              }).finally(() => setLoading(false));
              onEdit?.();
            }}
            onCancel={() => setEditing(false)}
          />
        </div>
      )}

      {/* ── Corps (vue détail) ── */}
      {!editing && <div style={{ padding: "18px 20px", display: "flex", flexDirection: "column", gap: 18 }}>

        {/* Informations */}
        <div>
          <SectionLabel>Informations</SectionLabel>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            {[
              { label: "Responsable",    val: app?.owner || "—" },
              { label: "Audits réalisés", val: dash.audits_count ?? "—" },
            ].map(({ label, val }) => (
              <div key={label} style={{ background: "var(--surface-2)", borderRadius: 8, padding: "9px 12px" }}>
                <div style={{ fontSize: 10, color: "var(--text-faint)", marginBottom: 2 }}>{label}</div>
                <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text)" }}>{val}</div>
              </div>
            ))}
            {app?.description && (
              <div style={{ background: "var(--surface-2)", borderRadius: 8, padding: "9px 12px", gridColumn: "1/-1" }}>
                <div style={{ fontSize: 10, color: "var(--text-faint)", marginBottom: 2 }}>Description</div>
                <div style={{ fontSize: 12, color: "var(--text-dim)", lineHeight: 1.5 }}>{app.description}</div>
              </div>
            )}
          </div>
        </div>

        <Sep />

        {/* DIC */}
        <div>
          <SectionLabel>Criticité DIC</SectionLabel>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {[
              { letter: "D", label: "Disponibilité",   chip: { bg: "rgba(29,158,117,.1)", border: "rgba(29,158,117,.3)", text: "#0F6E56" }, val: dic.availability },
              { letter: "I", label: "Intégrité",       chip: { bg: "rgba(239,159,39,.1)", border: "rgba(239,159,39,.3)", text: "#854F0B" }, val: dic.integrity },
              { letter: "C", label: "Confidentialité", chip: { bg: "rgba(226,75,74,.1)",  border: "rgba(226,75,74,.3)",  text: "#A32D2D" }, val: dic.confidentiality },
            ].map(({ letter, label, chip, val }) => (
              <div key={letter} style={{ display: "flex", alignItems: "center", gap: 10, padding: "7px 12px", background: "var(--surface-2)", borderRadius: 8 }}>
                <div style={{
                  width: 28, height: 28, borderRadius: 7, flexShrink: 0,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 13, fontWeight: 500, fontFamily: "var(--mono)",
                  background: chip.bg, border: `0.5px solid ${chip.border}`, color: chip.text,
                }}>{letter}</div>
                <span style={{ fontSize: 13, color: "var(--text-dim)", flex: 1 }}>{label}</span>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ fontSize: 15, fontWeight: 500, fontFamily: "var(--mono)", color: "var(--text)" }}>{val}</span>
                  <span style={{ fontSize: 10, color: "var(--text-faint)" }}>/5</span>
                  <div style={{ display: "flex", gap: 3 }}>
                    {[1,2,3,4,5].map(i => (
                      <div key={i} style={{ width: 8, height: 8, borderRadius: "50%", background: i <= val ? "#534AB7" : "var(--line)" }} />
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <Sep />

        {/* KPIs — 4 colonnes */}
        <div>
          <SectionLabel>KPIs Purple Team</SectionLabel>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 8 }}>
            {[
              { label: "Couverture ATT&CK", val: kpis.catalog_synced ? kpis.attack_coverage_pct : null,    unit: "%",   color: "#534AB7", noSync: !kpis.catalog_synced },
              { label: "Détection",         val: kpis.detection_coverage_pct, unit: "%",   color: "#1D9E75" },
              { label: "Réaction",          val: kpis.response_coverage_pct,  unit: "%",   color: "#EF9F27" },
              { label: "MTTD",              val: kpis.mttd_min,               unit: "min", color: "#534AB7" },
            ].map(({ label, val, unit, color, noSync }) => (
              <div key={label} style={{ background: "var(--surface-2)", borderRadius: 8, padding: "10px 12px" }}
                title={noSync ? "Importez le catalogue ATT&CK dans Paramètres pour obtenir ce KPI" : undefined}>
                <div style={{ fontSize: 10, color: "var(--text-faint)", marginBottom: 5 }}>{label}</div>
                <div style={{ display: "flex", alignItems: "baseline", gap: 3 }}>
                  <span style={{ fontSize: 20, fontWeight: 500, color: val == null ? "var(--text-faint)" : "var(--text)" }}>
                    {val ?? "—"}
                  </span>
                  {val != null && <span style={{ fontSize: 12, color: "var(--text-faint)" }}>{unit}</span>}
                  {noSync && <span style={{ fontSize: 9, color: "var(--text-faint)", marginLeft: 4, fontStyle: "italic" }}>catalogue requis</span>}
                </div>
                {val != null && unit === "%" && (
                  <div style={{ height: 3, borderRadius: 2, background: "var(--line)", marginTop: 7 }}>
                    <div style={{ height: "100%", width: `${val}%`, background: color, borderRadius: 2 }} />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        <Sep />

        {/* Couverture audit — blocs style screenshot */}
        <div>
          <SectionLabel>Couverture audit</SectionLabel>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 8 }}>
            {covItems.map(({ type, done }) => (
              <div key={type} style={{
                display: "flex", flexDirection: "column", alignItems: "center", gap: 5,
                padding: "10px 8px", borderRadius: 8,
                border: `0.5px solid ${done ? "rgba(29,158,117,.35)" : "var(--line)"}`,
                background: done ? "rgba(29,158,117,.1)" : "var(--surface-2)",
              }}>
                <div style={{
                  width: "100%", height: 8, borderRadius: 4,
                  background: done ? "#1D9E75" : "var(--line)",
                }} />
                <span style={{
                  fontSize: 10, fontWeight: 500, fontFamily: "var(--mono)", letterSpacing: ".04em",
                  color: done ? "#0F6E56" : "var(--text-faint)",
                }}>
                  {type}
                </span>
              </div>
            ))}
          </div>
        </div>

        <Sep />

        {/* Audits */}
        <div>
          <SectionLabel right={
            <span style={{ fontSize: 11, color: "var(--text-faint)" }}>
              {filteredAudits.length} résultat{filteredAudits.length > 1 ? "s" : ""}
            </span>
          }>Audits</SectionLabel>

          {/* Filtre statut */}
          <div style={{ display: "flex", gap: 5, flexWrap: "wrap", marginBottom: 10 }}>
            {/* Tous */}
            <Badge
              as="button"
              dot="var(--text-faint)"
              onClick={() => setAuditFilter("all")}
              extraStyle={{
                background: "var(--surface-2)", border: "0.5px solid var(--line)", color: "var(--text-faint)",
                opacity: auditFilter === "all" ? 1 : 0.35,
              }}
            >Tous</Badge>
            {/* Statuts présents */}
            {AUDIT_FILTER_ORDER.filter(s => audits.some(a => a.status === s)).map(s => {
              const st = AUDIT_STATUS_STYLE[s];
              return (
                <Badge
                  key={s}
                  as="button"
                  dot={st.dot}
                  onClick={() => setAuditFilter(auditFilter === s ? "all" : s)}
                  extraStyle={{
                    background: st.bg, border: `0.5px solid ${st.border}`, color: st.text,
                    opacity: auditFilter === s || auditFilter === "all" ? 1 : 0.35,
                  }}
                >{st.label}</Badge>
              );
            })}
          </div>

          {/* Liste */}
          <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
            {filteredAudits.length === 0 ? (
              <div style={{ fontSize: 12, color: "var(--text-faint)", textAlign: "center", padding: "12px 0" }}>
                Aucun audit avec ce statut.
              </div>
            ) : filteredAudits.map(audit => {
              const tc = AUDIT_TYPE_STYLE[audit.audit_type] || {};
              const st = AUDIT_STATUS_STYLE[audit.status]   || AUDIT_STATUS_STYLE["Draft"];
              return (
                <div key={audit.id} style={{
                  display: "flex", alignItems: "center", gap: 8,
                  padding: "9px 12px", background: "var(--surface-2)",
                  borderRadius: 8, border: "0.5px solid var(--line)",
                }}>
                  <span style={{
                    fontSize: 9, fontWeight: 500, fontFamily: "var(--mono)", padding: "2px 6px",
                    borderRadius: 4, flexShrink: 0,
                    background: tc.bg, border: `0.5px solid ${tc.border}`, color: tc.text,
                  }}>{audit.audit_type}</span>
                  <span style={{
                    fontSize: 13, fontWeight: 500, color: "var(--text)",
                    flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  }}>{audit.name}</span>
                  <Badge dot={st.dot} extraStyle={{ background: st.bg, border: `0.5px solid ${st.border}`, color: st.text }}>
                    {st.label}
                  </Badge>
                  <span style={{ fontSize: 11, color: "var(--text-faint)", flexShrink: 0 }}>
                    {fmtDate(audit.end_date || audit.start_date)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        <Sep />

        {/* Vulnérabilités */}
        <div>
          <SectionLabel right={
            <span style={{ fontSize: 11, color: "var(--text-faint)" }}>
              {filteredFindings.length} / {findings.length} résultat{filteredFindings.length > 1 ? "s" : ""}
            </span>
          }>Vulnérabilités</SectionLabel>

          {/* ── Double filtre : sévérité | séparateur | statut ── */}
          <div style={{ display: "flex", alignItems: "center", gap: 5, flexWrap: "wrap", marginBottom: 10 }}>
            {/* Tous */}
            <Badge
              as="button"
              dot="var(--text-faint)"
              onClick={() => { setSevFilter(null); setStFilter(null); }}
              extraStyle={{
                background: "var(--surface-2)", border: "0.5px solid var(--line)", color: "var(--text-faint)",
                opacity: !sevFilter && !stFilter ? 1 : 0.35,
              }}
            >Tous</Badge>

            {/* Sévérités présentes */}
            {SEV_ORDER.filter(sev => findings.some(f => f.severity === sev)).map(sev => {
              const s = SEVERITY_STYLE[sev];
              return (
                <Badge
                  key={sev}
                  as="button"
                  dot={s.dot}
                  onClick={() => toggleSev(sev)}
                  extraStyle={{
                    background: s.bg, border: `0.5px solid ${s.border}`, color: s.text,
                    opacity: !sevFilter || sevFilter === sev ? 1 : 0.35,
                  }}
                >{s.label}</Badge>
              );
            })}

            {/* Séparateur vertical */}
            <div style={{ width: 1, height: 16, background: "var(--line)", flexShrink: 0, alignSelf: "center" }} />

            {/* Statuts présents */}
            {FINDING_STATUS_ORDER.filter(st => findings.some(f => f.status === st)).map(st => {
              const s = FINDING_STATUS_STYLE[st];
              return (
                <Badge
                  key={st}
                  as="button"
                  dot={s.dot}
                  onClick={() => toggleSt(st)}
                  extraStyle={{
                    background: s.bg, border: `0.5px solid ${s.border}`, color: s.text,
                    opacity: !stFilter || stFilter === st ? 1 : 0.35,
                  }}
                >{s.label}</Badge>
              );
            })}
          </div>

          {/* Résumé sévérités */}
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>
            {SEV_ORDER.map(sev => {
              const count = findings.filter(f => f.severity === sev).length;
              if (count === 0) return null;
              const s = SEVERITY_STYLE[sev];
              return (
                <div key={sev} style={{
                  display: "inline-flex", flexDirection: "column", alignItems: "center",
                  gap: 2, padding: "6px 12px", minWidth: 54, borderRadius: 8,
                  background: s.bg, border: `0.5px solid ${s.border}`,
                  opacity: !sevFilter || sevFilter === sev ? 1 : 0.4,
                  transition: "opacity .12s",
                }}>
                  <span style={{ fontSize: 18, fontWeight: 500, fontFamily: "var(--mono)", color: s.text, lineHeight: 1 }}>{count}</span>
                  <span style={{ fontSize: 9, fontWeight: 500, letterSpacing: ".03em", color: s.text }}>{s.label}</span>
                </div>
              );
            })}
          </div>

          {/* Liste findings */}
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {filteredFindings.length === 0 ? (
              <div style={{ fontSize: 12, color: "var(--text-faint)", textAlign: "center", padding: "14px 0" }}>
                Aucune vulnérabilité avec ces filtres.
              </div>
            ) : filteredFindings.map(f => {
              const s  = SEVERITY_STYLE[f.severity]      || SEVERITY_STYLE["Info"];
              const fs = FINDING_STATUS_STYLE[f.status]  || FINDING_STATUS_STYLE["Open"];
              return (
                <div key={f.id} style={{
                  display: "flex", alignItems: "center", gap: 9,
                  padding: "8px 12px", background: "var(--surface-2)",
                  borderRadius: 8,
                  borderLeft: `3px solid ${s.bar}`,
                  borderTop: "0.5px solid var(--line)",
                  borderRight: "0.5px solid var(--line)",
                  borderBottom: "0.5px solid var(--line)",
                }}>
                  <span style={{
                    fontSize: 13, fontWeight: 500, color: "var(--text)",
                    flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  }}>{f.title}</span>
                  <Badge dot={fs.dot} extraStyle={{ background: fs.bg, border: `0.5px solid ${fs.border}`, color: fs.text }}>
                    {fs.label}
                  </Badge>
                </div>
              );
            })}
          </div>
        </div>

      </div>}
    </div>
  );
}
