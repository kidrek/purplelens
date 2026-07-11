"""Génération de livrables (cahier §5) : lettre d'engagement, NDA, rapport PTES.

Chaîne : gabarit HTML → PDF via Chromium headless (service `pdf-renderer` du
compose). Règles de sécurité :
  - TLP/client marqués en pied de page (bandeau de classification) ;
  - les preuves marquées `contains_secrets` ne sont JAMAIS intégrées en clair :
    on insère un marqueur masqué + renvoi vers la custody (spec preuves, porte 5).
Le rendu tourne sous le rôle de service `report_render` (périmètre minimal).
"""
from __future__ import annotations

import html
from datetime import UTC, datetime

from fastapi import FastAPI, Response
from pydantic import BaseModel

_TLP_COLORS = {
    "RED": "#D32F2F",
    "AMBER": "#F59E0B",
    "AMBER+STRICT": "#B45309",
    "GREEN": "#2E7D32",
    "CLEAR": "#455A64",
}


def _banner(tlp: str, client_name: str) -> str:
    color = _TLP_COLORS.get(tlp.upper(), "#455A64")
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f'<div class="tlp-banner" style="background:{color}">'
        f"TLP:{html.escape(tlp)} — {html.escape(client_name)} — {stamp}"
        f"</div>"
    )


_BASE_CSS = """
<style>
  @page { margin: 24mm 18mm; }
  body { font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif; color: #1A1626;
         font-size: 11pt; line-height: 1.5; }
  h1 { color: #4C1D95; font-size: 20pt; margin-bottom: 4px; }
  h2 { color: #6D28D9; font-size: 14pt; border-bottom: 2px solid #EDE9FE;
       padding-bottom: 4px; margin-top: 22px; }
  h3 { color: #4C1D95; font-size: 11.5pt; margin: 14px 0 4px; }
  .tlp-banner { color: white; font-weight: 700; padding: 6px 12px; border-radius: 6px;
                text-align: center; letter-spacing: 0.06em; margin-bottom: 18px; }
  .meta { color: #6B6580; font-size: 9pt; }
  .masked { background: #EDE9FE; color: #6D28D9; padding: 2px 8px; border-radius: 4px;
            font-style: italic; }
  table { width: 100%; border-collapse: collapse; margin: 10px 0; }
  th, td { border: 1px solid #E5E1F0; padding: 6px 8px; text-align: left; font-size: 10pt; }
  th { background: #F4F2F9; color: #4C1D95; }
  table.kv td:first-child { width: 34%; background: #FBFAFD; color: #4C1D95;
                            font-weight: 600; }
  .sev-critique { color: #D32F2F; font-weight: 700; }
  .sev-haute { color: #E65100; font-weight: 600; }
  .footer { color: #9B95AD; font-size: 8pt; text-align: center; margin-top: 30px; }
  .callout { background: #FFF7E6; border: 1px solid #F2D399; border-radius: 6px;
             padding: 8px 12px; font-size: 10pt; margin: 10px 0; }
  .sig-row { display: flex; gap: 24px; margin-top: 36px; }
  .sig-box { flex: 1; border: 1px solid #E5E1F0; border-radius: 6px; padding: 12px;
             min-height: 90px; font-size: 9.5pt; color: #6B6580; }
  .sig-box b { color: #1A1626; display: block; margin-bottom: 28px; }
  ul.compact { margin: 4px 0 10px; padding-left: 20px; }
  ul.compact li { margin: 2px 0; }
  .pill { display: inline-block; border: 1px solid #DDD6F3; border-radius: 999px;
          padding: 1px 10px; font-size: 9pt; color: #4C1D95; background: #F4F2F9;
          margin-right: 4px; }
</style>
"""


def _esc(v) -> str:
    """Échappe une valeur possiblement None/non-str."""
    return html.escape(str(v)) if v not in (None, "") else ""


def _dt(v) -> str:
    """Format lisible d'une date (str ISO ou date), '—' si absente."""
    if not v:
        return "—"
    return html.escape(str(v))


def _ul(items: list | None, empty: str = "—") -> str:
    """Liste HTML à partir d'une liste de chaînes (champ `lines` du bloc engagement)."""
    items = [i for i in (items or []) if str(i).strip()]
    if not items:
        return f"<p>{html.escape(empty)}</p>"
    lis = "".join(f"<li>{html.escape(str(i))}</li>" for i in items)
    return f'<ul class="compact">{lis}</ul>'


