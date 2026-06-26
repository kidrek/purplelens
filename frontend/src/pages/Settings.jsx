import { useEffect, useState } from "react";
import { useToast } from "../lib/useToast";

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
  const diff = Math.floor((new Date() - d) / 1000);
  if (diff < 60)    return "à l'instant";
  if (diff < 3600)  return `il y a ${Math.floor(diff / 60)} min`;
  if (diff < 86400) return `il y a ${Math.floor(diff / 3600)} h`;
  if (diff < 86400 * 7) return `il y a ${Math.floor(diff / 86400)} j`;
  return d.toLocaleDateString("fr-FR");
}

function StatusDot({ synced }) {
  return <span className={`settings-dot ${synced ? "settings-dot-ok" : "settings-dot-none"}`} />;
}

export default function Settings() {
  const [statuses, setStatuses]     = useState(null);
  const [syncing, setSyncing]       = useState({});
  const [syncingAll, setSyncingAll] = useState(false);
  const [d3fendStatus, setD3fendStatus] = useState(null);
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
        setStatuses(prev => prev
          ? [...prev.filter(s => s.name !== "mitre_attack"), data]
          : [data]);
      }
    } catch (_) {}
    try {
      const res = await fetch("/api/referentials/d3fend/status");
      if (res.ok) setD3fendStatus(await res.json());
    } catch (_) {}
  }

  useEffect(() => { loadStatus(); }, []);

  // ── Sync individuel (OWASP/CWE/CAPEC/CPE) ────────────────────────────────
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

  // ── Sync ATT&CK ───────────────────────────────────────────────────────────
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

  // ── Sync D3FEND (téléchargement automatique) ─────────────────────────────
  async function syncD3fend() {
    setSyncing(s => ({ ...s, d3fend: true }));
    try {
      const res = await fetch("/api/referentials/d3fend/sync", { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Erreur serveur");
      show(`D3FEND synchronisé — ${data.entry_count} mappings, ${data.attack_techniques_covered} techniques ATT&CK couvertes`);
      await loadStatus();
    } catch (e) {
      show(`Erreur D3FEND : ${e.message}`, "err");
    } finally {
      setSyncing(s => ({ ...s, d3fend: false }));
    }
  }

  // ── Tout mettre à jour ────────────────────────────────────────────────────
  async function syncAll() {
    setSyncingAll(true);
    try {
      const res  = await fetch("/api/referentials/sync-all", { method: "POST" });
      const data = await res.json();
      const ok   = data.results?.length || 0;
      const err  = data.errors?.length  || 0;
      if (err > 0) {
        show(`${ok} référentiel(s) mis à jour, ${err} erreur(s)`, "err");
      } else {
        show(`${ok} référentiels synchronisés avec succès`);
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

  // ── Carte référentiel générique ───────────────────────────────────────────
  function renderCard(name) {
    const st       = getStatus(name);
    const meta     = REF_META[name];
    const busy     = syncing[name] || syncingAll;
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
              <span className="settings-meta-item">Version : <strong>{st.version}</strong></span>
            )}
            {imported && (
              <span className="settings-meta-item">
                Entrées : <strong>{st.entry_count.toLocaleString("fr-FR")}</strong>
              </span>
            )}
            <span className="settings-meta-item">
              Mis à jour : <strong>{fmtDate(st?.synced_at)}</strong>
            </span>
            <span className="settings-meta-item settings-meta-source">Source : {meta.source}</span>
          </div>
        </div>
        <div className="settings-card-action">
          <button
            className={`btn ${imported ? "btn-ghost" : "btn-primary"}`}
            onClick={() => syncOne(name)}
            disabled={anyBusy}
            style={{ whiteSpace: "nowrap" }}
          >
            {busy && !syncingAll ? "Téléchargement…" : imported ? "↻  Mettre à jour" : "⬇  Importer"}
          </button>
        </div>
      </div>
    );
  }

  // ── Page ──────────────────────────────────────────────────────────────────
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

      {/* ── Bouton global ── */}
      <div className="settings-global-bar">
        <div className="settings-global-text">
          <span className="settings-global-icon">⬇</span>
          <span>
            <strong>Tout mettre à jour</strong> — synchronise automatiquement OWASP, CWE, CAPEC,
            CPE, ATT&CK Enterprise et D3FEND.
          </span>
        </div>
        <button className="btn btn-primary" onClick={syncAll} disabled={anyBusy}>
          {syncingAll ? "Synchronisation…" : "↻  Tout mettre à jour"}
        </button>
      </div>

      {/* ── Référentiels vulnérabilités ── */}
      <div className="settings-section-label">Référentiels de vulnérabilités</div>
      {["owasp", "cwe", "capec"].map(name => renderCard(name))}

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

      {/* ── ATT&CK ── */}
      <div className="settings-section-label">Catalogue MITRE ATT&CK</div>
      {(() => {
        const st       = getStatus("mitre_attack");
        const imported = st && st.entry_count > 0;
        const busy     = syncing.mitre;
        return (
          <div className="settings-card">
            <div className="settings-card-icon">
              <span className="ref-badge" style={{
                fontSize: 11, padding: "5px 8px", fontFamily: "var(--mono)",
                fontWeight: 600, background: "rgba(226,75,74,.1)",
                color: "#A32D2D", border: "1px solid rgba(226,75,74,.4)", borderRadius: 5,
              }}>ATT&CK</span>
            </div>
            <div className="settings-card-body">
              <div className="settings-card-name">MITRE ATT&CK Enterprise</div>
              <div className="settings-card-desc">
                Catalogue complet des techniques adversariales MITRE ATT&CK Enterprise.
                Utilisé comme dénominateur pour le KPI de couverture ATT&CK et comme source
                de recherche dans le formulaire des scénarios.
              </div>
              <div className="settings-card-meta">
                <span className="settings-meta-item">
                  <StatusDot synced={imported} />
                  {imported ? "En base" : "Non importé"}
                </span>
                {st?.version && <span className="settings-meta-item">Version : <strong>{st.version}</strong></span>}
                {imported && (
                  <>
                    <span className="settings-meta-item">Techniques : <strong>{st.entry_count?.toLocaleString("fr-FR")}</strong></span>
                    {st.parent_count && <span className="settings-meta-item">Dont parentes : <strong>{st.parent_count?.toLocaleString("fr-FR")}</strong></span>}
                  </>
                )}
                <span className="settings-meta-item">Mis à jour : <strong>{fmtDate(st?.synced_at)}</strong></span>
                <span className="settings-meta-item settings-meta-source">Source : github.com/mitre/cti</span>
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

      <hr style={{ border: "none", borderTop: "1px solid var(--line)", margin: "24px 0" }} />

      {/* ── D3FEND ── */}
      <div className="settings-section-label">MITRE D3FEND</div>

      <div className="settings-card">
        <div className="settings-card-icon">
          <span className="ref-badge" style={{
            fontSize: 11, padding: "5px 8px", fontFamily: "var(--mono)",
            fontWeight: 600, background: "rgba(29,158,117,.1)",
            color: "#0F6E56", border: "1px solid rgba(29,158,117,.4)", borderRadius: 5,
          }}>D3FEND</span>
        </div>
        <div className="settings-card-body">
          <div className="settings-card-name">MITRE D3FEND — Contre-mesures défensives</div>
          <div className="settings-card-desc">
            Mapping des techniques ATT&CK vers les contre-mesures défensives D3FEND (Harden, Detect,
            Isolate, Deceive, Evict, Restore). Utilisé dans le formulaire des scénarios pour suggérer
            automatiquement les mesures défensives associées à chaque étape offensive.
          </div>
          <div className="settings-card-meta">
            <span className="settings-meta-item">
              <StatusDot synced={d3fendStatus?.entry_count > 0} />
              {d3fendStatus?.entry_count > 0 ? "En base" : "Non importé"}
            </span>
            {d3fendStatus?.entry_count > 0 && (
              <>
                <span className="settings-meta-item">
                  Mappings : <strong>{d3fendStatus.entry_count.toLocaleString("fr-FR")}</strong>
                </span>
                <span className="settings-meta-item">
                  Techniques ATT&CK couvertes : <strong>{d3fendStatus.attack_techniques_covered}</strong>
                </span>
              </>
            )}
            <span className="settings-meta-item">
              Importé : <strong>{fmtDate(d3fendStatus?.synced_at)}</strong>
            </span>
            <span className="settings-meta-item settings-meta-source">
              Source : d3fend.mitre.org/ontologies/d3fend.json
            </span>
          </div>
        </div>
        <div className="settings-card-action">
          <button
            className={`btn ${d3fendStatus?.entry_count > 0 ? "btn-ghost" : "btn-primary"}`}
            onClick={syncD3fend}
            disabled={anyBusy}
            style={{ whiteSpace: "nowrap" }}
          >
            {syncing.d3fend
              ? "Téléchargement…"
              : d3fendStatus?.entry_count > 0
                ? "↻  Mettre à jour"
                : "⬇  Importer"}
          </button>
        </div>
      </div>

      <div className="settings-info-box" style={{ marginTop: 12 }}>
        <span className="settings-info-icon">ℹ</span>
        <div className="settings-info-text">
          Le catalogue D3FEND est téléchargé automatiquement depuis{" "}
          <a href="https://d3fend.mitre.org/ontologies/d3fend.json" target="_blank" rel="noopener noreferrer"
            style={{ color: "var(--violet-bright)" }}>d3fend.mitre.org/ontologies/d3fend.json</a>.
          En l'absence d'import, un mapping statique intégré de{" "}
          <strong>44 techniques</strong> est utilisé automatiquement dans le formulaire des scénarios.
        </div>
      </div>

      {node}
    </>
  );
}
