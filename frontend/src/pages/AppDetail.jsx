import { useEffect, useState } from "react";
import { api, ENUMS } from "../api/client";
import { KpiTile, ScorePill, DIC } from "../components/Shared";
import { AttackMatrix, CapabilityLegend } from "../components/AttackMatrix";
import {
  Modal, Field, Input, NumberInput, Select, Textarea, ChipPicker,
} from "../components/Form";
import { CpePicker } from "../components/CpePicker";
import {
  severityClass,
  fmtMin,
  fmtMilestones,
  auditStatusClass,
} from "../lib/format";
import { useToast } from "../lib/useToast";

export default function AppDetail({ appId, onBack, onManageAudits, onManageApps, onOpenAudit }) {
  const [dash, setDash] = useState(null);
  const [matrix, setMatrix] = useState(null);
  const [findings, setFindings] = useState([]);
  const [audits, setAudits] = useState([]);
  const [appFull, setAppFull] = useState(null);   // métadonnées complètes (pour édition)
  const [scenarios, setScenarios] = useState([]);
  const [registerOpen, setRegisterOpen] = useState(true);
  const [err, setErr] = useState(null);

  // modales
  const [editApp, setEditApp] = useState(null);
  const [newAudit, setNewAudit] = useState(null);
  const [newFinding, setNewFinding] = useState(null);
  const [modalErr, setModalErr] = useState(null);
  const { show, node } = useToast();

  async function loadAll() {
    try {
      const [d, m, f, allAudits, app, scn] = await Promise.all([
        api.applicationDashboard(appId),
        api.applicationMatrix(appId),
        api.findings(appId),
        api.audits(),
        api.getApplication ? api.getApplication(appId) : null,
        api.scenarios(),
      ]);
      setDash(d);
      setMatrix(m);
      setFindings(f);
      setAudits(allAudits.filter((a) => a.application_id === appId));
      setAppFull(app);
      setScenarios(scn);
    } catch (e) {
      setErr(e.message);
    }
  }

  useEffect(() => {
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [appId]);

  if (err) return <div className="empty">Erreur : {err}</div>;
  if (!dash) return <div className="loading">Chargement de l'application…</div>;

  const k = dash.kpis;

  // --- édition métadonnées application ---
  function openEditApp() {
    setModalErr(null);
    setEditApp({ ...appFull });
  }
  const setA = (key, v) => setEditApp((e) => ({ ...e, [key]: v }));
  async function saveApp() {
    if (!editApp.name.trim()) { setModalErr("Le nom est obligatoire."); return; }
    try {
      await api.updateApplication(appId, editApp);
      setEditApp(null);
      show("Application mise à jour");
      loadAll();
    } catch (e) { setModalErr(e.message); }
  }

  // --- ajout d'audit (application pré-remplie) ---
  function openNewAudit() {
    setModalErr(null);
    setNewAudit({
      name: "", audit_type: "Purple Team", status: "Draft",
      application_id: appId, team: "", results: "", scenario_ids: [],
      start_date: "", end_date: "",
    });
  }
  const setAu = (key, v) => setNewAudit((e) => ({ ...e, [key]: v }));
  function toggleAuditScenario(id) {
    const cur = newAudit.scenario_ids;
    setAu("scenario_ids", cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]);
  }
  async function saveAudit() {
    if (!newAudit.name.trim()) { setModalErr("Le nom est obligatoire."); return; }
    try {
      const audit = await api.createAudit({
        ...newAudit,
        start_date: newAudit.start_date || null,
        end_date: newAudit.end_date || null,
      });
      if (newAudit.scenario_ids.length) await api.populateAudit(audit.id);
      setNewAudit(null);
      show("Audit créé");
      loadAll();
    } catch (e) { setModalErr(e.message); }
  }

  // --- ajout de vulnérabilité (application pré-remplie) ---
  function openNewFinding() {
    setModalErr(null);
    setNewFinding({
      title: "", description: "", impact: "", cvss: 0, severity: "Medium",
      status: "Open", owasp: "", cwe: "", capec: "",
      application_id: appId, audit_id: null,
    });
  }
  const setFi = (key, v) => setNewFinding((e) => ({ ...e, [key]: v }));
  async function saveFinding() {
    if (!newFinding.title.trim()) { setModalErr("Le titre est obligatoire."); return; }
    try {
      await api.createFinding({ ...newFinding, audit_id: newFinding.audit_id || null });
      setNewFinding(null);
      show("Vulnérabilité créée");
      loadAll();
    } catch (e) { setModalErr(e.message); }
  }

  return (
    <>
      <button className="back-link" onClick={onBack}>
        ← Retour au portefeuille
      </button>

      <div className="page-head">
        <div className="flex between center">
          <div>
            <div className="page-eyebrow">{dash.exposure} · Application</div>
            <h1 className="page-title">{dash.application_name}</h1>
            <div className="flex gap center" style={{ marginTop: 8 }}>
              <DIC dic={dash.dic} />
              <span className="faint">·</span>
              <span className="muted" style={{ fontSize: 13 }}>
                {dash.techniques_tested}/{dash.techniques_relevant} techniques jouées
                sur {dash.audits_count} audit(s)
              </span>
            </div>
          </div>
          <div className="flex gap-sm" style={{ flexWrap: "wrap", justifyContent: "flex-end" }}>
            <button className="btn btn-ghost btn-sm" onClick={openNewFinding}>+ Vulnérabilité</button>
            <button className="btn btn-ghost btn-sm" onClick={openNewAudit}>+ Audit</button>
            <button className="btn btn-primary btn-sm" onClick={openEditApp}>Éditer l'application</button>
          </div>
        </div>
      </div>

      {/* Profil de risque de l'application */}
      <div className="profile-row">
        <div
          className="profile-card clickable-card"
          onClick={() => onManageApps && onManageApps()}
          title="Modifier dans la gestion des applications"
        >
          <div className="profile-label">Criticité métier · C<sub>M</sub></div>
          <div className="profile-main">
            <span className={`crit-pill crit-${dash.business_criticality.level}`}>
              {dash.business_criticality.label}
            </span>
            <span className="profile-coef">×{dash.business_criticality.coefficient}</span>
          </div>
          <div className="profile-hint">cliquez pour changer</div>
        </div>

        <div
          className="profile-card clickable-card"
          onClick={() => onManageApps && onManageApps()}
          title="Modifier dans la gestion des applications"
        >
          <div className="profile-label">Exposition réseau · E<sub>NET</sub></div>
          <div className="profile-main">
            <span className="exp-dot" />
            <span className="profile-strong">{dash.network_exposure.exposure}</span>
            <span className="profile-coef">×{dash.network_exposure.coefficient}</span>
          </div>
          <div className="profile-hint">cliquez pour changer</div>
        </div>

        <div className="profile-card">
          <div className="profile-label">Couverture d'audit</div>
          <div className="coverage-track">
            {dash.audit_coverage.items.map((it) => (
              <div className="coverage-seg" key={it.type}>
                <span className={`coverage-bar ${it.done ? "done" : ""}`} />
                <span className={`coverage-name ${it.done ? "done" : ""}`}>{it.type}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Les 5 KPIs du MVP */}
      <div className="kpi-row">
        <KpiTile name="Couverture ATT&CK" value={k.attack_coverage_pct} unit="%" pct={k.attack_coverage_pct} />
        <KpiTile name="Détection" value={k.detection_coverage_pct} unit="%" pct={k.detection_coverage_pct} />
        <KpiTile name="Réaction" value={k.response_coverage_pct} unit="%" pct={k.response_coverage_pct} />
        <KpiTile name="MTTD" value={fmtMin(k.mttd_min)} unit="min" />
        <KpiTile name="MTTR" value={fmtMin(k.mttr_min)} unit="min" />
      </div>

      {/* Matrice ATT&CK consolidée — dernière valeur connue par technique */}
      <h2 className="section-title">Matrice MITRE ATT&CK</h2>
      <p className="muted" style={{ fontSize: 13, marginTop: -6, marginBottom: 14 }}>
        Capacité de détection et de réaction par technique, consolidée sur tous
        les audits de l'application. En cas de doublon, la valeur de l'audit le
        plus récent est retenue.
      </p>
      <div className="card">
        <CapabilityLegend />
        {matrix && (
          <div className="matrix-summary">
            <span><b>{matrix.counts.total}</b> techniques testées</span>
            <span style={{ color: "var(--mint)" }}><b>{matrix.counts.full}</b> détectées + réagies</span>
            <span style={{ color: "var(--amber)" }}><b>{matrix.counts.detect}</b> détectées seules</span>
            <span style={{ color: "var(--coral)" }}><b>{matrix.counts.none}</b> manquées</span>
          </div>
        )}
        <div style={{ marginTop: 16 }}>
          <AttackMatrix matrix={matrix} />
        </div>
      </div>

      {/* Registre des audits — placé après la matrice */}
      <div className="card" style={{ marginTop: 24, padding: 0, overflow: "hidden" }}>
        <div className="flex between center register-head">
          <span style={{ fontWeight: 600, fontSize: 14 }}>
            Registre d'audits de l'application
            <span className="faint" style={{ fontWeight: 400 }}>
              {" "}· {audits.length} mission{audits.length > 1 ? "s" : ""}
            </span>
          </span>
          <button
            className="register-toggle"
            onClick={() => setRegisterOpen((o) => !o)}
          >
            {registerOpen ? "Masquer le registre ▲" : "Afficher le registre ▼"}
          </button>
        </div>

        {registerOpen && (
          audits.length === 0 ? (
            <div className="faint" style={{ padding: "18px 20px", fontSize: 13 }}>
              Aucune mission enregistrée pour cette application.
            </div>
          ) : (
            <table className="register-table">
              <thead>
                <tr>
                  <th>Mission</th>
                  <th>Prestataire</th>
                  <th>Jalons</th>
                  <th style={{ textAlign: "right" }}>ID</th>
                  <th>Statut</th>
                  <th style={{ textAlign: "right" }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {audits.map((audit) => (
                  <tr key={audit.id} className="clickable"
                      onClick={() => onOpenAudit && onOpenAudit(audit.id)}>
                    <td><span className="badge violet">{audit.audit_type}</span></td>
                    <td><span style={{ fontWeight: 500 }}>{audit.team || "—"}</span></td>
                    <td className="mono faint" style={{ fontSize: 13 }}>
                      {fmtMilestones(audit.start_date, audit.end_date)}
                    </td>
                    <td className="mono faint" style={{ textAlign: "right" }}>{audit.id}</td>
                    <td>
                      <span className={`badge ${auditStatusClass(audit.status)}`}>{audit.status}</span>
                    </td>
                    <td style={{ textAlign: "right" }} onClick={(e) => e.stopPropagation()}>
                      <button className="register-edit"
                        onClick={() => onOpenAudit && onOpenAudit(audit.id)}>
                        Ouvrir
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        )}
      </div>

      {/* Module 5 — vulnérabilités */}
      <h2 className="section-title">Vulnérabilités</h2>
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Titre</th>
              <th>Sévérité</th>
              <th>CVSS</th>
              <th>Mapping</th>
              <th>Statut</th>
            </tr>
          </thead>
          <tbody>
            {findings.length === 0 && (
              <tr>
                <td colSpan={5} className="faint">Aucune vulnérabilité.</td>
              </tr>
            )}
            {findings.map((f) => (
              <tr key={f.id}>
                <td style={{ fontWeight: 500 }}>{f.title}</td>
                <td>
                  <span className={`badge ${severityClass(f.severity)}`}>
                    {f.severity}
                  </span>
                </td>
                <td className="mono">{f.cvss.toFixed(1)}</td>
                <td>
                  {[f.owasp, f.cwe, f.capec].filter(Boolean).map((m) => (
                    <span className="ttp" key={m}>{m}</span>
                  ))}
                </td>
                <td className="muted" style={{ fontSize: 13 }}>{f.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Modale : éditer les métadonnées de l'application */}
      {editApp && (
        <Modal
          title="Éditer l'application"
          onClose={() => setEditApp(null)}
          error={modalErr}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setEditApp(null)}>Annuler</button>
              <button className="btn btn-primary" onClick={saveApp}>Enregistrer</button>
            </>
          }
        >
          <Field label="Nom *">
            <Input value={editApp.name} onChange={(v) => setA("name", v)} />
          </Field>
          <Field label="Description">
            <Textarea value={editApp.description} onChange={(v) => setA("description", v)} />
          </Field>
          <div className="field-row">
            <Field label="Responsable"><Input value={editApp.owner} onChange={(v) => setA("owner", v)} /></Field>
            <Field label="Équipe"><Input value={editApp.team} onChange={(v) => setA("team", v)} /></Field>
          </div>
          <div className="field-row">
            <Field label="Email"><Input value={editApp.email} onChange={(v) => setA("email", v)} /></Field>
            <Field label="Téléphone"><Input value={editApp.phone} onChange={(v) => setA("phone", v)} /></Field>
          </div>
          <div className="field-row">
            <Field label="Exposition">
              <Select value={editApp.exposure} onChange={(v) => setA("exposure", v)} options={ENUMS.exposure} />
            </Field>
            <Field label="URL"><Input value={editApp.url} onChange={(v) => setA("url", v)} /></Field>
          </div>
          <Field label="Technologies">
            <CpePicker
              valueRaw={editApp.technologies_cpe}
              onChange={(raw, readable) => {
                setA("technologies_cpe", raw);
                setA("technologies", readable);
              }}
            />
          </Field>
          <Field label="Criticité DIC (1 à 5)">
            <div className="field-row-3">
              <div><span className="hint">Disponibilité</span>
                <NumberInput min={1} max={5} value={editApp.dic_availability} onChange={(v) => setA("dic_availability", v)} /></div>
              <div><span className="hint">Intégrité</span>
                <NumberInput min={1} max={5} value={editApp.dic_integrity} onChange={(v) => setA("dic_integrity", v)} /></div>
              <div><span className="hint">Confidentialité</span>
                <NumberInput min={1} max={5} value={editApp.dic_confidentiality} onChange={(v) => setA("dic_confidentiality", v)} /></div>
            </div>
          </Field>
          <div className="field-row">
            <Field label="Scope Red Team"><Textarea value={editApp.scope_red_team} onChange={(v) => setA("scope_red_team", v)} /></Field>
            <Field label="Scope Pentest"><Textarea value={editApp.scope_pentest} onChange={(v) => setA("scope_pentest", v)} /></Field>
          </div>
        </Modal>
      )}

      {/* Modale : ajouter un audit (application verrouillée) */}
      {newAudit && (
        <Modal
          title="Nouvel audit"
          onClose={() => setNewAudit(null)}
          error={modalErr}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setNewAudit(null)}>Annuler</button>
              <button className="btn btn-primary" onClick={saveAudit}>Créer l'audit</button>
            </>
          }
        >
          <div className="modal-locked">
            Application : <b>{dash.application_name}</b>
          </div>
          <Field label="Nom *">
            <Input value={newAudit.name} onChange={(v) => setAu("name", v)}
              placeholder="ex. Purple Team CRM — APT29 Q3" />
          </Field>
          <div className="field-row">
            <Field label="Type">
              <Select value={newAudit.audit_type} onChange={(v) => setAu("audit_type", v)} options={ENUMS.auditType} />
            </Field>
            <Field label="Statut">
              <Select value={newAudit.status} onChange={(v) => setAu("status", v)} options={ENUMS.auditStatus} />
            </Field>
          </div>
          <div className="field-row">
            <Field label="Date de début (jalon)">
              <input type="date" className="input" value={newAudit.start_date}
                onChange={(e) => setAu("start_date", e.target.value)} />
            </Field>
            <Field label="Date de fin (jalon)" hint="Vide si en cours">
              <input type="date" className="input" value={newAudit.end_date}
                onChange={(e) => setAu("end_date", e.target.value)} />
            </Field>
          </div>
          <Field label="Prestataire / équipe">
            <Input value={newAudit.team} onChange={(v) => setAu("team", v)} placeholder="ex. SOC interne · Cymulate" />
          </Field>
          <Field label="Scénarios CTI" hint="Les techniques seront générées pour évaluation">
            {scenarios.length === 0
              ? <span className="faint" style={{ fontSize: 13 }}>Aucun scénario disponible.</span>
              : <ChipPicker
                  items={scenarios.map((s) => ({ value: s.id, label: s.threat_actor || s.name, title: s.name }))}
                  selected={newAudit.scenario_ids}
                  onToggle={toggleAuditScenario}
                />}
          </Field>
        </Modal>
      )}

      {/* Modale : ajouter une vulnérabilité (application verrouillée) */}
      {newFinding && (
        <Modal
          title="Nouvelle vulnérabilité"
          onClose={() => setNewFinding(null)}
          error={modalErr}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setNewFinding(null)}>Annuler</button>
              <button className="btn btn-primary" onClick={saveFinding}>Créer</button>
            </>
          }
        >
          <div className="modal-locked">
            Application : <b>{dash.application_name}</b>
          </div>
          <Field label="Titre *">
            <Input value={newFinding.title} onChange={(v) => setFi("title", v)}
              placeholder="ex. Injection SQL formulaire de recherche" />
          </Field>
          <Field label="Description"><Textarea value={newFinding.description} onChange={(v) => setFi("description", v)} /></Field>
          <Field label="Impact"><Textarea value={newFinding.impact} onChange={(v) => setFi("impact", v)} /></Field>
          <div className="field-row-3">
            <Field label="Sévérité">
              <Select value={newFinding.severity} onChange={(v) => setFi("severity", v)} options={ENUMS.severity} />
            </Field>
            <Field label="CVSS">
              <NumberInput min={0} max={10} step={0.1} value={newFinding.cvss} onChange={(v) => setFi("cvss", v ?? 0)} />
            </Field>
            <Field label="Statut">
              <Select value={newFinding.status} onChange={(v) => setFi("status", v)} options={ENUMS.findingStatus} />
            </Field>
          </div>
          <div className="field-row-3">
            <Field label="OWASP"><Input mono value={newFinding.owasp} onChange={(v) => setFi("owasp", v)} placeholder="A03" /></Field>
            <Field label="CWE"><Input mono value={newFinding.cwe} onChange={(v) => setFi("cwe", v)} placeholder="CWE-89" /></Field>
            <Field label="CAPEC"><Input mono value={newFinding.capec} onChange={(v) => setFi("capec", v)} placeholder="CAPEC-66" /></Field>
          </div>
          <Field label="Audit rattaché (optionnel)">
            <select className="select"
              value={newFinding.audit_id ?? ""}
              onChange={(e) => setFi("audit_id", e.target.value ? Number(e.target.value) : null)}>
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
