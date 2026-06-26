import { useEffect, useState } from "react";
import { api, ENUMS } from "../api/client";
import {
  Modal, Field, Input, NumberInput, Select, Textarea, ChipPicker,
} from "./Form";
import { severityClass, fmtMin, fmtMilestones, auditStatusClass } from "../lib/format";
import { parseRefValue } from "../lib/refData";
import { useToast } from "../lib/useToast";

/**
 * AuditDrawerContent — contenu complet d'un audit, utilisable dans un Drawer.
 *
 * Props :
 *   auditId    {number}  — id de l'audit à afficher
 *   onClose    {fn}      — ferme le drawer
 */
export function AuditDrawerContent({ auditId, onClose }) {
  const [audit, setAudit]         = useState(null);
  const [rows, setRows]           = useState([]);
  const [findings, setFindings]   = useState([]);
  const [apps, setApps]           = useState([]);
  const [scenarios, setScenarios] = useState([]);
  const [editing, setEditing]     = useState(null);   // null = vue, objet = mode édition inline
  const [saving, setSaving]       = useState(false);
  const [execEdit, setExecEdit]   = useState(false);
  const [stepEdit, setStepEdit]   = useState(null);
  const [err, setErr]             = useState(null);
  const [loadErr, setLoadErr]     = useState(null);
  const { show, node }            = useToast();

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

  // ── Édition inline ────────────────────────────────────────────────────
  function openEdit() {
    setErr(null);
    setExecEdit(true);
    setEditing({
      name: audit.name, audit_type: audit.audit_type, status: audit.status,
      application_id: audit.application_id, team: audit.team ?? "",
      results: audit.results ?? "", scenario_ids: audit.scenarios.map((s) => s.id),
    });
  }
  function cancelEdit() { setEditing(null); setExecEdit(false); setErr(null); }
  const setF = (k, v) => setEditing((e) => ({ ...e, [k]: v }));
  function toggleScenario(id) {
    const cur = editing.scenario_ids;
    setF("scenario_ids", cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]);
  }
  async function save() {
    if (!editing.name.trim()) { setErr("Le nom est obligatoire."); return; }
    setSaving(true);
    try {
      await api.updateAudit(auditId, editing);
      if (editing.scenario_ids.length) await api.populateAudit(auditId);
      setEditing(null);
      setExecEdit(false);
      show("Audit mis à jour");
      load();
    } catch (e) { setErr(e.message); } finally { setSaving(false); }
  }

  // ── Assessments ───────────────────────────────────────────────────────
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
  const toggleCell = (row, field) => saveStep(row, { [field]: !row[field] });

  const setS = (k, v) => setStepEdit((e) => ({ ...e, [k]: v }));
  async function saveStepEdit() {
    await saveStep(stepEdit, {
      step_description: stepEdit.step_description || "",
      command: stepEdit.command || "",
      detection_time_min: stepEdit.detection_time_min === "" ? null : Number(stepEdit.detection_time_min),
      response_time_min: stepEdit.response_time_min === "" ? null : Number(stepEdit.response_time_min),
      step_order: stepEdit.step_order,
    });
    setStepEdit(null);
    show("Étape mise à jour");
  }

  if (loadErr) return <div className="empty">Erreur : {loadErr}</div>;
  if (!audit)  return <div className="loading">Chargement de l'audit…</div>;

  return (
    <>
      {/* En-tête */}
      <div className="drawer-content-head">
        <div>
          <div className="page-eyebrow">{audit.audit_type} · Audit #{audit.id}</div>
          <h2 className="drawer-content-title">{editing ? "Modifier l'audit" : audit.name}</h2>
        </div>
        {editing ? (
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-ghost btn-sm" onClick={cancelEdit}>Annuler</button>
            <button className="btn btn-primary btn-sm" onClick={save} disabled={saving}>
              {saving ? "Enregistrement…" : "Enregistrer"}
            </button>
          </div>
        ) : (
          <button className="btn btn-primary btn-sm" onClick={openEdit}>Éditer</button>
        )}
      </div>

      {/* Métadonnées — lecture ou édition inline */}
      {editing ? (
        <>
          {err && <div className="modal-err" style={{ marginBottom: 16 }}>{err}</div>}
          <div className="card" style={{ marginBottom: 20 }}>
            <Field label="Nom *">
              <Input value={editing.name} onChange={(v) => setF("name", v)} placeholder="Nom de l'audit" />
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
                <Input value={editing.team} onChange={(v) => setF("team", v)} placeholder="Nom de l'équipe" />
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
              <Textarea value={editing.results} onChange={(v) => setF("results", v)} placeholder="Observations, conclusions…" />
            </Field>
          </div>
        </>
      ) : (
        <div className="card" style={{ marginBottom: 20 }}>
          <span className="card-label">Métadonnées</span>
          <div className="meta-grid" style={{ marginTop: 14 }}>
            <Meta label="Type" value={<span className="badge violet">{audit.audit_type}</span>} />
            <Meta label="Statut" value={<span className={`badge ${auditStatusClass(audit.status)}`}>{audit.status}</span>} />
            <Meta label="Application" value={appName(audit.application_id)} />
            <Meta label="Prestataire / équipe" value={audit.team || "—"} />
            <Meta label="Jalons" value={<span className="mono">{fmtMilestones(audit.start_date, audit.end_date)}</span>} />
            <Meta label="Scénarios CTI"
              value={audit.scenarios.length
                ? audit.scenarios.map((s) => s.threat_actor || s.name).join(", ")
                : "—"} />
          </div>
          {audit.results && (
            <div style={{ marginTop: 16 }}>
              <span className="card-label">Résultats / notes</span>
              <p className="muted" style={{ fontSize: 14, lineHeight: 1.5, marginTop: 6 }}>{audit.results}</p>
            </div>
          )}
        </div>
      )}

      {/* Exécution ATT&CK */}
      <div className="flex between center" style={{ marginBottom: 12 }}>
        <h3 className="section-title" style={{ margin: 0 }}>Exécution ATT&CK</h3>
      </div>

      {rows.length === 0 ? (
        <div className="card faint" style={{ fontSize: 13, marginBottom: 20 }}>
          Aucune technique. Rattachez un scénario à cet audit.
        </div>
      ) : execEdit ? (
        <div className="card" style={{ marginBottom: 20 }}>
          <table>
            <thead>
              <tr>
                <th>#</th><th>Technique</th><th>Détection</th><th>Réaction</th>
                <th>MTTD</th><th>MTTR</th><th style={{ textAlign: "right" }}>Étape</th>
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
                    <button className={`toggle ${row.detected ? "on-y" : "on-n"}`}
                      onClick={() => toggleCell(row, "detected")}>
                      {row.detected ? "OUI" : "NON"}
                    </button>
                  </td>
                  <td>
                    <button className={`toggle ${row.responded ? "on-y" : "on-n"}`}
                      onClick={() => toggleCell(row, "responded")}>
                      {row.responded ? "OUI" : "NON"}
                    </button>
                  </td>
                  <td className="mono faint">{fmtMin(row.detection_time_min)}</td>
                  <td className="mono faint">{fmtMin(row.response_time_min)}</td>
                  <td style={{ textAlign: "right" }}>
                    <button className="btn btn-ghost btn-sm"
                      onClick={() => setStepEdit({ ...row, detection_time_min: row.detection_time_min ?? "", response_time_min: row.response_time_min ?? "" })}>
                      Éditer
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="killchain-head">
            Kill-chain · {rows.length} étape{rows.length > 1 ? "s" : ""} mappée{rows.length > 1 ? "s" : ""} MITRE ATT&CK
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
                      <span className={`yn ${row.detected ? "y" : "n"}`}>D:{row.detected ? "OUI" : "NON"}</span>
                      <span className={`yn ${row.responded ? "y" : "n"}`}>R:{row.responded ? "OUI" : "NON"}</span>
                      {row.detection_time_min != null && <span className="kc-time">MTTD {fmtMin(row.detection_time_min)}′</span>}
                      {row.response_time_min != null && <span className="kc-time">MTTR {fmtMin(row.response_time_min)}′</span>}
                    </span>
                  </div>
                  {row.step_description && <div className="kc-desc">{row.step_description}</div>}
                  {row.command && <div className="kc-cmd"><span className="kc-prompt">$</span> {row.command}</div>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Vulnérabilités */}
      <h3 className="section-title">Vulnérabilités de l'audit</h3>
      <div className="card" style={{ marginBottom: 20 }}>
        {findings.length === 0 ? (
          <div className="faint" style={{ fontSize: 13 }}>Aucune vulnérabilité rattachée à cet audit.</div>
        ) : (
          <table>
            <thead>
              <tr><th>Titre</th><th>Sévérité</th><th>CVSS</th><th>Statut</th></tr>
            </thead>
            <tbody>
              {findings.map((f) => (
                <tr key={f.id}>
                  <td style={{ fontWeight: 500 }}>{f.title}</td>
                  <td><span className={`badge ${severityClass(f.severity)}`}>{f.severity}</span></td>
                  <td className="mono">{f.cvss.toFixed(1)}</td>
                  <td className="muted" style={{ fontSize: 13 }}>{f.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Modale édition étape ATT&CK */}
      {stepEdit && (
        <Modal title={`Étape ${stepEdit.step_order ?? ""} · ${stepEdit.technique.mitre_id}`}
          onClose={() => setStepEdit(null)}
          footer={<>
            <button className="btn btn-ghost" onClick={() => setStepEdit(null)}>Annuler</button>
            <button className="btn btn-primary" onClick={saveStepEdit}>Enregistrer</button>
          </>}
        >
          <div className="faint" style={{ fontSize: 13, marginBottom: 14 }}>
            {stepEdit.technique.tactic} · {stepEdit.technique.name}
          </div>
          <Field label="Description de l'étape">
            <Textarea value={stepEdit.step_description} onChange={(v) => setS("step_description", v)} placeholder="Ce qui a été tenté…" />
          </Field>
          <Field label="Commande / outil" hint="Affichée comme une ligne de terminal dans la kill-chain">
            <Input mono value={stepEdit.command} onChange={(v) => setS("command", v)} placeholder="ex. mimikatz sekurlsa::logonpasswords" />
          </Field>
          <div className="field-row-3">
            <Field label="Ordre"><NumberInput min={1} value={stepEdit.step_order} onChange={(v) => setS("step_order", v)} /></Field>
            <Field label="MTTD (min)"><NumberInput min={0} value={stepEdit.detection_time_min} onChange={(v) => setS("detection_time_min", v ?? "")} /></Field>
            <Field label="MTTR (min)"><NumberInput min={0} value={stepEdit.response_time_min} onChange={(v) => setS("response_time_min", v ?? "")} /></Field>
          </div>
          <div className="field-row">
            <Field label="Détection">
              <button className={`toggle ${stepEdit.detected ? "on-y" : "on-n"}`} onClick={() => setS("detected", !stepEdit.detected)}>
                {stepEdit.detected ? "OUI" : "NON"}
              </button>
            </Field>
            <Field label="Réaction">
              <button className={`toggle ${stepEdit.responded ? "on-y" : "on-n"}`} onClick={() => setS("responded", !stepEdit.responded)}>
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
