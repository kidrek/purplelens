import { useEffect, useState } from "react";
import { api, ENUMS } from "../api/client";
import { ConfirmDialog, EmptyState } from "../components/Form";
import { Drawer } from "../components/Drawer";
import { ScenarioDrawerContent } from "../components/ScenarioDrawerContent";
import { ScenarioForm } from "../components/ScenarioForm";
import { useToast } from "../lib/useToast";

// ── Constantes ────────────────────────────────────────────────────────────────

const ENGAGEMENT_COLORS = {
  "BAS":         { bg: "rgba(55,138,221,.15)", border: "0.5px solid #185FA5", text: "#85B7EB" },
  "Pentest":     { bg: "rgba(239,159,39,.15)", border: "0.5px solid #854F0B", text: "#FAC775" },
  "Red Team":    { bg: "rgba(226,75,74,.15)", border: "0.5px solid #993C1D", text: "#F09595" },
  "Purple Team": { bg: "rgba(83,74,183,.15)", border: "0.5px solid #534AB7", text: "#AFA9EC" },
};

// ── KPIs ─────────────────────────────────────────────────────────────────────

function ScenarioKpis({ items }) {
  if (!items || items.length === 0) return null;

  // Nombre de scénarios
  const total = items.length;

  // Acteurs émulés uniques
  const actors = [...new Set(items.map(s => s.threat_actor).filter(Boolean))];

  // Répartition par type d'engagement
  const byType = {};
  for (const type of ENUMS.auditType) byType[type] = 0;
  for (const s of items) byType[s.engagement_type] = (byType[s.engagement_type] || 0) + 1;

  // Tactiques uniques couvertes
  const tactics = new Set();
  const techniques = new Set();
  for (const s of items) {
    for (const st of s.steps) {
      if (st.tactic) tactics.add(st.tactic);
      if (st.mitre_id) techniques.add(st.mitre_id);
    }
  }

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 10, marginBottom: 20 }}>

      {/* 1. Scénarios */}
      <div className="app-kpi">
        <span className="app-kpi-label">Scénarios CTI</span>
        <span className="app-kpi-value">{total}</span>
        <span className="app-kpi-sub">dans la bibliothèque</span>
      </div>

      {/* 2. Acteurs émulés */}
      <div className="app-kpi">
        <span className="app-kpi-label">Acteurs émulés</span>
        <span className="app-kpi-value" style={{ color: "#534AB7" }}>{actors.length}</span>
        <span className="app-kpi-sub" style={{ wordBreak: "break-word" }}>
          {actors.slice(0, 3).join(" · ")}{actors.length > 3 ? ` +${actors.length - 3}` : ""}
        </span>
      </div>

      {/* 3. Répartition engagement */}
      <div className="app-kpi">
        <span className="app-kpi-label">Répartition</span>
        <div style={{ display: "flex", gap: 5, flexWrap: "wrap", marginTop: 8 }}>
          {ENUMS.auditType.filter(t => byType[t] > 0).map(type => {
            const c = ENGAGEMENT_COLORS[type] || {};
            return (
              <span key={type} style={{
                fontSize: 12, fontWeight: 600, padding: "3px 8px", borderRadius: 5,
                background: c.bg, border: `0.5px solid ${c.border}`, color: c.text,
              }}>
                {byType[type]} {type}
              </span>
            );
          })}
        </div>
        <span className="app-kpi-sub" style={{ marginTop: 6 }}>par type d'engagement</span>
      </div>

      {/* 4. Tactiques couvertes */}
      <div className="app-kpi">
        <span className="app-kpi-label">Tactiques MITRE</span>
        <span className="app-kpi-value" style={{ color: "#1D9E75" }}>{tactics.size}</span>
        <span className="app-kpi-sub">tactiques couvertes</span>
      </div>

      {/* 5. Techniques uniques */}
      <div className="app-kpi">
        <span className="app-kpi-label">Techniques MITRE</span>
        <span className="app-kpi-value" style={{ color: "#534AB7" }}>{techniques.size}</span>
        <span className="app-kpi-sub">techniques uniques mappées</span>
      </div>

    </div>
  );
}

