import { useState } from "react";
import { api, ENUMS } from "../api/client";
import { Field, Input, Textarea, SegmentedControl } from "./Form";
import { MitreTechniquePicker } from "./MitreTechniquePicker";
import { D3fendAccordion } from "./D3fendAccordion";
import { MitreMatrix } from "./MitreMatrix";
import { useToast } from "../lib/useToast";
import { attackUrl } from "../lib/d3fendData";

const EMPTY = {
  name: "", objective: "", threat_actor: "",
  engagement_type: "Pentest", sophistication: "Intermédiaire",
  references: "", description: "", ioc: "", ioa: "",
  steps: [],
};
const EMPTY_STEP = {
  tactic: "", mitre_id: "", technique_name: "", action: "", description: "",
};

/**
 * Bouton ⓘ ouvrant une page MITRE dans un nouvel onglet.
 * variant : "atk" (rouge) | "d3f" (vert)
 */
function InfoBtn({ href, title, variant = "atk" }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={`mitre-info-btn mitre-info-btn-${variant}`}
      title={title}
      onClick={e => e.stopPropagation()}
      aria-label={title}
    >
      ⓘ
    </a>
  );
}

/**
 * ScenarioForm — formulaire complet création/édition.
 * Utilisé dans un Drawer pour la création et l'édition.
 *
 * Props :
 *   initial    {object|null}  — valeurs initiales (null = création)
 *   scenarioId {number|null}  — id si édition, null si création
 *   onSaved    {fn}           — callback après succès
 *   onCancel   {fn}           — callback annulation
 */
export function ScenarioForm({ initial = null, scenarioId = null, onSaved, onCancel }) {
  const isEdit = !!scenarioId;

  const [form, setForm]         = useState(initial ?? { ...EMPTY });
  const [draft, setDraft]       = useState({ ...EMPTY_STEP });
  const [selectedTech, setSelectedTech] = useState(null);
  const [err, setErr]           = useState(null);
  const [saving, setSaving]     = useState(false);
  const { show, node }          = useToast();

  const set  = (k, v) => setForm(f => ({ ...f, [k]: v }));
  const setD = (k, v) => setDraft(d => ({ ...d, [k]: v }));

  const tacticLabel = (val) =>
    (ENUMS.tactics.find(t => t[0] === val) || [val, val])[1];

  const stepNumber = (idx) => idx + 1;

  function addStep() {
    if (!selectedTech) return;
    const step = {
      tactic:         selectedTech.tactic,
      mitre_id:       selectedTech.mitre_id,
      technique_name: selectedTech.name,
      action:         draft.action,
      description:    draft.description,
    };
    set("steps", [...form.steps, step]);
    setSelectedTech(null);
    setDraft({ ...EMPTY_STEP });
  }

  function removeStep(idx) {
    set("steps", form.steps.filter((_, i) => i !== idx));
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
          <div className="page-eyebrow">
            {isEdit ? `Scénario #${scenarioId}` : "Nouveau scénario"}
          </div>
          <h2 className="drawer-content-title">
            {isEdit ? "Modifier le scénario" : "Nouveau scénario d'attaque"}
          </h2>
        </div>
      </div>

      <p className="faint" style={{ fontSize: 13, marginBottom: 20 }}>
        Chaîne d'étapes mappées MITRE ATT&CK · réutilisable lors de la planification d'un audit.
      </p>

      {err && <div className="modal-err" style={{ marginBottom: 14 }}>{err}</div>}

      {/* Champs généraux */}
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

      {/* ── Matrice MITRE (aperçu dynamique) ── */}
      {form.steps.some(s => s.mitre_id) && (
        <MitreMatrix
          steps={form.steps
            .filter(s => s.mitre_id)
            .map((s, i) => ({ ...s, order: i + 1 }))}
        />
      )}

      {/* ── Section ATT&CK ── */}
      <div className="scen-section">
        <div className="scen-section-head">
          <span className="scen-badge scen-badge-atk">ATT&CK</span>
          <span className="scen-section-title">Étapes offensives</span>
          <span className="scen-section-count">
            {form.steps.length} étape{form.steps.length > 1 ? "s" : ""}
          </span>
        </div>

        {/* Liste des étapes */}
        {form.steps.length > 0 && (
          <div className="scen-items">
            {form.steps.map((st, idx) => (
              <div className="scen-item-card" key={idx}>
                <div className="scen-num scen-num-atk">{stepNumber(idx)}</div>
                <div className="scen-item-body">
                  <div className="scen-item-line1">
                    <span className="kc-tactic">{tacticLabel(st.tactic) || st.tactic}</span>
                    {st.mitre_id && <span className="ttp">{st.mitre_id}</span>}
                    {st.technique_name && (
                      <span className="scen-item-name">{st.technique_name}</span>
                    )}
                  </div>
                  {st.action && (
                    <div className="kc-cmd" style={{ marginTop: 5 }}>
                      <span className="kc-prompt">$</span> {st.action}
                    </div>
                  )}
                  {st.description && (
                    <div className="kc-desc">{st.description}</div>
                  )}
                </div>
                <div className="scen-item-actions">
                  {st.mitre_id && (
                    <InfoBtn
                      href={attackUrl(st.mitre_id)}
                      title={`Voir ${st.mitre_id} sur attack.mitre.org`}
                      variant="atk"
                    />
                  )}
                  <button
                    className="icon-btn danger"
                    onClick={() => removeStep(idx)}
                    title="Supprimer cette étape"
                  >🗑</button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Zone d'ajout */}
        <div className="scen-add-zone">
          <span className="scen-add-label">Ajouter une étape ATT&CK</span>
          <MitreTechniquePicker
            value={selectedTech}
            onChange={setSelectedTech}
          />
          <div className="scen-add-fields">
            <Input mono value={draft.action} onChange={v => setD("action", v)}
              placeholder="Commande / outil (ex. nmap -sV, mimikatz)" />
            <div style={{ height: 6 }} />
            <Textarea value={draft.description} onChange={v => setD("description", v)}
              placeholder="Description de l'étape et résultat attendu…" />
          </div>
          <button
            className={`btn btn-ghost btn-sm${selectedTech ? " btn-ready" : ""}`}
            style={{ marginTop: 10 }}
            onClick={addStep}
            disabled={!selectedTech}
          >
            + Ajouter l'étape
          </button>
        </div>
      </div>

      {/* ── Section D3FEND accordéon ── */}
      {form.steps.some(s => s.mitre_id) && (
        <div className="scen-section" style={{ marginBottom: 4 }}>
          <D3fendAccordion
            steps={form.steps.map((s, i) => ({ ...s, order: i + 1 }))}
          />
        </div>
      )}

      {/* Champs supplémentaires */}
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
        <button className="btn btn-ghost" onClick={onCancel} disabled={saving}>Annuler</button>
        <button className="btn btn-primary" onClick={save} disabled={saving}>
          {saving ? "Enregistrement…" : isEdit ? "Enregistrer" : "Créer le scénario"}
        </button>
      </div>

      {node}
    </div>
  );
}