def _para(v, empty: str = "—") -> str:
    """Paragraphe(s) à partir d'un champ texte libre (retours ligne préservés)."""
    if not v or not str(v).strip():
        return f"<p>{html.escape(empty)}</p>"
    parts = [html.escape(p.strip()) for p in str(v).split("\n") if p.strip()]
    return "".join(f"<p>{p}</p>" for p in parts)


def _kv_table(rows: list[tuple[str, str]]) -> str:
    """Tableau clé/valeur pour les blocs de métadonnées."""
    trs = "".join(
        f"<tr><td>{html.escape(k)}</td><td>{v or '—'}</td></tr>" for k, v in rows
    )
    return f'<table class="kv"><tbody>{trs}</tbody></table>'


def _sig_block(prestataire: str, client: str) -> str:
    """Bloc de signatures côte à côte (prestataire / client)."""
    return (
        '<div class="sig-row">'
        f'<div class="sig-box"><b>Pour le prestataire — {html.escape(prestataire or "Prestataire")}</b>'
        "Nom, fonction, date et signature :</div>"
        f'<div class="sig-box"><b>Pour le client — {html.escape(client)}</b>'
        "Nom, fonction, date et signature :</div>"
        "</div>"
    )


def _mask_if_secret(item: dict) -> str:
    """Une preuve `contains_secrets` n'apparaît jamais en clair dans un rapport."""
    if item.get("contains_secrets"):
        return '<span class="masked">[preuve masquée — voir chaîne de custody]</span>'
    return html.escape(item.get("caption") or item.get("original_filename", "preuve"))


