import { useEffect, useState } from "react";
import { api, ENUMS } from "../api/client";
import {
  Modal, Field, Input, NumberInput, Select, Textarea, ChipPicker,
} from "../components/Form";
import { severityClass, fmtMin, fmtMilestones, auditStatusClass } from "../lib/format";
import { useToast } from "../lib/useToast";

export default function AuditDetail({ auditId, onBack, onSelectApp }) {
  const [audit, setAudit] = useState(null);
  const [rows, setRows] = useState([]);        // assessments
  const [findings, setFindings] = useState([]);
  const [apps, setApps] = useState([]);
  const [scenarios, setScenarios] = useState([]);
  const [editing, setEditing] = useState(null); // form metadata
  const [execEdit, setExecEdit] = useState(false);
  const [err, setErr] = useState(null);
  const [loadErr, setLoadErr] = useState(null);
  const { show, node } = useToast();

  async function load() {
    try {
      const a = await api.getAudit(auditId);
      setAudit(a);
      let r = await api.assessments(auditId);
      if (r.length === 0 && a.scenarios.length) r = await api.populateAudit(auditId);
      setRows(r);
      setFindings(await api.findings(null, auditId));
      setApps(await api.applications());
      setScenarios(await api.scenarios());
    } catch (e) { setLoadErr(e.message); }
  }
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [auditId]);

  const appName = (id) => apps.find((a) => a.id === id)?.name || "—";

  // Sauvegarde générique d'une étape (préserve tous les champs)
  async function saveStep(row, patch) {
    await api.upsertAssessment(auditId, {
      audit_id: auditId,
      technique_id: row.technique_id,
      detected: !!row.detected,
      responded: !!row.responded,
      detection_time_min: row.detection_time_min,
      response_time_min: row.response_time_min,
      step_description: row.step_description || "",
      command: row.command || "",
      step_order: row.step_order,
      notes: row.notes || "",
      ...patch,
    });
    setRows(await api.assessments(auditId));
  }

  const toggleCell = (row, field) =>
    saveStep(row, { [field]: !row[field] });

  // --- édition d'une étape (commande, description, MTTD, MTTR) ---
  const [stepEdit, setStepEdit] = useState(null);
  function openStepEdit(row) {
    setStepEdit({
      ...row,
      detection_time_min: row.detection_time_min ?? "",
      response_time_min: row.response_time_min ?? "",
    });
  }
  const setS = (k, v) => setStepEdit((e) => ({ ...e, [k]: v }));
  async function saveStepEdit() {
    await saveStep(stepEdit, {
      step_description: stepEdit.step_description || "",
      command: stepEdit.command || "",
      detection_time_min:
        stepEdit.detection_time_min === "" ? null : Number(stepEdit.detection_time_min),
      response_time_min:
        stepEdit.response_time_min === "" ? null : Number(stepEdit.response_time_min),
      step_order: stepEdit.step_order,
    });
    setStepEdit(null);
    show("Étape mise à jour");
  }

  // --- édition métadonnées ---
  function openEdit() {
    setErr(null);
    setEditing({
      name: audit.name, audit_type: audit.audit_type, status: audit.status,
      application_id: audit.application_id, team: audit.team,
      results: audit.results, scenario_ids: audit.scenarios.map((s) => s.id),
    });
  }
  const setF = (k, v) => setEditing((e) => ({ ...e, [k]: v }));
  function toggleScenario(id) {
    const cur = editing.scenario_ids;
    setF("scenario_ids", cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]);
  }
  async function save() {
    if (!editing.name.trim()) { setErr("Le nom est obligatoire."); return; }
    try {
      await api.updateAudit(auditId, editing);
      if (editing.scenario_ids.length) await api.populateAudit(auditId);
      setEditing(null);
      show("Audit mis à jour");
      load();
    } catch (e) { setErr(e.message); }
  }

  if (loadErr) return <div className="empty">Erreur : {loadErr}</div>;
  if (!audit) return <div className="loading">Chargement de l'audit…</div>;

  return (
    <>
      <button className="back-link" onClick={onBack}>← Retour aux audits</button>

      <div className="page-head">
        <div className="flex between center">
          <div>
            <div className="page-eyebrow">
              {audit.audit_type} · Audit #{audit.id}
            </div>
            <h1 className="page-title">{audit.name}</h1>
          </div>
          <button className="btn btn-primary" onClick={openEdit}>Éditer l'audit</button>
        </div>
      </div>

      {/* Métadonnées */}
      <div className="card">
        <span className="card-label">Métadonnées</span>
        <div className="meta-grid" style={{ marginTop: 14 }}>
          <Meta label="Type" value={<span className="badge violet">{audit.audit_type}</span>} />
          <Meta label="Statut" value={<span className={`badge ${auditStatusClass(audit.status)}`}>{audit.status}</span>} />
          <Meta
            label="Application"
            value={
              <span className="linklike" onClick={() => onSelectApp && onSelectApp(audit.application_id)}>
                {appName(audit.application_id)}
              </span>
            }
          />
          <Meta label="Prestataire / équipe" value={audit.team || "—"} />
          <Meta label="Jalons" value={<span className="mono">{fmtMilestones(audit.start_date, audit.end_date)}</span>} />
          <Meta
            label="Scénarios CTI"
            value={audit.scenarios.length
              ? audit.scenarios.map((s) => s.threat_actor || s.name).join(", ")
              : "—"}
          />
        </div>
        {audit.results && (
          <div style={{ marginTop: 16 }}>
            <span className="card-label">Résultats / notes</span>
            <p className="muted" style={{ fontSize: 14, lineHeight: 1.5, marginTop: 6 }}>{audit.results}</p>
          </div>
        )}
      </div>

      {/* Exécution ATT&CK */}
      <div className="flex between center" style={{ margin: "34px 0 14px" }}>
        <h2 className="section-title" style={{ margin: 0 }}>Exécution ATT&CK</h2>
        <button className="btn btn-ghost btn-sm" onClick={() => setExecEdit((v) => !v)}>
          {execEdit ? "Terminer l'édition" : "Éditer l'exécution"}
        </button>
      </div>

      {rows.length === 0 ? (
        <div className="card faint" style={{ fontSize: 13 }}>
          Aucune technique. Rattachez un scénario à cet audit.
        </div>
      ) : execEdit ? (
        /* --- Mode édition : table avec toggles + édition de l'étape --- */
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>#</th><th>Technique</th><th>Détection</th><th>Réaction</th>
                <th>MTTD</th><th>MTTR</th><th>Commande / outil</th>
                <th style={{ textAlign: "right" }}>Étape</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td className="mono faint">{row.step_order ?? "—"}</td>
                  <td>
                    <span className="ttp">{row.technique.mitre_id}</span>{" "}
                    <span className="muted" style={{ fontSize: 13 }}>{row.technique.name}</span>
                  </td>
                  <td>
                    <button className={`toggle ${row.detected ? "on-y" : "on-n"}`} onClick={() => toggleCell(row, "detected")}>
                      {row.detected ? "OUI" : "NON"}
                    </button>
                  </td>
                  <td>
                    <button className={`toggle ${row.responded ? "on-y" : "on-n"}`} onClick={() => toggleCell(row, "responded")}>
                      {row.responded ? "OUI" : "NON"}
                    </button>
                  </td>
                  <td className="mono faint">{fmtMin(row.detection_time_min)}</td>
                  <td className="mono faint">{fmtMin(row.response_time_min)}</td>
                  <td className="mono faint" style={{ fontSize: 12, maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {row.command || "—"}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <button className="btn btn-ghost btn-sm" onClick={() => openStepEdit(row)}>
                      Éditer
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        /* --- Mode lecture : kill-chain ordonnée (façon maquette) --- */
        <div className="card">
          <div className="killchain-head">
            Kill-chain · {rows.length} étape{rows.length > 1 ? "s" : ""} mappée
            {rows.length > 1 ? "s" : ""} MITRE ATT&CK
          </div>
          <div className="killchain">
            {rows.map((row) => (
              <div className="kc-step" key={row.id}>
                <div className={`kc-num ${row.detected ? (row.responded ? "kc-full" : "kc-detect") : "kc-none"}`}>
                  {row.step_order ?? "·"}
                </div>
                <div className="kc-body">
                  <div className="kc-line1">
                    <span className="kc-tactic">{row.technique.tactic || "—"}</span>
                    <span className="ttp">{row.technique.mitre_id}</span>
                    <span className="kc-name">{row.technique.name}</span>
                    <span className="kc-flags">
                      <span className={`yn ${row.detected ? "y" : "n"}`} title="Détection">
                        D:{row.detected ? "OUI" : "NON"}
                      </span>
                      <span className={`yn ${row.responded ? "y" : "n"}`} title="Réaction">
                        R:{row.responded ? "OUI" : "NON"}
                      </span>
                      {row.detection_time_min != null && (
                        <span className="kc-time">MTTD {fmtMin(row.detection_time_min)}′</span>
                      )}
                      {row.response_time_min != null && (
                        <span className="kc-time">MTTR {fmtMin(row.response_time_min)}′</span>
                      )}
                    </span>
                  </div>
                  {row.step_description && (
                    <div className="kc-desc">{row.step_description}</div>
                  )}
                  {row.command && (
                    <div className="kc-cmd"><span className="kc-prompt">$</span> {row.command}</div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Vulnérabilités rattachées à cet audit */}
      <h2 className="section-title">Vulnérabilités de l'audit</h2>
      <div className="card">
        {findings.length === 0 ? (
          <div className="faint" style={{ fontSize: 13 }}>
            Aucune vulnérabilité rattachée à cet audit.
          </div>
        ) : (
          <table>
            <thead>
              <tr><th>Titre</th><th>Sévérité</th><th>CVSS</th><th>Mapping</th><th>Statut</th></tr>
            </thead>
            <tbody>
              {findings.map((f) => (
                <tr key={f.id}>
                  <td style={{ fontWeight: 500 }}>{f.title}</td>
                  <td><span className={`badge ${severityClass(f.severity)}`}>{f.severity}</span></td>
                  <td className="mono">{f.cvss.toFixed(1)}</td>
                  <td>{[f.owasp, f.cwe, f.capec].filter(Boolean).map((m) => <span className="ttp" key={m}>{m}</span>)}</td>
                  <td className="muted" style={{ fontSize: 13 }}>{f.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Modale d'édition des métadonnées */}
      {editing && (
        <Modal
          title="Modifier l'audit"
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
            <Input value={editing.name} onChange={(v) => setF("name", v)} />
          </Field>
          <div className="field-row">
            <Field label="Type">
              <Select value={editing.audit_type} onChange={(v) => setF("audit_type", v)} options={ENUMS.auditType} />
            </Field>
            <Field label="Statut">
              <Select value={editing.status} onChange={(v) => setF("status", v)} options={ENUMS.auditStatus} />
            </Field>
          </div>
          <div className="field-row">
            <Field label="Application *">
              <select className="select" value={editing.application_id ?? ""}
                onChange={(e) => setF("application_id", Number(e.target.value))}>
                {apps.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
              </select>
            </Field>
            <Field label="Prestataire / équipe">
              <Input value={editing.team} onChange={(v) => setF("team", v)} />
            </Field>
          </div>
          <Field label="Scénarios CTI">
            {scenarios.length === 0
              ? <span className="faint" style={{ fontSize: 13 }}>Aucun scénario disponible.</span>
              : <ChipPicker
                  items={scenarios.map((s) => ({ value: s.id, label: s.threat_actor || s.name, title: s.name }))}
                  selected={editing.scenario_ids}
                  onToggle={toggleScenario}
                />}
          </Field>
          <Field label="Résultats / notes">
            <Textarea value={editing.results} onChange={(v) => setF("results", v)} />
          </Field>
        </Modal>
      )}

      {/* Modale d'édition d'une étape de la kill-chain */}
      {stepEdit && (
        <Modal
          title={`Étape ${stepEdit.step_order ?? ""} · ${stepEdit.technique.mitre_id}`}
          onClose={() => setStepEdit(null)}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setStepEdit(null)}>Annuler</button>
              <button className="btn btn-primary" onClick={saveStepEdit}>Enregistrer</button>
            </>
          }
        >
          <div className="faint" style={{ fontSize: 13, marginBottom: 14 }}>
            {stepEdit.technique.tactic} · {stepEdit.technique.name}
          </div>
          <Field label="Description de l'étape">
            <Textarea value={stepEdit.step_description}
              onChange={(v) => setS("step_description", v)}
              placeholder="Ce qui a été tenté…" />
          </Field>
          <Field label="Commande / outil" hint="Affichée comme une ligne de terminal dans la kill-chain">
            <Input mono value={stepEdit.command}
              onChange={(v) => setS("command", v)}
              placeholder="ex. mimikatz sekurlsa::logonpasswords" />
          </Field>
          <div className="field-row-3">
            <Field label="Ordre">
              <NumberInput min={1} value={stepEdit.step_order}
                onChange={(v) => setS("step_order", v)} />
            </Field>
            <Field label="MTTD (min)">
              <NumberInput min={0} value={stepEdit.detection_time_min}
                onChange={(v) => setS("detection_time_min", v ?? "")} />
            </Field>
            <Field label="MTTR (min)">
              <NumberInput min={0} value={stepEdit.response_time_min}
                onChange={(v) => setS("response_time_min", v ?? "")} />
            </Field>
          </div>
          <div className="field-row">
            <Field label="Détection">
              <button className={`toggle ${stepEdit.detected ? "on-y" : "on-n"}`}
                onClick={() => setS("detected", !stepEdit.detected)}>
                {stepEdit.detected ? "OUI" : "NON"}
              </button>
            </Field>
            <Field label="Réaction">
              <button className={`toggle ${stepEdit.responded ? "on-y" : "on-n"}`}
                onClick={() => setS("responded", !stepEdit.responded)}>
                {stepEdit.responded ? "OUI" : "NON"}
              </button>
            </Field>
          </div>
        </Modal>
      )}
      {node}
    </>
  );
}

function Meta({ label, value }) {
  return (
    <div className="meta-item">
      <span className="meta-label">{label}</span>
      <span className="meta-value">{value}</span>
    </div>
  );
}
