#!/usr/bin/env python3
"""Contrôle d'exposition réseau (DAT §4.1bis) — traité comme du code de sécurité.

Échoue si un service autre que `frontend` publie un port (`ports:`).
Utilisé par `make config` et par le test CI test_network_exposure.
"""
from __future__ import annotations
import sys

try:
    import yaml
except ImportError:
    print("PyYAML requis (pip install pyyaml)", file=sys.stderr)
    sys.exit(2)

ALLOWED = {"frontend"}


def check(path: str) -> int:
    with open(path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    services = (cfg or {}).get("services", {}) or {}
    offenders = []
    for name, spec in services.items():
        published = (spec or {}).get("ports") or []
        if published and name not in ALLOWED:
            offenders.append((name, published))
    if offenders:
        print("VIOLATION — services publiant des ports hors 'frontend' :", file=sys.stderr)
        for name, ports in offenders:
            print(f"  - {name}: {ports}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "docker-compose.yml"
    sys.exit(check(target))
