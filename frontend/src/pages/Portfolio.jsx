import { useEffect, useState } from "react";
import {
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  Radar,
} from "recharts";
import { api } from "../api/client";
import { KpiTile, ScorePill, DIC } from "../components/Shared";
import { scoreColor } from "../lib/format";

export default function Portfolio({ onSelectApp }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    api.portfolio().then(setData).catch((e) => setErr(e.message));
  }, []);

  if (err) return <div className="empty">Erreur de chargement : {err}</div>;
  if (!data) return <div className="loading">Calcul des scores…</div>;

  const s = data.summary;

  // Radar : couverture moyenne sur les 3 axes
  const radar = [
    { axis: "Couverture ATT&CK", val: s.avg_attack_coverage_pct },
    { axis: "Détection", val: s.avg_detection_coverage_pct },
    { axis: "Réaction", val: s.avg_response_coverage_pct },
  ];

  return (
    <>
      <div className="page-head">
        <div className="page-eyebrow">Cockpit Purple Team</div>
        <h1 className="page-title">Posture de résilience</h1>
        <p className="page-sub">
          Sommes-nous capables de détecter et réagir aux scénarios de menace qui
          ciblent réellement nos applications critiques ? Voici la réponse,
          application par application.
        </p>
      </div>

      <div className="kpi-row" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <KpiTile name="Applications suivies" value={s.applications_count} />
        <KpiTile
          name="Couverture ATT&CK moy."
          value={s.avg_attack_coverage_pct}
          unit="%"
          pct={s.avg_attack_coverage_pct}
        />
        <KpiTile
          name="Détection moy."
          value={s.avg_detection_coverage_pct}
          unit="%"
          pct={s.avg_detection_coverage_pct}
        />
        <KpiTile
          name="Réaction moy."
          value={s.avg_response_coverage_pct}
          unit="%"
          pct={s.avg_response_coverage_pct}
        />
      </div>

      <div
        className="grid"
        style={{ gridTemplateColumns: "1.6fr 1fr", marginTop: 16, alignItems: "stretch" }}
      >
        <div className="card">
          <div className="flex between center" style={{ marginBottom: 6 }}>
            <span className="card-label">Portefeuille applicatif</span>
            <span className="faint" style={{ fontSize: 12 }}>
              {s.open_critical} critiques · {s.open_high} élevées ouvertes
            </span>
          </div>
          <table>
            <thead>
              <tr>
                <th>Application</th>
                <th>Exposition</th>
                <th>DIC</th>
                <th>ATT&CK</th>
                <th>Détection</th>
                <th>Réaction</th>
                <th>Vulns</th>
              </tr>
            </thead>
            <tbody>
              {data.applications.map((a) => (
                <tr
                  key={a.application_id}
                  className="clickable"
                  onClick={() => onSelectApp(a.application_id)}
                >
                  <td style={{ fontWeight: 600 }}>{a.application_name}</td>
                  <td>
                    <span className="badge violet">{a.exposure}</span>
                  </td>
                  <td>
                    <DIC dic={a.dic} />
                  </td>
                  <td>
                    <ScorePill pct={a.kpis.attack_coverage_pct} />
                  </td>
                  <td>
                    <ScorePill pct={a.kpis.detection_coverage_pct} />
                  </td>
                  <td>
                    <ScorePill pct={a.kpis.response_coverage_pct} />
                  </td>
                  <td className="mono">
                    {a.vulnerabilities.Critical > 0 && (
                      <span style={{ color: "var(--coral)" }}>
                        {a.vulnerabilities.Critical}C{" "}
                      </span>
                    )}
                    {a.vulnerabilities.High > 0 && (
                      <span style={{ color: "var(--amber)" }}>
                        {a.vulnerabilities.High}H
                      </span>
                    )}
                    {a.vulnerabilities.Critical === 0 &&
                      a.vulnerabilities.High === 0 && (
                        <span className="faint">—</span>
                      )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card">
          <span className="card-label">Couverture moyenne</span>
          <div style={{ height: 240, marginTop: 8 }}>
            <ResponsiveContainer>
              <RadarChart data={radar} outerRadius="72%">
                <PolarGrid stroke="var(--line)" />
                <PolarAngleAxis
                  dataKey="axis"
                  tick={{ fill: "var(--text-dim)", fontSize: 11 }}
                />
                <Radar
                  dataKey="val"
                  stroke="var(--violet-bright)"
                  fill="var(--violet)"
                  fillOpacity={0.35}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>
          <p className="faint" style={{ fontSize: 12, lineHeight: 1.5 }}>
            L'écart entre détection et réaction révèle la maturité du couple
            SOC / CERT. Cliquez une application pour le détail.
          </p>
        </div>
      </div>
    </>
  );
}
