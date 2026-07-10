"""Journal tamper-evident : le chaînage détecte toute altération (spec v2 §6)."""
from __future__ import annotations

from app.journal.chain import GENESIS, compute_hash


def _entry(i: int) -> dict:
    return {"event_type": "test", "actor_id": None, "detail": {"i": i}}


def test_hash_is_deterministic():
    e = _entry(1)
    assert compute_hash(GENESIS, e) == compute_hash(GENESIS, e)


def test_chain_links_change_when_prev_changes():
    e = _entry(1)
    h_from_genesis = compute_hash(GENESIS, e)
    h_from_other = compute_hash("f" * 64, e)
    assert h_from_genesis != h_from_other  # le hash précédent est bien scellé dans l'entrée


def test_altering_entry_breaks_chain():
    """Recalcul : modifier une entrée passée invalide tous les hash suivants."""
    chain = []
    prev = GENESIS
    for i in range(5):
        h = compute_hash(prev, _entry(i))
        chain.append((prev, _entry(i), h))
        prev = h

    # On altère l'entrée n°2 et on recalcule à partir d'elle.
    tampered = _entry(999)
    recomputed = compute_hash(chain[2][0], tampered)
    assert recomputed != chain[2][2]  # rupture détectée à l'entrée altérée


def test_genesis_is_64_zeros():
    assert GENESIS == "0" * 64
