import { useEffect, useState } from "react";
import { api, ENUMS } from "../api/client";
import {
  Modal, Field, Input, NumberInput, Select, Textarea, ConfirmDialog, EmptyState,
} from "../components/Form";
import { severityClass } from "../lib/format";
import { useToast } from "../lib/useToast";

const EMPTY = {
  title: "", description: "", impact: "", cvss: 0, severity: "Medium",
  status: "Open", owasp: "", cwe: "", capec: "",
  application_id: null, audit_id: null,
};

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
    setEditing({ id: f.id, form: { ...EMPTY, ...f } });
  }
  const set = (k, v) => setEditing((e) => ({ ...e, form: { ...e.form, [k]: v } }));

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

  // audits filtrés sur l'application choisie dans le formulaire
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
                    {[f.owasp, f.cwe, f.capec].filter(Boolean).map((m) => <span className="ttp" key={m}>{m}</span>) || "—"}
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
          <div className="field-row-3">
            <Field label="OWASP"><Input mono value={editing.form.owasp} onChange={(v) => set("owasp", v)} placeholder="A03" /></Field>
            <Field label="CWE"><Input mono value={editing.form.cwe} onChange={(v) => set("cwe", v)} placeholder="CWE-89" /></Field>
            <Field label="CAPEC"><Input mono value={editing.form.capec} onChange={(v) => set("capec", v)} placeholder="CAPEC-66" /></Field>
          </div>
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