def render_engagement_letter(*, client: dict, prestataire: dict | None, audit: dict,
                             engagement: dict, scenario: dict | None,
                             applications: list[dict], auditeurs: list[dict],
                             tlp: str) -> str:
    """Lettre d'engagement complète (cahier §5.A) : reprend l'intégralité du bloc
    `audit.engagement` saisi dans l'outil, plus les métadonnées de mission (audit,
    scénario, applications ciblées, équipe assignée, organisations)."""
    client_name = client.get("nom", "")
    presta_name = (prestataire or {}).get("nom") or "Prestataire Purple Team"

    # Applications ciblées : tableau criticité/exposition.
    app_rows = "".join(
        f"<tr><td>{_esc(a.get('nom'))}</td><td>{_esc(a.get('version')) or '—'}</td>"
        f"<td>{_esc(a.get('criticite')) or '—'}</td><td>{_esc(a.get('exposition')) or '—'}</td>"
        f"<td>{_esc(a.get('environnement') or audit.get('environnement')) or '—'}</td></tr>"
        for a in applications
    )
    apps_html = (
        f"<table><thead><tr><th>Application</th><th>Version</th><th>Criticité</th>"
        f"<th>Exposition</th><th>Environnement</th></tr></thead><tbody>{app_rows}</tbody></table>"
        if app_rows else "<p>Aucune application référencée — voir périmètre ci-dessus.</p>"
    )

    # Équipe assignée.
    team_rows = "".join(
        f"<tr><td>{_esc(r.get('nom'))}</td><td>{_esc(r.get('role')) or '—'}</td>"
        f"<td>{_esc(', '.join(r.get('competences') or [])) or '—'}</td>"
        f"<td>{_esc(r.get('contact')) or '—'}</td></tr>"
        for r in auditeurs
    )
    team_html = (
        f"<table><thead><tr><th>Intervenant</th><th>Rôle</th><th>Compétences</th>"
        f"<th>Contact</th></tr></thead><tbody>{team_rows}</tbody></table>"
        if team_rows else "<p>Équipe communiquée avant le démarrage de la mission.</p>"
    )

    # Contexte scénario (Purple/Red) le cas échéant.
    scenario_html = ""
    if scenario:
        techniques = scenario.get("techniques") or []
        tech_pills = "".join(f'<span class="pill">{_esc(t)}</span>' for t in techniques[:12])
        more = f" <span class='meta'>(+{len(techniques)-12})</span>" if len(techniques) > 12 else ""
        scenario_html = (
            "<h2>3. Scénario de menace émulé</h2>"
            + _kv_table([
                ("Scénario", _esc(scenario.get("nom"))),
                ("Acteur émulé", _esc(scenario.get("acteur_emule")) or "—"),
                ("Type d'engagement", _esc(scenario.get("type_engagement")) or "—"),
                ("Sophistication", _esc(scenario.get("sophistication")) or "—"),
                ("Objectif", _esc(scenario.get("objectif")) or "—"),
            ])
            + (f"<h3>Techniques MITRE ATT&amp;CK couvertes</h3><p>{tech_pills}{more}</p>" if tech_pills else "")
        )

    referentiels = ", ".join(audit.get("referentiels_methodo") or []) or "PTES"
    sec = 4 if scenario else 3  # numérotation dynamique des sections suivantes

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_BASE_CSS}</head><body>
    {_banner(tlp, client_name)}
    <h1>Lettre d'engagement</h1>
    <p class="meta">Mission : {_esc(audit.get('nom'))} — Catégorie {_esc(audit.get('categorie'))}
    {('· ' + _esc(audit.get('type_test'))) if audit.get('type_test') else ''}
    · Référentiels : {_esc(referentiels)}</p>

    <h2>1. Parties</h2>
    {_kv_table([
        ("Prestataire", _esc(presta_name)),
        ("Client", _esc(client_name) + (f" — SIREN {_esc(client.get('siren'))}" if client.get('siren') else "")),
        ("Secteur du client", _esc(client.get('secteur')) or "—"),
        ("Référent client", _esc(client.get('referent_interne')) or "—"),
        ("Référence SOW", _esc(engagement.get('sow')) or "—"),
        ("Référence NDA", _esc(engagement.get('ref_nda')) or "—"),
        ("Autorisation signée", "Oui" if engagement.get('autorisation_signee') else "Non — à signer avant tout test"),
    ])}
    {'' if engagement.get('autorisation_signee') else '<div class="callout">⚠ Aucun test ne peut démarrer avant la signature de la présente autorisation par un représentant habilité du client.</div>'}

    <h2>2. Objectifs et périmètre</h2>
    <h3>Objectifs de la mission</h3>
    {_ul(engagement.get('objectifs'), "Objectifs définis conjointement au cadrage.")}
    <h3>Périmètre inclus</h3>
    {_ul(engagement.get('perimetre_inclus'), "Périmètre détaillé en annexe du SOW.")}
    <h3>Périmètre explicitement exclu</h3>
    {_ul(engagement.get('perimetre_exclus'), "Aucune exclusion déclarée — toute cible hors périmètre inclus reste proscrite.")}
    <h3>Applications ciblées</h3>
    {apps_html}

    {scenario_html}

    <h2>{sec}. Fenêtres d'intervention</h2>
    {_kv_table([
        ("Dates de la mission", f"{_dt(audit.get('date_debut'))} → {_dt(audit.get('date_fin'))}"),
        ("Environnement", _esc(audit.get('environnement')) or "—"),
        ("Niveau d'intensité", _esc(engagement.get('niveau_intensite')) or "Standard"),
    ])}
    <h3>Fenêtres de test autorisées</h3>
    {_ul(engagement.get('fenetres_test'), "Fenêtres à convenir avec les contacts d'autorisation.")}

    <h2>{sec+1}. Règles d'engagement</h2>
    {_para(engagement.get('regles_engagement'),
           "Conformité " + referentiels + ". Toute action hors périmètre est proscrite. "
           "Les preuves collectées sont chiffrées, horodatées et conservées selon la politique de rétention.")}

    <h2>{sec+2}. Contacts</h2>
    <h3>Contacts d'autorisation</h3>
    {_ul(engagement.get('contacts_autorisation'), "À désigner avant le démarrage.")}
    <h3>Contacts d'urgence (arrêt immédiat)</h3>
    {_ul(engagement.get('contacts_urgence'), "À désigner avant le démarrage.")}

    <h2>{sec+3}. Équipe d'audit assignée</h2>
    {team_html}

    <h2>{sec+4}. Livrables attendus</h2>
    {_ul(engagement.get('livrables_attendus'), "Rapport de mission et restitution — liste détaillée au SOW.")}

    <h2>{sec+5}. Clauses légales</h2>
    {_para(engagement.get('clauses_legales'),
           "Les tests sont réalisés dans le strict cadre de l'autorisation ci-dessus. "
           "Le prestataire s'engage à la confidentialité (voir NDA référencé) et à la "
           "non-destruction ; le client garantit être titulaire des droits sur les systèmes ciblés.")}

    {_sig_block(presta_name, client_name)}
    <div class="footer">Document généré par Purple Cockpit — TLP:{_esc(tlp)} — diffusion restreinte aux parties</div>
    </body></html>"""


def render_nda(*, client: dict, prestataire: dict | None, engagement: dict,
               audit: dict | None, tlp: str) -> str:
    """Accord de confidentialité complet : reprend les cinq clauses NDA saisies dans
    le bloc engagement (objet, durée, traitement, restitution, droit applicable)."""
    client_name = client.get("nom", "")
    presta_name = (prestataire or {}).get("nom") or "Prestataire Purple Team"
    engagement = engagement or {}
    mission = _esc((audit or {}).get("nom")) if audit else ""

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_BASE_CSS}</head><body>
    {_banner(tlp, client_name)}
    <h1>Accord de confidentialité (NDA)</h1>
    {f'<p class="meta">Rattaché à la mission : {mission}</p>' if mission else ''}

    <h2>1. Parties</h2>
    {_kv_table([
        ("Partie divulgatrice / réceptrice", "Réciproque — chaque partie est tour à tour divulgatrice et réceptrice"),
        ("Prestataire", _esc(presta_name)),
        ("Client", _esc(client_name) + (f" — SIREN {_esc(client.get('siren'))}" if client.get('siren') else "")),
        ("Référence", _esc(engagement.get('ref_nda')) or "—"),
    ])}

    <h2>2. Objet et informations confidentielles</h2>
    {_para(engagement.get('nda_objet'),
           "Sont confidentielles toutes informations techniques, organisationnelles ou "
           "commerciales échangées dans le cadre de la mission : architecture, vulnérabilités "
           "découvertes, preuves d'exploitation, identifiants, données métier, ainsi que "
           "l'existence et le contenu des livrables.")}

    <h2>3. Durée</h2>
    {_para(engagement.get('nda_duree'),
           "Les obligations de confidentialité s'appliquent pendant la mission et perdurent "
           "après son terme, y compris après restitution ou destruction des informations.")}

    <h2>4. Traitement et protection des informations</h2>
    {_para(engagement.get('nda_traitement'),
           "Les informations sont marquées et manipulées selon le protocole TLP (Traffic Light "
           "Protocol) ; les preuves sont chiffrées, horodatées et stockées dans un coffre "
           "inaltérable avec journal d'accès nominatif. L'accès est limité au strict besoin "
           "d'en connaître au sein de l'équipe assignée.")}

    <h2>5. Restitution et destruction</h2>
    {_para(engagement.get('nda_restitution'),
           "En fin de mission, les informations confidentielles sont restituées ou détruites "
           "par crypto-effacement (destruction des clés de chiffrement), la trace de "
           "destruction restant journalisée sans le contenu.")}

    <h2>6. Droit applicable</h2>
    {_para(engagement.get('nda_droit'),
           "Le présent accord est régi par le droit applicable convenu entre les parties ; "
           "tout litige relève des juridictions compétentes du ressort du client.")}

    <h2>7. Marquage TLP de la mission</h2>
    <p>Sauf mention contraire par document, les échanges de la mission sont marqués
    <strong>TLP:{_esc(tlp)}</strong> — la diffusion suit strictement les règles de ce niveau.</p>

    {_sig_block(presta_name, client_name)}
    <div class="footer">Document généré par Purple Cockpit — TLP:{_esc(tlp)} — diffusion restreinte aux parties</div>
    </body></html>"""


