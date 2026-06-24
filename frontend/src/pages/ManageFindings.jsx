import { useEffect, useState } from "react";
import { api, ENUMS } from "../api/client";
import {
  Modal, Field, Input, NumberInput, Select, Textarea, ConfirmDialog, EmptyState,
} from "../components/Form";
import { RefGroup } from "../components/RefPicker";
import { parseRefValue, refToReadable } from "../lib/refData";
import { severityClass } from "../lib/format";
import { useToast } from "../lib/useToast";

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
  const { show, node } = useToast();

  const load = () => {
    api.findings(filterApp || undefined).then(setItems).catch(() => setItems([]));
    api.applications().then(setApps).catch(() => {});
    api.audits().then(setAudits).catch(() => {});
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [filterApp]);

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
