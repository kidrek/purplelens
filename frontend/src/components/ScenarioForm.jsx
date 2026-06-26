import { useState } from "react";
import { api, ENUMS } from "../api/client";
import { Field, Input, Textarea, SegmentedControl } from "./Form";
import { useToast } from "../lib/useToast";

const EMPTY = {
  name: "", objective: "", threat_actor: "",
  engagement_type: "Pentest", sophistication: "Intermédiaire",
  references: "", description: "", ioc: "", ioa: "",
  steps: [],
};
const EMPTY_STEP = {
  tactic: "Initial Access", mitre_id: "",
  technique_name: "", action: "", description: "",
};

/**
 * ScenarioForm — formulaire complet création/édition d'un scénario.
 * Conçu pour s'afficher dans un Drawer ou une Modal.
 *
 * Props :
 *   initial    {object|null}  — valeurs initiales (null = création)
 *   scenarioId {number|null}  — id si édition, null si création
 *   onSaved    {fn}           — callback(updatedOrCreated) après succès
 *   onCancel   {fn}           — callback annulation
 */
export function ScenarioForm({ initial = null, scenarioId = null, onSaved, onCancel }) {
  const isEdit = !!scenarioId;

  const [form, setForm]   = useState(initial ?? { ...EMPTY });
  const [draft, setDraft] = useState({ ...EMPTY_STEP });
  const [err, setErr]     = useState(null);
  const [saving, setSaving] = useState(false);
  const { show, node }    = useToast();

  const set  = (k, v) => setForm(f => ({ ...f, [k]: v }));
  const setD = (k, v) => setDraft(d => ({ ...d, [k]: v }));

  const tacticLabel = (val) =>
    (ENUMS.tactics.find(t => t[0] === val) || [val, val])[1];

  function addStep() {
    const raw = draft.mitre_id.trim();
    if (!raw && !draft.technique_name.trim()) return;
    set("steps", [...form.steps, { ...draft, mitre_id: raw.toUpperCase() }]);
    setDraft({ ...EMPTY_STEP, tactic: draft.tactic });
  }

  function removeStep(i) {
    set("steps", form.steps.filter((_, idx) => idx !== i));
  }

  async function save() {
    if (!form.name.trim()) { setErr("Le nom est obligatoire."); return; }
    setErr(null);
    setSaving(true);
    const payload = {
      ...form,
      steps: form.steps.map((s, i) => ({ ...s, order: i + 1 })),
      technique_mitre_ids: [],
    };
    try {
      const result = isEdit
        ? await api.updateScenario(scenarioId, payload)
        : await api.createScenario(payload);
      show(isEdit ? "Scénario mis à jour" : "Scénario créé");
      onSaved?.(result);
    } catch (e) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="scenario-form">
      {/* En-tête */}
      <div className="drawer-content-head">
        <div>
          <div className="page-eyebrow">{isEdit ? `Scénario #${scenarioId}` : "Nouveau scénario"}</div>
          <h2 className="drawer-content-title">
            {isEdit ? "Modifier le scénario" : "Nouveau scénario d'attaque"}
          </h2>
        </div>
      </div>

      <p className="faint" style={{ fontSize: 13, marginBottom: 20 }}>
        Chaîne d'étapes mappées MITRE ATT&CK · réutilisable lors de la planification d'un audit.
      </p>

      {err && (
        <div className="modal-err" style={{ marginBottom: 14 }}>{err}</div>
      )}

      <Field label="Nom du scénario *">
        <Input value={form.name} onChange={v => set("name", v)}
          placeholder="ex. Intrusion externe → exfiltration de données" />
      </Field>

      <div className="field-row">
        <Field label="Objectif visé">
          <Input value={form.objective} onChange={v => set("objective", v)}
            placeholder="ex. Démontrer le vol de la base clients" />
        </Field>
        <Field label="Adversaire émulé">
          <Input value={form.threat_actor} onChange={v => set("threat_actor", v)}
            placeholder="ex. APT29, Affilié ransomware" />
        </Field>
      </div>

      <div className="field-row">
        <Field label="Type d'engagement">
          <SegmentedControl value={form.engagement_type}
            onChange={v => set("engagement_type", v)} options={ENUMS.auditType} />
        </Field>
        <Field label="Sophistication">
          <SegmentedControl value={form.sophistication}
            onChange={v => set("sophistication", v)} options={ENUMS.sophistication} />
        </Field>
      </div>

      {/* Kill-chain */}
      <div className="lbl" style={{ marginTop: 6, marginBottom: 8 }}>
        Étapes de la kill-chain · {form.steps.length}
      </div>

      {form.steps.length > 0 && (
        <div className="step-list">
          {form.steps.map((st, i) => (
            <div className="step-item" key={i}>
              <span className="step-idx">{i + 1}</span>
              <div className="step-content">
                <div className="flex gap-sm center wrap">
                  <span className="kc-tactic">{tacticLabel(st.tactic)}</span>
                  {st.mitre_id && <span className="ttp">{st.mitre_id}</span>}
                  {st.technique_name && (
                    <span className="muted" style={{ fontSize: 13 }}>{st.technique_name}</span>
                  )}
                </div>
                {st.action && (
                  <div className="kc-cmd" style={{ marginTop: 6 }}>
                    <span className="kc-prompt">$</span> {st.action}
                  </div>
                )}
                {st.description && <div className="kc-desc">{st.description}</div>}
              </div>
              <button className="icon-btn danger" onClick={() => removeStep(i)}>🗑</button>
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
        <Input mono value={draft.mitre_id} onChange={v => setD("mitre_id", v)}
          placeholder="Technique MITRE · ID (T1190)" />
        <div style={{ height: 8 }} />
        <Input mono value={draft.technique_name} onChange={v => setD("technique_name", v)}
          placeholder="Nom de la technique (ex. Exploit Public-Facing Application)" />
        <div style={{ height: 8 }} />
        <Input mono value={draft.action} onChange={v => setD("action", v)}
          placeholder="Action · commande système ou outil (ex. nmap -sV, mimikatz)" />
        <div style={{ height: 8 }} />
        <Textarea value={draft.description} onChange={v => setD("description", v)}
          placeholder="Description de l'action et résultat attendu / observable…" />
        <button className="btn btn-ghost btn-sm" style={{ marginTop: 10 }}
          onClick={addStep}
          disabled={!draft.mitre_id.trim() && !draft.technique_name.trim()}>
          + Ajouter l'étape
        </button>
      </div>

      <Field label="Description générale">
        <Textarea value={form.description} onChange={v => set("description", v)}
          placeholder="Contexte, objectif global du scénario…" />
      </Field>

      <div className="field-row">
        <Field label="IOC" hint="Indicateurs de compromission">
          <Textarea value={form.ioc} onChange={v => set("ioc", v)}
            placeholder="Hash, IP, domaine…" />
        </Field>
        <Field label="IOA" hint="Indicateurs d'attaque">
          <Textarea value={form.ioa} onChange={v => set("ioa", v)}
            placeholder="Comportements, patterns…" />
        </Field>
      </div>

      <Field label="Références" hint="Liens MITRE, rapports CTI…">
        <Input value={form.references} onChange={v => set("references", v)}
          placeholder="https://attack.mitre.org/…" />
      </Field>

      {/* Actions */}
      <div style={{
        display: "flex", justifyContent: "flex-end", gap: 10,
        marginTop: 24, paddingTop: 18, borderTop: "1px solid var(--line)",
      }}>
        <button className="btn btn-ghost" onClick={onCancel} disabled={saving}>
          Annuler
        </button>
        <button className="btn btn-primary" onClick={save} disabled={saving}>
          {saving ? "Enregistrement…" : isEdit ? "Enregistrer" : "Créer le scénario"}
        </button>
      </div>

      {node}
    </div>
  );
}
