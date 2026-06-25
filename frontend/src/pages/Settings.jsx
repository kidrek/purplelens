import { useEffect, useState } from "react";
import { useToast } from "../lib/useToast";

// Métadonnées statiques de chaque référentiel
const REF_META = {
  owasp: {
    label: "OWASP Top 10",
    desc: "Les 10 risques de sécurité applicatifs les plus critiques, publiés par l'OWASP Foundation. Utilisé dans le mapping des vulnérabilités.",
    badgeClass: "ref-badge ref-badge-owasp",
    source: "owasp.org / github.com/OWASP/Top10",
  },
  cwe: {
    label: "CWE — Common Weakness Enumeration",
    desc: "Catalogue des faiblesses logicielles et matérielles maintenu par MITRE. Référence standard pour la classification des vulnérabilités.",
    badgeClass: "ref-badge ref-badge-cwe",
    source: "cwe.mitre.org",
  },
  capec: {
    label: "CAPEC — Common Attack Pattern Enumeration",
    desc: "Catalogue des patrons d'attaque courants maintenu par MITRE. Permet de mapper les vulnérabilités aux vecteurs d'attaque connus.",
    badgeClass: "ref-badge ref-badge-capec",
    source: "capec.mitre.org",
  },
  cpe: {
    label: "CPE — Common Platform Enumeration",
    desc: "Nomenclature standard des systèmes, logiciels et paquets publiée par le NIST (NVD). Utilisé dans le champ Technologies des applications.",
    badgeClass: "ref-badge ref-badge-cpe",
    source: "nvd.nist.gov",
  },
};

function fmtDate(iso) {
  if (!iso) return "jamais";
  const d = new Date(iso);
  const now = new Date();
  const diff = Math.floor((now - d) / 1000);
  if (diff < 60) return "à l'instant";
  if (diff < 3600) return `il y a ${Math.floor(diff / 60)} min`;
  if (diff < 86400) return `il y a ${Math.floor(diff / 3600)} h`;
  if (diff < 86400 * 7) return `il y a ${Math.floor(diff / 86400)} j`;
  return d.toLocaleDateString("fr-FR");
}

function StatusDot({ synced }) {
  if (!synced) return <span className="settings-dot settings-dot-none" />;
  return <span className="settings-dot settings-dot-ok" />;
}

