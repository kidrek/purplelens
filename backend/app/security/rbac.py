"""Moteur de décision `can()` — version serveur, 5 portes, deny par défaut.
Spec backend v2 §3.2 (portes) · §3.4 (actions à haut risque) · DAT §2.4.

    DÉCISION = AUTORISER ⟺ toutes les portes passent, sinon REFUSER
      1. Authentifié ? (jeton valide, compte 'active')
      2. MFA suffisant pour la sensibilité visée ? (step-up si requis)
      3. La matrice rôle × entité × action autorise l'action ?
      4. Cloisonnement : le client du record ∈ client_scope ? (ou scope vide)
      5. (preuves) TLP/PAP de l'objet compatible avec le contexte de diffusion ?

La porte 4 est vérifiée ici ET garantie par la RLS PostgreSQL — double barrière.
Les réponses d'erreur au client sont 403 sans détail exploitable ; la raison précise
part au journal (DAT §2.4 / DA §5.4).
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status

from app.config import settings
from app.security.context import SecurityContext
from app.security.matrix import Action, allowed

# Actions à haut risque exigeant une réauthentification récente (spec v2 §3.4).
HIGH_RISK_ACTIONS: frozenset[str] = frozenset(
    {
        # Nommage canonique : celui passé par les routes (préfixe.action).
        # Spec v2 §3.4 + §2.1 : gestion des comptes, legal hold, crypto-shredding,
        # export d'archive, rotation de KEK — tous exigent une réauth récente.
        "legal_hold.release",
        "crypto.shredding",
        "audit.export",
        "kek.rotation",
        "user.create",
        "user.role_change",
        "user.deactivate",
    }
)


@dataclass
class Decision:
    allowed: bool
    reason: str = "ok"


def _tlp_pap_compatible(record: dict | None, purpose: str) -> bool:
    """Porte 5 — contrôle de diffusion (preuves). En v1 : diffusion interne autorisée ;
    l'inclusion au livrable des `contains_secrets` exige un masquage (géré côté générateur).
    """
    if not record:
        return True
    if purpose == "report_render" and record.get("contains_secrets"):
        # Le générateur doit masquer avant inclusion — refus tant que non masqué.
        return bool(record.get("masked"))
    return True


def can(
    ctx: SecurityContext,
    action: Action,
    entity: str,
    record: dict | None = None,
    *,
    purpose: str = "view",
) -> Decision:
    """Évalue les 5 portes dans l'ordre strict, deny par défaut."""
    # Porte 1 — authentifié (le contexte n'existe que si le jeton était valide).
    if not ctx.user_id and not ctx.is_service:
        return Decision(False, "gate1_unauthenticated")

    # Porte 3 — matrice (évaluée avant le cloisonnement pour un refus net).
    if not allowed(ctx.role, entity, action):
        return Decision(False, "gate3_matrix_denied")

    # Porte 4 — cloisonnement (RESTREINT, jamais n'élargit).
    if record is not None:
        client_id = _scope_client_of(record)
        if client_id is not None and ctx.client_scope and client_id not in ctx.client_scope:
            return Decision(False, "gate4_client_scope")

    # Porte 5 — TLP/PAP (preuves).
    if entity == "evidence" and not _tlp_pap_compatible(record, purpose):
        return Decision(False, "gate5_tlp_pap")

    return Decision(True, "ok")


def _scope_client_of(record: dict) -> str | None:
    """Résolution du client d'un record (spec v2 §3.2, porte 4) : direct ou via parent."""
    return record.get("client_id") or record.get("audit_client_id")


# ── Dépendances FastAPI ─────────────────────────────────────────────────────
def get_security_context(request: Request) -> SecurityContext:
    ctx = getattr(request.state, "security_context", None)
    if ctx is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthenticated")
    return ctx


def require(entity: str, action: Action):
    """Dépendance de route : impose que la matrice autorise (entity, action).

    Le cloisonnement fin (porte 4) sur un record précis est revérifié dans le handler
    via can() ; la RLS garantit de toute façon l'invisibilité des lignes hors scope.
    """

    def _dep(ctx: SecurityContext = Depends(get_security_context)) -> SecurityContext:
        decision = can(ctx, action, entity)
        if not decision.allowed:
            # 403 sans détail exploitable ; la raison précise est journalisée en amont.
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
        return ctx

    return _dep


def require_step_up(risk_action: str):
    """Dépendance : impose une réauthentification récente (< STEP_UP_MAX_AGE) pour une
    action à haut risque (spec v2 §3.4)."""

    def _dep(ctx: SecurityContext = Depends(get_security_context)) -> SecurityContext:
        if risk_action not in HIGH_RISK_ACTIONS:
            return ctx
        if not ctx.step_up_fresh(settings.step_up_max_age_seconds):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="step_up_required",
                headers={"WWW-Authenticate": 'MFA realm="step-up"'},
            )
        return ctx

    return _dep
