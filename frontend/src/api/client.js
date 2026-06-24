const BASE = "/api";

async function req(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(`${BASE}${path}`, opts);
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      const j = await res.json();
      detail = j.detail || detail;
    } catch (_) {}
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  portfolio: () => req("GET", "/dashboard/portfolio"),
  applicationDashboard: (id) => req("GET", `/dashboard/application/${id}`),
  applicationMatrix: (id) => req("GET", `/dashboard/application/${id}/matrix`),

  applications: () => req("GET", "/applications"),
  applicationsCoverage: () => req("GET", "/applications/coverage"),
  getApplication: (id) => req("GET", `/applications/${id}`),
  createApplication: (b) => req("POST", "/applications", b),
  updateApplication: (id, b) => req("PUT", `/applications/${id}`, b),
  deleteApplication: (id) => req("DELETE", `/applications/${id}`),

  scenarios: () => req("GET", "/cti/scenarios"),
  techniques: () => req("GET", "/cti/techniques"),
  createScenario: (b) => req("POST", "/cti/scenarios", b),
  updateScenario: (id, b) => req("PUT", `/cti/scenarios/${id}`, b),
  deleteScenario: (id) => req("DELETE", `/cti/scenarios/${id}`),

  audits: () => req("GET", "/audits"),
  getAudit: (id) => req("GET", `/audits/${id}`),
  createAudit: (b) => req("POST", "/audits", b),
  updateAudit: (id, b) => req("PUT", `/audits/${id}`, b),
  deleteAudit: (id) => req("DELETE", `/audits/${id}`),
  populateAudit: (id) => req("POST", `/audits/${id}/populate`),
  assessments: (auditId) => req("GET", `/audits/${auditId}/assessments`),
  upsertAssessment: (auditId, b) => req("POST", `/audits/${auditId}/assessments`, b),

  findings: (appId, auditId) => {
    const params = [];
    if (appId) params.push(`application_id=${appId}`);
    if (auditId) params.push(`audit_id=${auditId}`);
    return req("GET", `/findings${params.length ? "?" + params.join("&") : ""}`);
  },
  createFinding: (b) => req("POST", "/findings", b),
  updateFinding: (id, b) => req("PUT", `/findings/${id}`, b),
  deleteFinding: (id) => req("DELETE", `/findings/${id}`),
};

export const ENUMS = {
  exposure: ["Internet", "Interne", "Partenaire", "Cloud"],
  auditType: ["BAS", "Pentest", "Red Team", "Purple Team"],
  auditStatus: ["Draft", "Scoping", "In Progress", "Review", "Completed", "Closed"],
  findingStatus: ["Open", "Validated", "Assigned", "In Progress", "Fixed", "Retested", "Closed"],
  severity: ["Critical", "High", "Medium", "Low", "Info"],
  sophistication: ["Fondamental", "Intermédiaire", "Avancé"],
  // tactiques ATT&CK avec libellé court pour les boutons de la kill-chain
  tactics: [
    ["Initial Access", "Accès init."],
    ["Execution", "Exécution"],
    ["Persistence", "Persistance"],
    ["Privilege Escalation", "Élév. priv."],
    ["Defense Evasion", "Évasion"],
    ["Credential Access", "Identifiants"],
    ["Discovery", "Découverte"],
    ["Lateral Movement", "Mvt latéral"],
    ["Collection", "Collecte"],
    ["Command and Control", "C2"],
    ["Exfiltration", "Exfiltration"],
    ["Impact", "Impact"],
  ],
};
