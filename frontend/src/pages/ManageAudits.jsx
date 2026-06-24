import { useEffect, useState } from "react";
import { api, ENUMS } from "../api/client";
import {
  Modal, Field, Input, Select, Textarea, ChipPicker, ConfirmDialog, EmptyState,
} from "../components/Form";
import { useToast } from "../lib/useToast";

const EMPTY = {
  name: "", audit_type: "Purple Team", status: "Draft",
  application_id: null, team: "", results: "", scenario_ids: [],
  start_date: "", end_date: "",
};

export default function ManageAudits({ onSelectApp, onOpenAudit }) {
  const [items, setItems] = useState(null);
  const [apps, setApps] = useState([]);
  const [scenarios, setScenarios] = useState([]);
  const [editing, setEditing] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [err, setErr] = useState(null);
  const { show, node } = useToast();

  const load = () => {
    api.audits().then(setItems).catch(() => setItems([]));
    api.applications().then(setApps).catch(() => {});
    api.scenarios().then(setScenarios).catch(() => {});
  };
  useEffect(() => { load(); }, []);

  const appName = (id) => apps.find((a) => a.id === id)?.name || "—";

  function openNew() {
    setErr(null);
    setEditing({ form: { ...EMPTY, application_id: apps[0]?.id ?? null } });
  }
  function openEdit(a) {
    setErr(null);
    setEditing({
      id: a.id,
      form: {
        name: a.name, audit_type: a.audit_type, status: a.status,
        application_id: a.application_id, team: a.team, results: a.results,
        scenario_ids: a.scenarios.map((s) => s.id),
        start_date: a.start_date ? a.start_date.slice(0, 10) : "",
        end_date: a.end_date ? a.end_date.slice(0, 10) : "",
      },
    });
  }
  const set = (k, v) => setEditing((e) => ({ ...e, form: { ...e.form, [k]: v } }));

  function toggleScenario(id) {
    const cur = editing.form.scenario_ids;
    set("scenario_ids", cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]);
  }

  async function save() {
    const f = editing.form;
    if (!f.name.trim()) { setErr("Le nom est obligatoire."); return; }
    if (!f.application_id) { setErr("Sélectionnez une application."); return; }
    // normalise les dates vides en null
    const payload = {
      ...f,
      start_date: f.start_date ? f.start_date : null,
      end_date: f.end_date ? f.end_date : null,
    };
    try {
      let audit;
      if (editing.id) { audit = await api.updateAudit(editing.id, payload); show("Audit mis à jour"); }
      else { audit = await api.createAudit(payload); show("Audit créé"); }
      // Génère les évaluations pour les techniques des scénarios choisis
      if (f.scenario_ids.length) await api.populateAudit(audit.id);
      setEditing(null); load();
    } catch (e) { setErr(e.message); }
  }

  async function doDelete() {
    try { await api.deleteAudit(confirm.id); show("Audit supprimé"); setConfirm(null); load(); }
    catch (e) { show(e.message, "err"); setConfirm(null); }
  }

  return (
    <>
      <div className="page-head">
        <div className="page-eyebrow">Module 3</div>
        <h1 className="page-title">Gestion des audits</h1>
        <p className="page-sub">
          Chaque audit relie une application à des scénarios CTI. À la
          sauvegarde, les techniques à évaluer sont générées automatiquement.
        </p>
      </div>

      <div className="toolbar">
        <button className="btn btn-primary" onClick={openNew} disabled={apps.length === 0}>
          + Nouvel audit
        </button>
      </div>

      {apps.length === 0 ? (
        <EmptyState title="Aucune application" hint="Créez d'abord une application avant de lancer un audit." />
      ) : items?.length === 0 ? (
        <EmptyState title="Aucun audit" hint="Créez votre premier audit Purple Team." />
      ) : (
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>Audit</th><th>Type</th><th>Statut</th>
                <th>Application</th><th>Scénarios</th>
                <th style={{ textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {!items && <tr><td colSpan={6} className="faint">Chargement…</td></tr>}
              {items?.map((a) => (
                <tr key={a.id} className="clickable" onClick={() => onOpenAudit && onOpenAudit(a.id)}>
                  <td style={{ fontWeight: 600 }}>{a.name}</td>
                  <td><span className="badge violet">{a.audit_type}</span></td>
                  <td className="muted" style={{ fontSize: 13 }}>{a.status}</td>
                  <td className="muted" style={{ fontSize: 13 }}>
                    {appName(a.application_id)}
                  </td>
                  <td className="faint" style={{ fontSize: 12 }}>
                    {a.scenarios.map((s) => s.threat_actor || s.name).join(", ") || "—"}
                  </td>
                  <td onClick={(e) => e.stopPropagation()}>
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

      {editing && (
        <Modal
          title={editing.id ? "Modifier l'audit" : "Nouvel audit"}
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
            <Input value={editing.form.name} onChange={(v) => set("name", v)} placeholder="ex. Purple Team CRM — APT29 Q2" />
          </Field>
          <div className="field-row">
            <Field label="Type">
              <Select value={editing.form.audit_type} onChange={(v) => set("audit_type", v)} options={ENUMS.auditType} />
            </Field>
            <Field label="Statut">
              <Select value={editing.form.status} onChange={(v) => set("status", v)} options={ENUMS.auditStatus} />
            </Field>
          </div>
          <div className="field-row">
            <Field label="Application *" hint="Application cible de l'audit">
              <select className="select"
                value={editing.form.application_id ?? ""}
                onChange={(e) => set("application_id", Number(e.target.value))}>
                {apps.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
              </select>
            </Field>
            <Field label="Équipe">
              <Input value={editing.form.team} onChange={(v) => set("team", v)} />
            </Field>
          </div>
          <div className="field-row">
            <Field label="Date de début (jalon)">
              <input type="date" className="input"
                value={editing.form.start_date}
                onChange={(e) => set("start_date", e.target.value)} />
            </Field>
            <Field label="Date de fin (jalon)" hint="Laisser vide si mission en cours">
              <input type="date" className="input"
                value={editing.form.end_date}
                onChange={(e) => set("end_date", e.target.value)} />
            </Field>
          </div>
          <Field label="Scénarios CTI" hint="Les techniques de ces scénarios seront générées pour évaluation">
            {scenarios.length === 0
              ? <span className="faint" style={{ fontSize: 13 }}>Aucun scénario disponible.</span>
              : <ChipPicker
                  items={scenarios.map((s) => ({ value: s.id, label: s.threat_actor || s.name, title: s.name }))}
                  selected={editing.form.scenario_ids}
                  onToggle={toggleScenario}
                />}
          </Field>
          <Field label="Résultats / notes">
            <Textarea value={editing.form.results} onChange={(v) => set("results", v)} />
          </Field>
        </Modal>
      )}

      {confirm && (
        <ConfirmDialog
          message={`Supprimer l'audit « ${confirm.name} » et ses évaluations ?`}
          onConfirm={doDelete}
          onCancel={() => setConfirm(null)}
        />
      )}
      {node}
    </>
  );
}
