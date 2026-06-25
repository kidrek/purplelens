import { useEffect, useState } from "react";
import { api, ENUMS } from "../api/client";
import { Modal, Field, Input, NumberInput, Select, Textarea } from "./Form";
import { RefGroup } from "./RefPicker";
import { parseRefValue, refToReadable } from "../lib/refData";
import { severityClass } from "../lib/format";
import { useToast } from "../lib/useToast";

/**
 * FindingDrawerContent — contenu complet d'une vulnérabilité, utilisable dans un Drawer.
 *
 * Props :
 *   finding   {object}  — objet finding déjà chargé (depuis la liste parente)
 *   onClose   {fn}      — ferme le drawer
 *   onUpdated {fn}      — callback après modification (reload parent)
 */
export function FindingDrawerContent({ finding: initialFinding, onClose, onUpdated }) {
  const [finding, setFinding]   = useState(initialFinding);
  const [apps, setApps]         = useState([]);
  const [audits, setAudits]     = useState([]);
  const [editing, setEditing]   = useState(null);
  const [err, setErr]           = useState(null);
  const { show, node }          = useToast();

  useEffect(() => {
    setFinding(initialFinding);
  }, [initialFinding]);

  useEffect(() => {
    api.applications().then(setApps).catch(() => {});
    api.audits().then(setAudits).catch(() => {});
  }, []);

  const appName  = (id) => apps.find((a) => a.id === id)?.name || "—";
  const auditName = (id) => id ? (audits.find((a) => a.id === id)?.name || "—") : "—";

  // Refs structurées (JSON) ou fallback legacy
  const owaspRefs = parseRefValue(finding.owasp_refs);
  const cweRefs   = parseRefValue(finding.cwe_refs);
  const capecRefs = parseRefValue(finding.capec_refs);

  function openEdit() {
    setErr(null);
    setEditing({
      ...finding,
      owasp_refs: finding.owasp_refs || "",
      cwe_refs:   finding.cwe_refs   || "",
      capec_refs: finding.capec_refs  || "",
    });
  }
  const setF = (k, v) => setEditing((e) => ({ ...e, [k]: v }));

  function handleRefChange(refs, readables) {
    setEditing((e) => ({
      ...e,
      owasp_refs: refs.owasp, cwe_refs: refs.cwe, capec_refs: refs.capec,
      owasp: readables.owasp, cwe: readables.cwe, capec: readables.capec,
    }));
  }

  async function save() {
    if (!editing.title.trim()) { setErr("Le titre est obligatoire."); return; }
    try {
      const updated = await api.updateFinding(finding.id, {
        ...editing, audit_id: editing.audit_id || null,
      });
      setFinding({ ...finding, ...editing });
      setEditing(null);
      show("Vulnérabilité mise à jour");
      onUpdated?.();
    } catch (e) { setErr(e.message); }
  }

  // Couleur CVSS
  const cvssColor = finding.cvss >= 9 ? "#E24B4A"
    : finding.cvss >= 7 ? "#EF9F27"
    : finding.cvss >= 4 ? "#1D9E75"
    : "var(--text-dim)";

  return (
    <>
      {/* En-tête */}
      <div className="drawer-content-head">
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="page-eyebrow">Vulnérabilité #{finding.id}</div>
          <h2 className="drawer-content-title" style={{ wordBreak: "break-word" }}>
            {finding.title}
          </h2>
        </div>
        <button className="btn btn-primary btn-sm" onClick={openEdit}>Éditer</button>
      </div>

      {/* Méta rapide */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 20 }}>
        <span className={`badge ${severityClass(finding.severity)}`}>{finding.severity}</span>
        <span className="badge" style={{
          fontFamily: "var(--mono)", fontSize: 11, padding: "2px 8px", borderRadius: 5,
          fontWeight: 600, background: "var(--surface-2)", border: "1px solid var(--line)",
          color: cvssColor,
        }}>CVSS {finding.cvss.toFixed(1)}</span>
        <span className="badge" style={{
          fontSize: 11, padding: "2px 8px", borderRadius: 5, fontWeight: 500,
          background: "var(--surface-2)", border: "1px solid var(--line)", color: "var(--text-dim)",
        }}>{finding.status}</span>
      </div>

      {/* CVSS bar */}
      <div style={{ height: 4, background: "var(--line)", borderRadius: 2, marginBottom: 20, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${Math.min(finding.cvss * 10, 100)}%`, background: cvssColor, borderRadius: 2 }} />
      </div>

      {/* Description & Impact */}
      {finding.description && (
        <div className="card" style={{ marginBottom: 14 }}>
          <span className="card-label">Description</span>
          <p style={{ fontSize: 14, lineHeight: 1.6, marginTop: 8, color: "var(--text)" }}>
            {finding.description}
          </p>
        </div>
      )}
      {finding.impact && (
        <div className="card" style={{ marginBottom: 14 }}>
          <span className="card-label">Impact</span>
          <p style={{ fontSize: 14, lineHeight: 1.6, marginTop: 8, color: "var(--text)" }}>
            {finding.impact}
          </p>
        </div>
      )}

      {/* Références OWASP / CWE / CAPEC */}
      {(owaspRefs.length > 0 || cweRefs.length > 0 || capecRefs.length > 0 ||
        finding.owasp || finding.cwe || finding.capec) && (
        <div className="card" style={{ marginBottom: 14 }}>
          <span className="card-label">Références de sécurité</span>
          <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 8 }}>
            {/* OWASP */}
            {owaspRefs.length > 0 && (
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                <span style={{
                  fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".08em",
                  color: "#854F0B", background: "#FAEEDA", border: "1px solid rgba(239,159,39,.4)",
                  borderRadius: 4, padding: "2px 6px", flexShrink: 0,
                }}>OWASP</span>
                {owaspRefs.map(r => (
                  <span key={r.ref_id} className="ref-chip ref-chip-owasp" title={r.name}>
                    <span className="ref-chip-id">{r.ref_id}</span>
                    <span className="ref-chip-name">{r.name}</span>
                  </span>
                ))}
              </div>
            )}
            {/* CWE */}
            {cweRefs.length > 0 && (
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                <span style={{
                  fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".08em",
                  color: "#0F6E56", background: "#E1F5EE", border: "1px solid rgba(93,202,165,.4)",
                  borderRadius: 4, padding: "2px 6px", flexShrink: 0,
                }}>CWE</span>
                {cweRefs.map(r => (
                  <span key={r.ref_id} className="ref-chip ref-chip-cwe" title={r.name}>
                    <span className="ref-chip-id">{r.ref_id}</span>
                    <span className="ref-chip-name">{r.name}</span>
                  </span>
                ))}
              </div>
            )}
            {/* CAPEC */}
            {capecRefs.length > 0 && (
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                <span style={{
                  fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".08em",
                  color: "#534AB7", background: "#EEEDFE", border: "1px solid rgba(83,74,183,.4)",
                  borderRadius: 4, padding: "2px 6px", flexShrink: 0,
                }}>CAPEC</span>
                {capecRefs.map(r => (
                  <span key={r.ref_id} className="ref-chip ref-chip-capec" title={r.name}>
                    <span className="ref-chip-id">{r.ref_id}</span>
                    <span className="ref-chip-name">{r.name}</span>
                  </span>
                ))}
              </div>
            )}
            {/* Fallback legacy */}
            {owaspRefs.length === 0 && cweRefs.length === 0 && capecRefs.length === 0 && (
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {[finding.owasp, finding.cwe, finding.capec].filter(Boolean).map(m => (
                  <span className="ttp" key={m}>{m}</span>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Contexte */}
      <div className="card" style={{ marginBottom: 20 }}>
        <span className="card-label">Contexte</span>
        <div className="meta-grid" style={{ marginTop: 12 }}>
          <div className="meta-item">
            <span className="meta-label">Application</span>
            <span className="meta-value">{appName(finding.application_id)}</span>
          </div>
          <div className="meta-item">
            <span className="meta-label">Audit rattaché</span>
            <span className="meta-value">{auditName(finding.audit_id)}</span>
          </div>
        </div>
      </div>

      {/* Modale d'édition */}
      {editing && (
        <Modal
          title="Modifier la vulnérabilité"
          onClose={() => setEditing(null)}
          error={err}
          footer={<>
            <button className="btn btn-ghost" onClick={() => setEditing(null)}>Annuler</button>
            <button className="btn btn-primary" onClick={save}>Enregistrer</button>
          </>}
        >
          <Field label="Titre *">
            <Input value={editing.title} onChange={(v) => setF("title", v)} />
          </Field>
          <Field label="Description">
            <Textarea value={editing.description} onChange={(v) => setF("description", v)} />
          </Field>
          <Field label="Impact">
            <Textarea value={editing.impact} onChange={(v) => setF("impact", v)} />
          </Field>
          <div className="field-row-3">
            <Field label="Sévérité">
              <Select value={editing.severity} onChange={(v) => setF("severity", v)} options={ENUMS.severity} />
            </Field>
            <Field label="CVSS">
              <NumberInput min={0} max={10} step={0.1} value={editing.cvss} onChange={(v) => setF("cvss", v ?? 0)} />
            </Field>
            <Field label="Statut">
              <Select value={editing.status} onChange={(v) => setF("status", v)} options={ENUMS.findingStatus} />
            </Field>
          </div>
          <Field label="Références de sécurité">
            <RefGroup
              values={{ owasp: editing.owasp_refs || "", cwe: editing.cwe_refs || "", capec: editing.capec_refs || "" }}
              onChange={handleRefChange}
            />
          </Field>
          <Field label="Audit rattaché (optionnel)">
            <select className="select"
              value={editing.audit_id ?? ""}
              onChange={(e) => setF("audit_id", e.target.value ? Number(e.target.value) : null)}>
              <option value="">Aucun</option>
              {audits.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
          </Field>
        </Modal>
      )}
      {node}
    </>
  );
}