def render_ptes_report(*, client: dict, prestataire: dict | None, audit: dict,
                       scenario: dict | None, applications: list[dict],
                       auditeurs: list[dict], actions: list[dict],
                       findings: list[dict], evidence: list[dict], tlp: str) -> str:
    """Rapport PTES complet. Les preuves secrètes restent masquées (porte 5)."""
    client_name = client.get("nom", "")
    presta_name = (prestataire or {}).get("nom") or "Prestataire Purple Team"
    referentiels = ", ".join(audit.get("referentiels_methodo") or []) or "PTES"

    # ── Synthèse chiffrée par sévérité ──
    sev_order = ["critique", "haute", "moyenne", "basse", "info"]
    sev_count: dict[str, int] = {}
    for f in findings:
        s = str(f.get("severite") or "info").lower()
        sev_count[s] = sev_count.get(s, 0) + 1
    stat_cells = "".join(
        f"<td class='sev-{s}'><strong>{sev_count.get(s, 0)}</strong> {s}</td>"
        for s in sev_order if s in sev_count
    ) or "<td>Aucune vulnérabilité enregistrée</td>"

    # ── Vulnérabilités détaillées ──
    rows = "".join(
        f"<tr><td>{_esc(f.get('titre'))}"
        + (f"<br><span class='meta'>{_esc(f.get('cve'))}</span>" if f.get('cve') else "")
        + f"</td><td>{_esc(f.get('cvss_score')) or '—'}</td>"
        f"<td class='sev-{_esc(str(f.get('severite','')).lower())}'>{_esc(f.get('severite')) or '—'}</td>"
        f"<td>{_esc(f.get('epss')) or '—'}</td>"
        f"<td>{'Oui' if f.get('kev') else '—'}</td>"
        f"<td>{_esc(f.get('sla_niveau')) or '—'}</td>"
        f"<td>{_esc(f.get('statut')) or '—'}</td></tr>"
        for f in findings
    )

    # ── Actions d'audit par phase PTES ──
    actions_html = ""
    if actions:
        act_rows = "".join(
            f"<tr><td>{_esc(a.get('ptes_phase')) or '—'}</td><td>{_esc(a.get('titre'))}</td>"
            f"<td>{_esc(a.get('technique_attack')) or '—'}</td>"
            f"<td>{_esc(a.get('outil')) or '—'}</td>"
            f"<td>{_esc(a.get('resultat')) or '—'}</td></tr>"
            for a in actions
        )
        actions_html = (
            "<h2>Actions d'audit réalisées</h2>"
            "<table><thead><tr><th>Phase PTES</th><th>Action</th><th>ATT&amp;CK</th>"
            f"<th>Outil</th><th>Résultat</th></tr></thead><tbody>{act_rows}</tbody></table>"
        )

    # ── Contexte scénario ──
    scenario_html = ""
    if scenario:
        techniques = scenario.get("techniques") or []
        tech_pills = "".join(f'<span class="pill">{_esc(t)}</span>' for t in techniques[:16])
        more = f" <span class='meta'>(+{len(techniques)-16})</span>" if len(techniques) > 16 else ""
        scenario_html = (
            "<h2>Scénario de menace émulé</h2>"
            + _kv_table([
                ("Scénario", _esc(scenario.get("nom"))),
                ("Acteur émulé", _esc(scenario.get("acteur_emule")) or "—"),
                ("Sophistication", _esc(scenario.get("sophistication")) or "—"),
                ("Objectif", _esc(scenario.get("objectif")) or "—"),
            ])
            + (f"<p>{tech_pills}{more}</p>" if tech_pills else "")
        )

    # ── Périmètre applicatif ──
    app_rows = "".join(
        f"<tr><td>{_esc(a.get('nom'))}</td><td>{_esc(a.get('criticite')) or '—'}</td>"
        f"<td>{_esc(a.get('exposition')) or '—'}</td><td>{_esc(a.get('stack')) or '—'}</td></tr>"
        for a in applications
    )
    apps_html = (
        "<h2>Périmètre applicatif</h2><table><thead><tr><th>Application</th><th>Criticité</th>"
        f"<th>Exposition</th><th>Stack</th></tr></thead><tbody>{app_rows}</tbody></table>"
    ) if app_rows else ""

    team = ", ".join(_esc(r.get("nom")) for r in auditeurs) or "—"
    ev_items = "".join(f"<li>{_mask_if_secret(e)}</li>" for e in evidence)

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_BASE_CSS}</head><body>
    {_banner(tlp, client_name)}
    <h1>Rapport Purple Team</h1>
    <p class="meta">{_esc(audit.get('nom'))} — {_esc(client_name)} — généré par {_esc(presta_name)}</p>

    <h2>Fiche de mission</h2>
    {_kv_table([
        ("Client", _esc(client_name)),
        ("Prestataire", _esc(presta_name)),
        ("Catégorie / type de test", f"{_esc(audit.get('categorie'))}" + (f" · {_esc(audit.get('type_test'))}" if audit.get('type_test') else "")),
        ("Référentiels", _esc(referentiels)),
        ("Période", f"{_dt(audit.get('date_debut'))} → {_dt(audit.get('date_fin'))}"),
        ("Environnement", _esc(audit.get('environnement')) or "—"),
        ("Équipe d'audit", team),
        ("Statut de l'audit", _esc(audit.get('statut')) or "—"),
    ])}

    <h2>Synthèse</h2>
    <table><tbody><tr>{stat_cells}</tr></tbody></table>

    {scenario_html}
    {apps_html}
    {actions_html}

    <h2>Vulnérabilités</h2>
    <table><thead><tr><th>Vulnérabilité</th><th>CVSS</th><th>Sévérité</th><th>EPSS</th>
    <th>KEV</th><th>SLA</th><th>Statut</th></tr>
    </thead><tbody>{rows or '<tr><td colspan=7>Aucune</td></tr>'}</tbody></table>

    <h2>Preuves référencées</h2>
    <ul class="compact">{ev_items or '<li>Aucune preuve stockée</li>'}</ul>
    <p class="meta">Chaque preuve est scellée dans le coffre (empreinte SHA-256, journal
    d'accès nominatif) ; les preuves contenant des secrets sont masquées dans ce document
    et consultables uniquement via la chaîne de custody.</p>

    <div class="footer">TLP:{_esc(tlp)} — diffusion restreinte au client — généré par Purple Cockpit</div>
    </body></html>"""


async def html_to_pdf(html_content: str) -> bytes:
    """Convertit le HTML en PDF via le service Chromium headless (pdf-renderer).

    En cas d'échec du renderer, on LÈVE une erreur au lieu de renvoyer le HTML :
    stocker du HTML sous une extension .pdf produit un fichier corrompu (le bug
    observé). Le pipeline reste testable via un renderer réel ou un mock explicite.
    """
    import httpx

    from app.config import settings

    renderer_url = getattr(settings, "pdf_renderer_url", "http://pdf-renderer:3000/pdf")
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(renderer_url, json={"html": html_content})
        resp.raise_for_status()  # 503 du renderer → RuntimeError remonté à l'appelant
        ctype = resp.headers.get("content-type", "")
        if "application/pdf" not in ctype:
            # Garde-fou : ne jamais laisser passer autre chose qu'un vrai PDF.
            raise RuntimeError(
                f"pdf-renderer a renvoyé {ctype!r} au lieu d'un PDF — rendu indisponible"
            )
        return resp.content


# ── Micro-service de rendu (service `pdf-renderer` du compose) ───────────────
# Le modèle DOIT être défini au niveau module : un BaseModel déclaré dans une
# closure (à l'intérieur de _build_render_app) n'est pas reconnu de façon fiable
# par FastAPI comme corps de requête — il le traite alors en paramètre query,
# renvoyant 422 "Field required (query, req)" même sur un POST JSON valide.
# C'était la cause du 422 systématique du renderer.
class RenderRequest(BaseModel):
    # Corps attendu : {"html": "<...>"}. Champ tolérant (défaut vide) : le contrôle
    # "html vide" est fait explicitement dans le endpoint, avec un message clair.
    html: str = ""


def _build_render_app():
    """Application FastAPI minimale exposant POST /pdf.

    Rend un vrai PDF via Playwright/Chromium. En cas d'indisponibilité du moteur,
    renvoie une erreur explicite (503) — JAMAIS du HTML déguisé en PDF (qui serait
    stocké tel quel sous une extension .pdf). Cette séparation garde le rendu hors
    du processus API (isolation, ressources).
    """
    render_app = FastAPI(title="pdf-renderer")

    @render_app.get("/health")
    async def _health():
        return {"status": "ok"}

    @render_app.post("/pdf")
    async def _pdf(req: RenderRequest):
        html_content = req.html
        if not html_content.strip():
            return Response(
                content=b"empty_html", media_type="text/plain", status_code=422
            )
        try:
            from playwright.async_api import async_playwright  # type: ignore

            async with async_playwright() as p:
                browser = await p.chromium.launch(args=["--no-sandbox"])
                page = await browser.new_page()
                await page.set_content(html_content, wait_until="networkidle")
                pdf = await page.pdf(format="A4", print_background=True)
                await browser.close()
            return Response(content=pdf, media_type="application/pdf")
        except Exception as exc:
            # NE JAMAIS renvoyer le HTML déguisé en succès : l'appelant le
            # stockerait sous .pdf (fichier corrompu). Échec franc → l'API
            # remonte l'erreur au lieu de produire un faux PDF.
            import logging

            logging.getLogger("pdf-renderer").error(
                "rendu Chromium indisponible (%s) — vérifier `playwright install "
                "chromium` dans l'image", exc, exc_info=True,
            )
            return Response(
                content=b"pdf_renderer_unavailable",
                media_type="text/plain",
                status_code=503,
            )

    return render_app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(_build_render_app(), host="0.0.0.0", port=3000)
