"""Invariant de déploiement (DAT §4.1bis) : un SEUL service publie des ports.

Vérifie que docker-compose.yml n'expose au monde extérieur que le reverse proxy
`frontend`. Tout autre `ports:` est un défaut de sécurité (fuite d'un service interne).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")


def _compose_path() -> Path:
    """Résout docker-compose.yml selon le contexte d'exécution.

    Ordre : variable COMPOSE_FILE (explicite) → racine du dépôt (exécution locale/CI)
    → /docker-compose.yml (monté en lecture seule par le service `api-test`).
    Test BLOQUANT : si introuvable, on échoue avec un message actionnable plutôt
    que de sauter silencieusement un invariant de sécurité.
    """
    candidates = []
    if os.environ.get("COMPOSE_FILE"):
        candidates.append(Path(os.environ["COMPOSE_FILE"]))
    candidates.append(Path(__file__).resolve().parents[2] / "docker-compose.yml")
    candidates.append(Path("/docker-compose.yml"))
    for c in candidates:
        if c.is_file():
            return c
    pytest.fail(
        "docker-compose.yml introuvable (cherché : "
        + ", ".join(str(c) for c in candidates)
        + ") — définir COMPOSE_FILE ou monter le fichier (service api-test)."
    )


_COMPOSE = _compose_path()


def test_only_frontend_publishes_ports():
    compose = yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))
    services = compose.get("services", {})
    publishing = [name for name, spec in services.items() if spec.get("ports")]
    assert publishing == ["frontend"], (
        f"Seul 'frontend' doit publier des ports, trouvé : {publishing}"
    )


def test_data_services_are_internal_only():
    compose = yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))
    services = compose.get("services", {})
    for name in ("postgres", "redis", "minio", "vault", "keycloak", "clamav"):
        spec = services.get(name, {})
        assert "ports" not in spec, f"{name} ne doit jamais publier de port"
        # Ces services ne doivent pas être sur le réseau edge.
        assert "edge" not in (spec.get("networks") or []), f"{name} ne doit pas être sur edge"