export default function Settings() {
  const [statuses, setStatuses] = useState(null);
  const [syncing, setSyncing] = useState({}); // { owasp: true, ... }
  const [syncingAll, setSyncingAll] = useState(false);
  const { show, node } = useToast();

  async function loadStatus() {
    try {
      const res = await fetch("/api/referentials/status");
      if (res.ok) setStatuses(await res.json());
    } catch (_) {}
    try {
      const res = await fetch("/api/referentials/mitre/status");
      if (res.ok) {
        const data = await res.json();
        setStatuses(prev => prev ? [...prev.filter(s => s.name !== "mitre_attack"), data] : [data]);
      }
    } catch (_) {}
  }

  useEffect(() => { loadStatus(); }, []);

  async function syncOne(name) {
    setSyncing(s => ({ ...s, [name]: true }));
    try {
      const res = await fetch(`/api/referentials/${name}/sync`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Erreur serveur");
      show(`${REF_META[name].label} mis à jour (${data.entry_count} entrées)`);
      await loadStatus();
    } catch (e) {
      show(`Erreur : ${e.message}`, "err");
    } finally {
      setSyncing(s => ({ ...s, [name]: false }));
    }
  }

  async function syncMitre() {
    setSyncing(s => ({ ...s, mitre: true }));
    try {
      const res = await fetch("/api/referentials/mitre/sync", { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Erreur serveur");
      show(`Catalogue ATT&CK mis à jour (${data.entry_count} techniques)`);
      await loadStatus();
    } catch (e) {
      show(`Erreur : ${e.message}`, "err");
    } finally {
      setSyncing(s => ({ ...s, mitre: false }));
    }
  }

  async function syncAll() {
    setSyncingAll(true);
    try {
      const res = await fetch("/api/referentials/sync-all", { method: "POST" });
      const data = await res.json();
      const ok = data.results?.length || 0;
      const err = data.errors?.length || 0;
      if (err > 0) {
        show(`${ok} référentiel(s) mis à jour, ${err} erreur(s)`, "err");
      } else {
        show(`Tous les référentiels sont à jour (${ok} synchronisés)`);
      }
      await loadStatus();
    } catch (e) {
      show(`Erreur : ${e.message}`, "err");
    } finally {
      setSyncingAll(false);
    }
  }

  function getStatus(name) {
    return statuses?.find(s => s.name === name) || null;
  }

  const anyBusy = syncingAll || Object.values(syncing).some(Boolean);

  function renderCard(name) {
    const st = getStatus(name);
    const meta = REF_META[name];
    const busy = syncing[name] || syncingAll;
    const imported = st && st.entry_count > 0;
    return (
      <div className="settings-card" key={name}>
        <div className="settings-card-icon">
          <span className={meta.badgeClass} style={{ fontSize: 11, padding: "5px 8px" }}>
            {name.toUpperCase()}
          </span>
        </div>
        <div className="settings-card-body">
          <div className="settings-card-name">{meta.label}</div>
          <div className="settings-card-desc">{meta.desc}</div>
          <div className="settings-card-meta">
            <span className="settings-meta-item">
              <StatusDot synced={imported} />
              {imported ? "En base" : "Non importé"}
            </span>
            {st?.version && (
              <span className="settings-meta-item">
                Version : <strong>{st.version}</strong>
              </span>
            )}
            {imported && (
              <span className="settings-meta-item">
                Entrées : <strong>{st.entry_count.toLocaleString("fr-FR")}</strong>
              </span>
            )}
            <span className="settings-meta-item">
              Mis à jour : <strong>{fmtDate(st?.synced_at)}</strong>
            </span>
            <span className="settings-meta-item settings-meta-source">
              Source : {meta.source}
            </span>
          </div>
        </div>
        <div className="settings-card-action">
          <button
            className={`btn ${imported ? "btn-ghost" : "btn-primary"}`}
            onClick={() => syncOne(name)}
            disabled={anyBusy}
            style={{ whiteSpace: "nowrap" }}
          >
            {busy && !syncingAll
              ? "Téléchargement…"
              : imported ? "↻  Mettre à jour" : "⬇  Importer"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="page-head">
        <div className="page-eyebrow">Paramètres</div>
        <h1 className="page-title">Référentiels de sécurité</h1>
        <p className="page-sub">
          Téléchargez et mettez à jour les référentiels locaux utilisés dans les formulaires.
          Une fois importés, PurpleLens fonctionne entièrement hors ligne.
        </p>
      </div>

      {/* Bouton global */}
      <div className="settings-global-bar">
        <div className="settings-global-text">
          <span className="settings-global-icon">⬇</span>
          <span>
            <strong>Tout mettre à jour</strong> — télécharge simultanément OWASP Top 10,
            CWE, CAPEC, CPE et le catalogue ATT&CK Enterprise depuis leurs sources officielles et met à jour la base locale.
          </span>
        </div>
        <button
          className="btn btn-primary"
          onClick={syncAll}
          disabled={anyBusy}
        >
          {syncingAll ? "Synchronisation…" : "↻  Tout mettre à jour"}
        </button>
      </div>

      <div className="settings-section-label">Référentiels de vulnérabilités</div>

      {(["owasp", "cwe", "capec"]).map(name => renderCard(name))}

      <div className="settings-section-label" style={{ marginTop: 28 }}>Référentiel de composants logiciels</div>

      {renderCard("cpe")}

      <div className="settings-info-box">
        <span className="settings-info-icon">ℹ</span>
        <div className="settings-info-text">
          La synchronisation nécessite un accès réseau vers les sources officielles
          (owasp.org, cwe.mitre.org, capec.mitre.org, nvd.nist.gov). Une fois les référentiels importés,
          la recherche dans les formulaires fonctionne entièrement hors ligne.
          En l'absence d'import, un jeu de données intégré est utilisé automatiquement.
        </div>
      </div>

      <hr style={{ border: "none", borderTop: "1px solid var(--line)", margin: "24px 0" }} />

      <div className="settings-section-label">Catalogue MITRE ATT&CK</div>

      {(() => {
        const st = getStatus("mitre_attack");
        const imported = st && st.entry_count > 0;
        const busy = syncing.mitre;
        return (
          <div className="settings-card">
            <div className="settings-card-icon">
              <span className="ref-badge" style={{
                fontSize: 11, padding: "5px 8px", fontFamily: "var(--mono)",
                fontWeight: 600, background: "rgba(226,75,74,.1)",
                color: "#A32D2D", border: "1px solid rgba(226,75,74,.4)",
                borderRadius: 5
              }}>ATT&CK</span>
            </div>
            <div className="settings-card-body">
              <div className="settings-card-name">MITRE ATT&CK Enterprise</div>
              <div className="settings-card-desc">
                Catalogue complet des techniques adversariales MITRE ATT&CK Enterprise.
                Utilisé comme dénominateur pour calculer le vrai taux de couverture ATT&CK
                de chaque application (techniques testées / total catalogue).
              </div>
              <div className="settings-card-meta">
                <span className="settings-meta-item">
                  <span className={`settings-dot ${imported ? "settings-dot-ok" : "settings-dot-none"}`} />
                  {imported ? "En base" : "Non importé"}
                </span>
                {st?.version && (
                  <span className="settings-meta-item">
                    Version : <strong>{st.version}</strong>
                  </span>
                )}
                {imported && (
                  <>
                    <span className="settings-meta-item">
                      Techniques : <strong>{st.entry_count?.toLocaleString("fr-FR")}</strong>
                    </span>
                    {st.parent_count && (
                      <span className="settings-meta-item">
                        Dont parentes : <strong>{st.parent_count?.toLocaleString("fr-FR")}</strong>
                      </span>
                    )}
                  </>
                )}
                <span className="settings-meta-item">
                  Mis à jour : <strong>{fmtDate(st?.synced_at)}</strong>
                </span>
                <span className="settings-meta-item settings-meta-source">
                  Source : github.com/mitre/cti
                </span>
              </div>
            </div>
            <div className="settings-card-action">
              <button
                className={`btn ${imported ? "btn-ghost" : "btn-primary"}`}
                onClick={syncMitre}
                disabled={anyBusy}
                style={{ whiteSpace: "nowrap" }}
              >
                {busy ? "Téléchargement…" : imported ? "↻  Mettre à jour" : "⬇  Importer"}
              </button>
            </div>
          </div>
        );
      })()}

      <div className="settings-info-box" style={{ marginTop: 12 }}>
        <span className="settings-info-icon">ℹ</span>
        <div className="settings-info-text">
          Le catalogue ATT&CK Enterprise contient environ <strong>200 techniques parentes</strong> et
          plus de <strong>400 sous-techniques</strong>. Le téléchargement depuis GitHub MITRE/CTI
          peut prendre quelques secondes. Le KPI de couverture dans les fiches applications
          utilise uniquement les techniques parentes comme dénominateur.
        </div>
      </div>

      {node}
    </>
  );
}
