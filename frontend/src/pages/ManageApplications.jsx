import { useEffect, useState } from "react";
import { api, ENUMS } from "../api/client";
import {
  Modal,
  Field,
  Input,
  NumberInput,
  Select,
  Textarea,
  ConfirmDialog,
  EmptyState,
} from "../components/Form";
import { CpePicker } from "../components/CpePicker";
import { DIC } from "../components/Shared";
import { useToast } from "../lib/useToast";

const EMPTY = {
  name: "",
  description: "",
  owner: "",
  team: "",
  email: "",
  phone: "",
  exposure: "Interne",
  technologies: "",
  technologies_cpe: "",
  url: "",
  scope_red_team: "",
  scope_pentest: "",
  dic_availability: 3,
  dic_integrity: 3,
  dic_confidentiality: 3,
};

// Définition des 4 types d'audit avec leur couleur
const AUDIT_TYPES = [
  { key: "BAS",         label: "BAS",    color: "#378ADD" },
  { key: "Pentest",     label: "PEN",    color: "#EF9F27" },
  { key: "Red Team",    label: "RED",    color: "#E24B4A" },
  { key: "Purple Team", label: "PUR",    color: "#534AB7" },
];

function CoverageBlocks({ coverage }) {
  if (!coverage) return <span className="faint" style={{ fontSize: 13 }}>—</span>;
  return (
    <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
      {AUDIT_TYPES.map(({ key, label, color }) => {
        const status = coverage[key]; // "done" | "in_progress" | null
        const filled  = status === "done";
        const ongoing = status === "in_progress";
        return (
          <div
            key={key}
            style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 3 }}
            title={
              filled  ? `${key} — réalisé` :
              ongoing ? `${key} — en cours` :
                        `${key} — jamais réalisé`
            }
          >
            <div style={{
              width: 22, height: 10, borderRadius: 3,
              background: filled ? color : ongoing ? color : "var(--line)",
              opacity: ongoing ? 0.5 : 1,
            }} />
            <span style={{
              fontSize: 9, fontFamily: "var(--mono)", fontWeight: 600,
              letterSpacing: "0.02em", textTransform: "uppercase",
              color: "var(--text-faint)",
            }}>{label}</span>
          </div>
        );
      })}
    </div>
  );
}

function CoverageLegend() {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap",
      padding: "8px 4px", marginBottom: 10,
    }}>
      <span style={{ fontSize: 11, color: "var(--text-faint)", fontWeight: 600,
        textTransform: "uppercase", letterSpacing: "0.08em", marginRight: 4 }}>
        Couverture :
      </span>
      {AUDIT_TYPES.map(({ key, label, color }) => (
        <span key={key} style={{ display: "inline-flex", alignItems: "center", gap: 5,
          fontSize: 12, color: "var(--text-dim)" }}>
          <span style={{ width: 14, height: 8, borderRadius: 2, background: color,
            display: "inline-block", flexShrink: 0 }} />
          {key}
        </span>
      ))}
      <span style={{ display: "inline-flex", alignItems: "center", gap: 5,
        fontSize: 12, color: "var(--text-faint)", marginLeft: 4 }}>
        <span style={{ width: 14, height: 8, borderRadius: 2, background: "var(--line)",
          display: "inline-block" }} />
        Non réalisé
      </span>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 5,
        fontSize: 12, color: "var(--text-faint)" }}>
        <span style={{ width: 14, height: 8, borderRadius: 2, background: "#378ADD",
          opacity: 0.5, display: "inline-block" }} />
        En cours
      </span>
    </div>
  );
}

