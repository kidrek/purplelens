"""Durcissement P1 — ancrage WORM de la tête de chaîne du journal (fonctions pures)."""
from __future__ import annotations

from datetime import UTC, datetime

from app.journal import anchor


def test_serialize_roundtrip_and_deterministic():
    payload = anchor.build_anchor_payload(
        seq=42, curr_hash="a" * 64, count=42,
        sealed_at_iso="2026-01-01T00:00:00+00:00",
        anchored_at_iso="2026-01-01T01:00:00+00:00",
    )
    data = anchor.serialize(payload)
    assert anchor.deserialize(data) == payload
    # Sérialisation déterministe (ancre reproductible).
    assert anchor.serialize(payload) == data
    assert payload["version"] == anchor.ANCHOR_VERSION


def test_anchor_key_is_seq_sortable():
    at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    k9 = anchor.anchor_object_key(9, at)
    k10 = anchor.anchor_object_key(10, at)
    # Le zero-padding garantit que le tri lexicographique = tri par seq.
    assert k9 < k10
    assert k10.startswith("journal-head/000000000010-")
    assert k10.endswith("20260102T030405Z.json")


def test_consistency_ok():
    a = {"seq": 10, "curr_hash": "h"}
    ok, reason = anchor.check_anchor_consistency(
        a, current_max_seq=12, hash_at_anchor_seq="h"
    )
    assert ok and reason == "ok"


def test_consistency_detects_rewritten_entry():
    a = {"seq": 10, "curr_hash": "h"}
    ok, reason = anchor.check_anchor_consistency(
        a, current_max_seq=12, hash_at_anchor_seq="TAMPERED"
    )
    assert not ok and reason == "hash_mismatch"


def test_consistency_detects_missing_seq():
    a = {"seq": 10, "curr_hash": "h"}
    ok, reason = anchor.check_anchor_consistency(
        a, current_max_seq=12, hash_at_anchor_seq=None
    )
    assert not ok and reason == "anchored_seq_missing"


def test_consistency_detects_truncation():
    a = {"seq": 10, "curr_hash": "h"}
    ok, reason = anchor.check_anchor_consistency(
        a, current_max_seq=5, hash_at_anchor_seq="h"
    )
    assert not ok and reason == "chain_shorter_than_anchor"
