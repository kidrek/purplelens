"""Contexte de sécurité d'une requête (spec backend v2 §3.2).

Extrait de l'access token vérifié ; jamais construit à partir de données client
non signées. Porte le sujet, le rôle, le scope client et la fraîcheur MFA.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SecurityContext:
    user_id: str
    role: str
    client_scope: list[str] = field(default_factory=list)  # [] = tous (selon rôle)
    mfa: bool = False
    auth_time: int = 0  # epoch de la dernière authentification (pour step-up)
    email: str | None = None
    display_name: str | None = None

    @property
    def is_service(self) -> bool:
        from app.security.matrix import SERVICE_ROLES

        return self.role in SERVICE_ROLES

    @property
    def is_multi_client(self) -> bool:
        """admin et manager sont toujours multi-clients (spec v2 §2.1)."""
        return self.role in {"admin", "manager"} or not self.client_scope

    def step_up_fresh(self, max_age_seconds: int) -> bool:
        """Vrai si la dernière authentification est assez récente (porte 2, step-up)."""
        return self.mfa and (time.time() - self.auth_time) <= max_age_seconds
