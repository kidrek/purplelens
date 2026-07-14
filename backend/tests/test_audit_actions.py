"""Dérivation des actions d'audit depuis le scénario lié — mapping tactique → phase PTES.

Le composant pur (tactique ATT&CK → phase PTES) est testé ici ; la génération complète
(lecture des étapes, dédoublonnage, insertion) est couverte par le parcours e2e
(test_e2e_http).
"""
from __future__ import annotations

from app.api import service


def test_ptes_from_tactic_maps_known_tactics():
    assert service._ptes_from_tactic("reconnaissance") == "reconnaissance"
    assert service._ptes_from_tactic("initial-access") == "exploitation"
    assert service._ptes_from_tactic("execution") == "exploitation"


def test_ptes_from_tactic_other_tactics_go_post_exploitation():
    for tac in ("persistence", "privilege-escalation", "lateral-movement",
                "exfiltration", "impact", "command-and-control"):
        assert service._ptes_from_tactic(tac) == "post-exploitation", tac


def test_ptes_from_tactic_is_case_insensitive():
    assert service._ptes_from_tactic("Initial-Access") == "exploitation"


def test_ptes_from_tactic_defaults_to_exploitation_when_absent():
    assert service._ptes_from_tactic(None) == "exploitation"
    assert service._ptes_from_tactic("") == "exploitation"
