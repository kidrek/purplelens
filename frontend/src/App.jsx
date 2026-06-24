import { useState } from "react";
import Portfolio from "./pages/Portfolio";
import AppDetail from "./pages/AppDetail";
import AuditDetail from "./pages/AuditDetail";
import ManageApplications from "./pages/ManageApplications";
import ManageScenarios from "./pages/ManageScenarios";
import ManageAudits from "./pages/ManageAudits";
import ManageFindings from "./pages/ManageFindings";

export default function App() {
  const [view, setView] = useState("portfolio");
  const [appId, setAppId] = useState(null);
  const [auditId, setAuditId] = useState(null);

  function selectApp(id) {
    setAppId(id);
    setView("appDetail");
  }
  function openAudit(id) {
    setAuditId(id);
    setView("auditDetail");
  }
  function go(v) {
    setView(v);
  }

  const navItem = (id, label) => (
    <button
      className={`nav-item ${view === id ? "active" : ""}`}
      onClick={() => go(id)}
    >
      <span className="dot" />
      {label}
    </button>
  );

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark" />
          <span className="brand-name">PurpleLens</span>
        </div>
        <div className="brand-tag">Security Validation</div>

        <div className="nav-group-label">Pilotage</div>
        {navItem("portfolio", "Cockpit")}

        <div className="nav-group-label">Gestion</div>
        {navItem("applications", "Applications")}
        {navItem("scenarios", "Scénarios CTI")}
        {navItem("audits", "Audits")}
        {navItem("findings", "Vulnérabilités")}
      </aside>

      <main className="main">
        {view === "portfolio" && <Portfolio onSelectApp={selectApp} />}
        {view === "appDetail" && (
          <AppDetail
            appId={appId}
            onBack={() => go("portfolio")}
            onManageAudits={() => go("audits")}
            onManageApps={() => go("applications")}
            onOpenAudit={openAudit}
          />
        )}
        {view === "auditDetail" && (
          <AuditDetail
            auditId={auditId}
            onBack={() => go("audits")}
            onSelectApp={selectApp}
          />
        )}
        {view === "applications" && <ManageApplications onSelectApp={selectApp} />}
        {view === "scenarios" && <ManageScenarios />}
        {view === "audits" && (
          <ManageAudits onSelectApp={selectApp} onOpenAudit={openAudit} />
        )}
        {view === "findings" && <ManageFindings onSelectApp={selectApp} />}
      </main>
    </div>
  );
}
