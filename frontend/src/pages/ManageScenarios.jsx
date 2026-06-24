import { useEffect, useState } from "react";
import { api, ENUMS } from "../api/client";
import {
  Modal, Field, Input, Textarea, SegmentedControl, ConfirmDialog, EmptyState,
} from "../components/Form";
import { useToast } from "../lib/useToast";

const EMPTY = {
  name: "", objective: "", threat_actor: "",
  engagement_type: "Pentest", sophistication: "Intermédiaire",
  references: "", description: "", ioc: "", ioa: "",
  steps: [],
};

// brouillon d'étape en cours d'ajout
const EMPTY_STEP = { tactic: "Initial Access", mitre_id: "", technique_name: "", action: "", description: "" };

export default function ManageScenarios() {
  const [items, setItems] = useState(null);
  const [editing, setEditing] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [draft, setDraft] = useState({ ...EMPTY_STEP });
  const [err, setErr] = useState(null);
  const { show, node } = useToast();

  const load = () => api.scenarios().then(setItems).catch(() => setItems([]));
  useEffect(() => { load(); }, []);

  function openNew() { setErr(null); setDraft({ ...EMPTY_STEP }); setEditing({ form: { ...EMPTY, steps: [] } }); }
  function openEdit(s) {
    setErr(null);
    setDraft({ ...EMPTY_STEP });
    setEditing({
      id: s.id,
      form: {
        name: s.name, objective: s.objective, threat_actor: s.threat_actor,
        engagement_type: s.engagement_type, sophistication: s.sophistication,
        references: s.references, description: s.description, ioc: s.ioc, ioa: s.ioa,
        steps: s.steps.map((st) => ({
          tactic: st.tactic, mitre_id: st.mitre_id, technique_name: st.technique_name,
          action: st.action, description: st.description,
        })),
      },
    });
  }
  const set = (k, v) => setEditing((e) => ({ ...e, form: { ...e.form, [k]: v } }));
  const setD = (k, v) => setDraft((d) => ({ ...d, [k]: v }));

  function addStep() {
    // technique_name peut contenir "T1190 description" : on parse l'id éventuel
    const raw = draft.mitre_id.trim();
    if (!raw && !draft.technique_name.trim()) return;
    const newStep = { ...draft, mitre_id: raw.toUpperCase() };
    set("steps", [...editing.form.steps, newStep]);
    setDraft({ ...EMPTY_STEP, tactic: draft.tactic });
  }
  function removeStep(i) {
    set("steps", editing.form.steps.filter((_, idx) => idx !== i));
  }

  async function save() {
    const f = editing.form;
    if (!f.name.trim()) { setErr("Le nom est obligatoire."); return; }
    const payload = {
      ...f,
      steps: f.steps.map((s, i) => ({ ...s, order: i + 1 })),
      technique_mitre_ids: [],
    };
    try {
      if (editing.id) { await api.updateScenario(editing.id, payload); show("Scénario mis à jour"); }
      else { await api.createScenario(payload); show("Scénario créé"); }
      setEditing(null); load();
    } catch (e) { setErr(e.message); }
  }

  async function doDelete() {
    try { await api.deleteScenario(confirm.id); show("Scénario supprimé"); setConfirm(null); load(); }
    catch (e) { show(e.message, "err"); setConfirm(null); }
  }

  const tacticLabel = (val) => (ENUMS.tactics.find((t) => t[0] === val) || [val, val])[1];

  return (
    <>
      <div className="page-head">
        <div className="page-eyebrow">Module 2 · CTI</div>
        <h1 className="page-title">Gestion des scénarios</h1>
        <p className="page-sub">
          Chaînes d'étapes mappées MITRE ATT&CK, réutilisables lors de la
          planification d'un audit.
        </p>
      </div>

      <div className="toolbar">
        <button className="btn btn-primary" onClick={openNew}>+ Nouveau scénario</button>
      </div>

      {items?.length === 0 ? (
        <EmptyState title="Aucun scénario" hint="Créez un scénario de menace pour le rejouer en audit." />
      ) : (
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>Scénario</th><th>Adversaire</th><th>Engagement</th>
                <th>Étapes</th><th style={{ textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {!items && <tr><td colSpan={5} className="faint">Chargement…</td></tr>}
              {items?.map((s) => (
                <tr key={s.id}>
                  <td style={{ fontWeight: 600 }}>
                    {s.name}
                    {s.objective && <div className="faint" style={{ fontSize: 12, fontWeight: 400, marginTop: 3 }}>{s.objective}</div>}
                  </td>
                  <td><span className="badge violet">{s.threat_actor || "—"}</span></td>
                  <td className="muted" style={{ fontSize: 13 }}>{s.engagement_type}</td>
                  <td className="wrap" style={{ maxWidth: 280 }}>
                    {s.steps.length
                      ? s.steps.map((st, i) => <span className="ttp" key={i} title={st.technique_name}>{st.mitre_id || "—"}</span>)
                      : <span className="faint">—</span>}
                  </td>
                  <td>
                    <div className="row-actions">
                      <button className="icon-btn" title="Modifier" onClick={() => openEdit(s)}>✎</button>
                      <button className="icon-btn danger" title="Supprimer" onClick={() => setConfirm(s)}>🗑</button>
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
          title={editing.id ? "Modifier le scénario d'attaque" : "Nouveau scénario d'attaque"}
          onClose={() => setEditing(null)}
          error={err}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setEditing(null)}>Annuler</button>
              <button className="btn btn-primary" onClick={save}>
                {editing.id ? "Enregistrer" : "Créer le scénario"}
              </button>
            </>
          }
        >
          <p className="faint" style={{ fontSize: 13, marginTop: -12, marginBottom: 18 }}>
            Chaîne d'étapes mappées MITRE ATT&CK · réutilisable lors de la planification d'un audit
          </p>

          <Field label="Nom du scénario *">
            <Input value={editing.form.name} onChange={(v) => set("name", v)}
              placeholder="ex. Intrusion externe → exfiltration de données" />
          </Field>

          <div className="field-row">
            <Field label="Objectif visé">
              <Input value={editing.form.objective} onChange={(v) => set("objective", v)}
                placeholder="ex. Démontrer le vol de la base clients" />
            </Field>
            <Field label="Adversaire émulé">
              <Input value={editing.form.threat_actor} onChange={(v) => set("threat_actor", v)}
                placeholder="ex. Affilié ransomware" />
            </Field>
          </div>

          <div className="field-row">
            <Field label="Type d'engagement">
              <SegmentedControl value={editing.form.engagement_type}
                onChange={(v) => set("engagement_type", v)} options={ENUMS.auditType} />
            </Field>
            <Field label="Sophistication">
              <SegmentedControl value={editing.form.sophistication}
                onChange={(v) => set("sophistication", v)} options={ENUMS.sophistication} />
            </Field>
          </div>

          {/* Kill-chain */}
          <div className="lbl" style={{ marginTop: 6, marginBottom: 8 }}>
            Étapes de la kill-chain · {editing.form.steps.length}
          </div>

          {editing.form.steps.length > 0 && (
            <div className="step-list">
              {editing.form.steps.map((st, i) => (
                <div className="step-item" key={i}>
                  <span className="step-idx">{i + 1}</span>
                  <div className="step-content">
                    <div className="flex gap-sm center wrap">
                      <span className="kc-tactic">{tacticLabel(st.tactic)}</span>
                      {st.mitre_id && <span className="ttp">{st.mitre_id}</span>}
                      {st.technique_name && <span className="muted" style={{ fontSize: 13 }}>{st.technique_name}</span>}
                    </div>
                    {st.action && <div className="kc-cmd" style={{ marginTop: 6 }}><span className="kc-prompt">$</span> {st.action}</div>}
                    {st.description && <div className="kc-desc">{st.description}</div>}
                  </div>
                  <button className="icon-btn danger" title="Retirer" onClick={() => removeStep(i)}>🗑</button>
                </div>
              ))}
            </div>
          )}

          {/* Ajout d'une étape */}
          <div className="step-builder">
            <div className="tactic-picker">
              {ENUMS.tactics.map(([val, label]) => (
                <button key={val} type="button"
                  className={`tactic-chip ${draft.tactic === val ? "sel" : ""}`}
                  onClick={() => setD("tactic", val)}>
                  {label}
                </button>
              ))}
            </div>
            <Input mono value={draft.mitre_id} onChange={(v) => setD("mitre_id", v)}
              placeholder="Technique MITRE · ID (T1190)" />
            <div style={{ height: 8 }} />
            <Input mono value={draft.technique_name} onChange={(v) => setD("technique_name", v)}
              placeholder="Nom de la technique (ex. Exploit Public-Facing Application)" />
            <div style={{ height: 8 }} />
            <Input mono value={draft.action} onChange={(v) => setD("action", v)}
              placeholder="Action · commande système ou outil (ex. nmap -sV, mimikatz)" />
            <div style={{ height: 8 }} />
            <Textarea value={draft.description} onChange={(v) => setD("description", v)}
              placeholder="Description de l'action et résultat attendu / observable…" />
            <button className="btn btn-ghost btn-sm" style={{ marginTop: 10 }}
              onClick={addStep}
              disabled={!draft.mitre_id.trim() && !draft.technique_name.trim()}>
              + Ajouter l'étape
            </button>
          </div>

          <Field label="Références" hint="Conservé : liens MITRE, rapports CTI…">
            <Input value={editing.form.references} onChange={(v) => set("references", v)}
              placeholder="https://attack.mitre.org/…" />
          </Field>
        </Modal>
      )}

      {confirm && (
        <ConfirmDialog
          message={`Supprimer le scénario « ${confirm.name} » ?`}
          onConfirm={doDelete}
          onCancel={() => setConfirm(null)}
        />
      )}
      {node}
    </>
  );
}