export default function ManageApplications({ onSelectApp }) {
  const [items, setItems]     = useState(null);
  const [coverage, setCoverage] = useState({});
  const [editing, setEditing] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [err, setErr]         = useState(null);
  const { show, node }        = useToast();

  const load = () => {
    api.applications().then(setItems).catch(() => setItems([]));
    api.applicationsCoverage().then(setCoverage).catch(() => setCoverage({}));
  };
  useEffect(() => { load(); }, []);

  function openNew() {
    setErr(null);
    setEditing({ form: { ...EMPTY } });
  }
  function openEdit(a) {
    setErr(null);
    setEditing({ id: a.id, form: { ...EMPTY, ...a } });
  }
  const set = (k, v) =>
    setEditing((e) => ({ ...e, form: { ...e.form, [k]: v } }));

  async function save() {
    const f = editing.form;
    if (!f.name.trim()) { setErr("Le nom est obligatoire."); return; }
    try {
      if (editing.id) {
        await api.updateApplication(editing.id, f);
        show("Application mise à jour");
      } else {
        await api.createApplication(f);
        show("Application créée");
      }
      setEditing(null);
      load();
    } catch (e) { setErr(e.message); }
  }

  async function doDelete() {
    try {
      await api.deleteApplication(confirm.id);
      show("Application supprimée");
      setConfirm(null);
      load();
    } catch (e) { show(e.message, "err"); setConfirm(null); }
  }

  return (
    <>
      <div className="page-head">
        <div className="page-eyebrow">Module 1</div>
        <h1 className="page-title">Gestion des applications</h1>
        <p className="page-sub">
          Le référentiel central. Toutes les métriques sont calculées par application.
        </p>
      </div>

      <div className="toolbar">
        <button className="btn btn-primary" onClick={openNew}>+ Nouvelle application</button>
      </div>

      {items?.length === 0 ? (
        <EmptyState title="Aucune application" hint="Créez votre première application pour commencer." />
      ) : (
        <>
          <CoverageLegend />
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
                {items?.map((a) => (
                  <tr key={a.id}>
                    <td style={{ fontWeight: 600, cursor: "pointer" }}
                        onClick={() => onSelectApp && onSelectApp(a.id)}>
                      {a.name}
                    </td>
                    <td><span className="badge violet">{a.exposure}</span></td>
                    <td className="muted">{a.owner || "—"}</td>
                    <td>
                      <DIC dic={{ availability: a.dic_availability, integrity: a.dic_integrity, confidentiality: a.dic_confidentiality }} />
                    </td>
                    <td>
                      <CoverageBlocks coverage={coverage[a.id]} />
                    </td>
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
        </>
      )}

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
            <Input value={editing.form.name} onChange={(v) => set("name", v)} placeholder="ex. CRM Clients" />
          </Field>
          <Field label="Description">
            <Textarea value={editing.form.description} onChange={(v) => set("description", v)} />
          </Field>
          <div className="field-row">
            <Field label="Responsable">
              <Input value={editing.form.owner} onChange={(v) => set("owner", v)} />
            </Field>
            <Field label="Équipe">
              <Input value={editing.form.team} onChange={(v) => set("team", v)} />
            </Field>
          </div>
          <div className="field-row">
            <Field label="Email">
              <Input value={editing.form.email} onChange={(v) => set("email", v)} />
            </Field>
            <Field label="Téléphone">
              <Input value={editing.form.phone} onChange={(v) => set("phone", v)} />
            </Field>
          </div>
          <div className="field-row">
            <Field label="Exposition">
              <Select value={editing.form.exposure} onChange={(v) => set("exposure", v)} options={ENUMS.exposure} />
            </Field>
            <Field label="URL">
              <Input value={editing.form.url} onChange={(v) => set("url", v)} placeholder="https://…" />
            </Field>
          </div>
          <Field label="Technologies">
            <CpePicker
              valueRaw={editing.form.technologies_cpe}
              onChange={(raw, readable) => {
                setEditing((e) => ({
                  ...e,
                  form: { ...e.form, technologies_cpe: raw, technologies: readable },
                }));
              }}
            />
          </Field>
          <Field label="Criticité DIC (1 à 5)">
            <div className="field-row-3">
              <div>
                <span className="hint">Disponibilité</span>
                <NumberInput min={1} max={5} value={editing.form.dic_availability} onChange={(v) => set("dic_availability", v)} />
              </div>
              <div>
                <span className="hint">Intégrité</span>
                <NumberInput min={1} max={5} value={editing.form.dic_integrity} onChange={(v) => set("dic_integrity", v)} />
              </div>
              <div>
                <span className="hint">Confidentialité</span>
                <NumberInput min={1} max={5} value={editing.form.dic_confidentiality} onChange={(v) => set("dic_confidentiality", v)} />
              </div>
            </div>
          </Field>
          <div className="field-row">
            <Field label="Scope Red Team">
              <Textarea value={editing.form.scope_red_team} onChange={(v) => set("scope_red_team", v)} />
            </Field>
            <Field label="Scope Pentest">
              <Textarea value={editing.form.scope_pentest} onChange={(v) => set("scope_pentest", v)} />
            </Field>
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