// ── Matrice MITRE simplifiée ──────────────────────────────────────────────────

// Ordre canonique des tactiques MITRE ATT&CK Enterprise
const TACTIC_ORDER = [
  "Reconnaissance", "Resource Development", "Initial Access", "Execution",
  "Persistence", "Privilege Escalation", "Defense Evasion", "Credential Access",
  "Discovery", "Lateral Movement", "Collection", "Command and Control",
  "Exfiltration", "Impact",
];

function ScenarioMatrix({ items }) {
  if (!items || items.length === 0) return null;

  const COLLAPSE_THRESHOLD = 2;

  // Collecte toutes les techniques depuis les steps
  const byTactic = {};
  for (const s of items) {
    for (const st of s.steps) {
      if (!st.mitre_id) continue;
      const tactic = st.tactic || "Unknown";
      if (!byTactic[tactic]) byTactic[tactic] = new Map();
      if (!byTactic[tactic].has(st.mitre_id)) {
        byTactic[tactic].set(st.mitre_id, {
          mitre_id: st.mitre_id,
          name: st.technique_name || st.mitre_id,
          scenarios: [],
        });
      }
      byTactic[tactic].get(st.mitre_id).scenarios.push(s.name);
    }
  }

  // Tri des tactiques selon l'ordre canonique
  const tactics = [
    ...TACTIC_ORDER.filter(t => byTactic[t]),
    ...Object.keys(byTactic).filter(t => !TACTIC_ORDER.includes(t)),
  ];

  // Seuil de repli automatique
  const maxRows = tactics.length > 0
    ? Math.max(...tactics.map(t => byTactic[t].size))
    : 0;

  const [collapsed, setCollapsed] = useState(true);

  if (tactics.length === 0) return (
    <div className="card faint" style={{ fontSize: 13, marginBottom: 20 }}>
      Aucune technique mappée. Ajoutez des étapes à vos scénarios.
    </div>
  );

  return (
    <div style={{ marginBottom: 20 }}>
      {/* Header avec titre + bouton repli */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
        <h2 className="section-title" style={{ margin: 0, flex: 1 }}>
          Matrice MITRE ATT&amp;CK — couverture des scénarios
        </h2>
        <button
          className="matrix-collapse-btn"
          onClick={() => setCollapsed(c => !c)}
        >
          <span className={`matrix-chv${collapsed ? "" : " up"}`}>▾</span>
          {collapsed ? "Déplier" : "Replier"}
        </button>
      </div>

      {/* Corps de la matrice avec repli */}
      <div style={{ position: "relative" }}>
        <div
          className="matrix-wrap"
          style={{
            maxHeight: collapsed ? 130 : "none",
            overflow: collapsed ? "hidden" : "visible",
          }}
        >
          <div className="matrix-grid">
            {tactics.map(tactic => {
              const techs = [...byTactic[tactic].values()];
              return (
                <div className="matrix-col" key={tactic}>
                  <div className="matrix-col-head" title={tactic}>{tactic}</div>
                  <div className="matrix-cells">
                    {techs.map(t => (
                      <div
                        key={t.mitre_id}
                        className="matrix-cell scen-matrix-cell"
                        title={`${t.mitre_id} — ${t.name}\nScénarios : ${t.scenarios.join(", ")}`}
                      >
                        <span className="matrix-ttp">{t.mitre_id}</span>
                        <span className="matrix-tname">{t.name}</span>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 12 }}>
            <span style={{
              width: 13, height: 13, borderRadius: 4, display: "inline-block", flexShrink: 0,
              background: "rgba(83,74,183,.18)", border: "1px solid rgba(83,74,183,.55)",
            }} />
            <span style={{ fontSize: 12, color: "var(--text-dim)" }}>
              Technique présente dans au moins un scénario — survolez une cellule pour voir les scénarios associés
            </span>
          </div>
        </div>
        {/* Fondu de repli */}
        {collapsed && (
          <div style={{
            position: "absolute", bottom: 0, left: 0, right: 0, height: 56,
            background: "linear-gradient(transparent, var(--bg))",
            pointerEvents: "none",
          }} />
        )}
      </div>
    </div>
  );
}

// ── Composant principal ───────────────────────────────────────────────────────

export default function ManageScenarios() {
  const [items, setItems]         = useState(null);
  const [confirm, setConfirm]     = useState(null);
  const [drawer, setDrawer]       = useState(null);   // scenario object → vue détail
  const [createDrawer, setCreateDrawer] = useState(false); // drawer création
  const { show, node }            = useToast();

  const load = () => api.scenarios().then(setItems).catch(() => setItems([]));
  useEffect(() => { load(); }, []);

  async function doDelete() {
    try { await api.deleteScenario(confirm.id); show("Scénario supprimé"); setConfirm(null); load(); }
    catch (e) { show(e.message, "err"); setConfirm(null); }
  }

  return (
    <>
      <div className="page-head">
        <div className="page-eyebrow">Module 2 · CTI</div>
        <h1 className="page-title">Gestion des scénarios</h1>
        <p className="page-sub">
          Chaînes d'étapes mappées MITRE ATT&CK, réutilisables lors de la planification d'un audit.
        </p>
      </div>

      <div className="toolbar">
        <button className="btn btn-primary" onClick={() => setCreateDrawer(true)}>
          + Nouveau scénario
        </button>
      </div>

      {/* KPIs */}
      <ScenarioKpis items={items} />

      {/* Matrice MITRE */}
      {items && items.length > 0 && (
        <ScenarioMatrix items={items} />
      )}

      {/* Liste des scénarios */}
      {items && items.length > 0 && (
        <h2 className="section-title">Scénarios</h2>
      )}

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
              {items?.map(s => {
                const ec = ENGAGEMENT_COLORS[s.engagement_type] || {};
                return (
                  <tr key={s.id} className="clickable" onClick={() => setDrawer(s)}>
                    <td style={{ fontWeight: 600 }}>
                      {s.name}
                      {s.objective && (
                        <div className="faint" style={{ fontSize: 12, fontWeight: 400, marginTop: 3 }}>
                          {s.objective}
                        </div>
                      )}
                    </td>
                    <td><span className="badge violet">{s.threat_actor || "—"}</span></td>
                    <td>
                      <span style={{
                        fontSize: 11, fontWeight: 500, padding: "2px 7px", borderRadius: 5,
                        background: ec.bg, border: `0.5px solid ${ec.border}`, color: ec.text,
                        fontFamily: "var(--mono)",
                      }}>
                        {s.engagement_type}
                      </span>
                    </td>
                    <td className="wrap" style={{ maxWidth: 280 }}>
                      {s.steps.length
                        ? s.steps.map((st, i) => (
                            <span className="ttp" key={i} title={st.technique_name}>
                              {st.mitre_id || "—"}
                            </span>
                          ))
                        : <span className="faint">—</span>}
                    </td>
                    <td onClick={e => e.stopPropagation()}>
                      <div className="row-actions">
                        <button className="icon-btn danger" title="Supprimer" onClick={() => setConfirm(s)}>🗑</button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {confirm && (
        <ConfirmDialog
          message={`Supprimer le scénario « ${confirm.name} » ?`}
          onConfirm={doDelete}
          onCancel={() => setConfirm(null)}
        />
      )}

      {/* Drawer — Création */}
      <Drawer
        open={createDrawer}
        onClose={() => setCreateDrawer(false)}
        title="Nouveau scénario"
      >
        <ScenarioForm
          onSaved={() => { setCreateDrawer(false); load(); }}
          onCancel={() => setCreateDrawer(false)}
        />
      </Drawer>

      {/* Drawer — Détail / édition */}
      <Drawer
        open={drawer !== null}
        onClose={() => setDrawer(null)}
        title="Scénario CTI"
      >
        {drawer !== null && (
          <ScenarioDrawerContent
            scenario={drawer}
            onClose={() => setDrawer(null)}
            onUpdated={() => { load(); setDrawer(null); }}
          />
        )}
      </Drawer>

      {node}
    </>
  );
}
