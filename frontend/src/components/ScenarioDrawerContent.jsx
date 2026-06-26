import { useState } from "react";
import { ENUMS } from "../api/client";
import { Drawer } from "./Drawer";
import { ScenarioForm } from "./ScenarioForm";
import { useToast } from "../lib/useToast";

const ENGAGEMENT_COLORS = {
  "BAS":         { bg: "rgba(55,138,221,.1)",  border: "rgba(55,138,221,.4)",  text: "#185FA5" },
  "Pentest":     { bg: "rgba(239,159,39,.1)",  border: "rgba(239,159,39,.4)",  text: "#854F0B" },
  "Red Team":    { bg: "rgba(226,75,74,.1)",   border: "rgba(226,75,74,.4)",   text: "#A32D2D" },
  "Purple Team": { bg: "rgba(83,74,183,.1)",   border: "rgba(83,74,183,.4)",   text: "#534AB7" },
};

const EMPTY_STEP = { tactic: "Initial Access", mitre_id: "", technique_name: "", action: "", description: "" };

/**
 * ScenarioDrawerContent — contenu complet d'un scénario, utilisable dans un Drawer.
 *
 * Props :
 *   scenario   {object}  — objet scénario déjà chargé
 *   onClose    {fn}      — ferme le drawer
 *   onUpdated  {fn}      — callback après modification (reload parent)
 */
export function ScenarioDrawerContent({ scenario: initialScenario, onClose, onUpdated }) {
  const [scenario, setScenario] = useState(initialScenario);
  const [editDrawer, setEditDrawer] = useState(false);
  const { show, node } = useToast();

  const ec = ENGAGEMENT_COLORS[scenario.engagement_type] || {};
  const tacticLabel = (val) => (ENUMS.tactics.find(t => t[0] === val) || [val, val])[1];

  const initialForm = {
    name: scenario.name, objective: scenario.objective,
    threat_actor: scenario.threat_actor, engagement_type: scenario.engagement_type,
    sophistication: scenario.sophistication, references: scenario.references,
    description: scenario.description, ioc: scenario.ioc, ioa: scenario.ioa,
    steps: scenario.steps.map(st => ({
      tactic: st.tactic, mitre_id: st.mitre_id, technique_name: st.technique_name,
      action: st.action, description: st.description,
    })),
  };

  return (
    <>
      {/* En-tête */}
      <div className="drawer-content-head">
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="page-eyebrow">Scénario CTI #{scenario.id}</div>
          <h2 className="drawer-content-title" style={{ wordBreak: "break-word" }}>
            {scenario.name}
          </h2>
        </div>
        <button className="btn btn-primary btn-sm" onClick={() => setEditDrawer(true)}>Éditer</button>
      </div>

      {/* Badges */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 18 }}>
        <span style={{
          fontSize: 11, fontWeight: 600, padding: "3px 9px", borderRadius: 5,
          fontFamily: "var(--mono)",
          background: ec.bg, border: `0.5px solid ${ec.border}`, color: ec.text,
        }}>{scenario.engagement_type}</span>
        {scenario.sophistication && (
          <span style={{
            fontSize: 11, fontWeight: 500, padding: "3px 9px", borderRadius: 5,
            background: "var(--surface-2)", border: "1px solid var(--line)", color: "var(--text-dim)",
          }}>{scenario.sophistication}</span>
        )}
        {scenario.threat_actor && (
          <span className="badge violet" style={{ fontFamily: "var(--mono)", fontSize: 11 }}>
            {scenario.threat_actor}
          </span>
        )}
      </div>

      {/* Description & Objectif */}
      {scenario.objective && (
        <div className="card" style={{ marginBottom: 12 }}>
          <span className="card-label">Objectif</span>
          <p style={{ fontSize: 14, lineHeight: 1.6, marginTop: 8, color: "var(--text)" }}>
            {scenario.objective}
          </p>
        </div>
      )}
      {scenario.description && (
        <div className="card" style={{ marginBottom: 12 }}>
          <span className="card-label">Description</span>
          <p style={{ fontSize: 14, lineHeight: 1.6, marginTop: 8, color: "var(--text)" }}>
            {scenario.description}
          </p>
        </div>
      )}

      {/* Kill-chain */}
      <h3 className="section-title" style={{ marginBottom: 10 }}>
        Kill-chain · {scenario.steps.length} étape{scenario.steps.length > 1 ? "s" : ""}
      </h3>
      {scenario.steps.length === 0 ? (
        <div className="card faint" style={{ fontSize: 13, marginBottom: 16 }}>
          Aucune étape définie pour ce scénario.
        </div>
      ) : (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="killchain">
            {[...scenario.steps].sort((a, b) => (a.order ?? 0) - (b.order ?? 0)).map((st, i) => (
              <div className="kc-step" key={st.id ?? i}>
                <div className="kc-num kc-none" style={{
                  background: "rgba(83,74,183,.15)",
                  border: "1px solid rgba(83,74,183,.4)",
                  color: "var(--violet-bright)",
                }}>
                  {st.order ?? i + 1}
                </div>
                <div className="kc-body">
                  <div className="kc-line1">
                    <span className="kc-tactic">{tacticLabel(st.tactic) || st.tactic}</span>
                    {st.mitre_id && <span className="ttp">{st.mitre_id}</span>}
                    {st.technique_name && (
                      <span className="kc-name">{st.technique_name}</span>
                    )}
                  </div>
                  {st.description && <div className="kc-desc">{st.description}</div>}
                  {st.action && (
                    <div className="kc-cmd">
                      <span className="kc-prompt">$</span> {st.action}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* IOC / IOA */}
      {(scenario.ioc || scenario.ioa) && (
        <div className="card" style={{ marginBottom: 12 }}>
          {scenario.ioc && (
            <div style={{ marginBottom: scenario.ioa ? 12 : 0 }}>
              <span className="card-label">Indicateurs de compromission (IOC)</span>
              <p style={{ fontSize: 13, lineHeight: 1.5, marginTop: 6, color: "var(--text-dim)", fontFamily: "var(--mono)", whiteSpace: "pre-wrap" }}>
                {scenario.ioc}
              </p>
            </div>
          )}
          {scenario.ioa && (
            <div>
              <span className="card-label">Indicateurs d'attaque (IOA)</span>
              <p style={{ fontSize: 13, lineHeight: 1.5, marginTop: 6, color: "var(--text-dim)", fontFamily: "var(--mono)", whiteSpace: "pre-wrap" }}>
                {scenario.ioa}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Références */}
      {scenario.references && (
        <div className="card" style={{ marginBottom: 20 }}>
          <span className="card-label">Références</span>
          <p style={{ fontSize: 13, lineHeight: 1.6, marginTop: 6, color: "var(--text-dim)", wordBreak: "break-all" }}>
            {scenario.references}
          </p>
        </div>
      )}

      {/* Drawer d'édition — s'ouvre par-dessus le drawer de détail */}
      <Drawer
        open={editDrawer}
        onClose={() => setEditDrawer(false)}
        title="Modifier le scénario"
      >
        <ScenarioForm
          initial={initialForm}
          scenarioId={scenario.id}
          onSaved={(updated) => {
            setScenario(s => ({ ...s, ...initialForm }));
            setEditDrawer(false);
            onUpdated?.();
          }}
          onCancel={() => setEditDrawer(false)}
        />
      </Drawer>

      {node}
    </>
  );
}
