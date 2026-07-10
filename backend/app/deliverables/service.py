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
  .tlp-banner { color: white; font-weight: 700; padding: 6px 12px; border-radius: 6px;
                text-align: center; letter-spacing: 0.06em; margin-bottom: 18px; }
  .meta { color: #6B6580; font-size: 9pt; }
  .masked { background: #EDE9FE; color: #6D28D9; padding: 2px 8px; border-radius: 4px;
            font-style: italic; }
  table { width: 100%; border-collapse: collapse; margin: 10px 0; }
  th, td { border: 1px solid #E5E1F0; padding: 6px 8px; text-align: left; font-size: 10pt; }
  th { background: #F4F2F9; color: #4C1D95; }
  .sev-critique { color: #D32F2F; font-weight: 700; }
  .footer { color: #9B95AD; font-size: 8pt; text-align: center; margin-top: 30px; }
</style>
"""


def _mask_if_secret(item: dict) -> str:
    """Une preuve `contains_secrets` n'apparaît jamais en clair dans un rapport."""
    if item.get("contains_secrets"):
        return '<span class="masked">[preuve masquée — voir chaîne de custody]</span>'
    return html.escape(item.get("caption") or item.get("original_filename", "preuve"))


def render_engagement_letter(*, client_name: str, audit_name: str, tlp: str,
                             scope: str, dates: str) -> str:
    """Lettre d'engagement (règles PTES : périmètre, autorisation, fenêtre)."""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_BASE_CSS}</head><body>
    {_banner(tlp, client_name)}
    <h1>Lettre d'engagement</h1>
    <p class="meta">Audit : {html.escape(audit_name)}</p>
    <h2>1. Parties</h2>
    <p>Le présent document formalise l'engagement entre le prestataire Purple Team et
    <strong>{html.escape(client_name)}</strong>.</p>
    <h2>2. Périmètre autorisé</h2>
    <p>{html.escape(scope)}</p>
    <h2>3. Fenêtre d'intervention</h2>
    <p>{html.escape(dates)}</p>
    <h2>4. Règles d'engagement</h2>
    <p>Conformité PTES. Toute action hors périmètre est proscrite. Les preuves collectées
    sont chiffrées, horodatées et conservées selon la politique de rétention.</p>
    <div class="footer">Document généré automatiquement — TLP:{html.escape(tlp)}</div>
    </body></html>"""


def render_nda(*, client_name: str, tlp: str) -> str:
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_BASE_CSS}</head><body>
    {_banner(tlp, client_name)}
    <h1>Accord de confidentialité (NDA)</h1>
    <p>Les informations échangées dans le cadre de la mission Purple Team avec
    <strong>{html.escape(client_name)}</strong> sont strictement confidentielles.</p>
    <h2>Engagements</h2>
    <p>Non-divulgation, usage limité à la mission, restitution ou destruction en fin
    de mission selon la politique de rétention et de crypto-effacement.</p>
    <div class="footer">TLP:{html.escape(tlp)}</div>
    </body></html>"""


def render_ptes_report(*, client_name: str, audit_name: str, tlp: str,
                       findings: list[dict], evidence: list[dict]) -> str:
    """Rapport PTES synthétique. Les preuves secrètes sont masquées (porte 5)."""
    rows = "".join(
        f"<tr><td>{html.escape(f.get('titre',''))}</td>"
        f"<td>{html.escape(str(f.get('cvss_score','')))}</td>"
        f"<td class='sev-{html.escape(str(f.get('severite','')).lower())}'>"
        f"{html.escape(str(f.get('severite','')))}</td>"
        f"<td>{html.escape(f.get('sla_niveau') or '')}</td></tr>"
        for f in findings
    )
    ev_items = "".join(f"<li>{_mask_if_secret(e)}</li>" for e in evidence)
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_BASE_CSS}</head><body>
    {_banner(tlp, client_name)}
    <h1>Rapport Purple Team</h1>
    <p class="meta">{html.escape(audit_name)} — {html.escape(client_name)}</p>
    <h2>Synthèse des vulnérabilités</h2>
    <table><thead><tr><th>Vulnérabilité</th><th>CVSS</th><th>Sévérité</th><th>SLA</th></tr>
    </thead><tbody>{rows or '<tr><td colspan=4>Aucune</td></tr>'}</tbody></table>
    <h2>Preuves référencées</h2>
    <ul>{ev_items or '<li>Aucune preuve stockée</li>'}</ul>
    <div class="footer">TLP:{html.escape(tlp)} — diffusion restreinte au client</div>
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
