"""Ancrage externe (WORM) de la tête de chaîne du journal — durcissement P1.

Le journal est tamper-EVIDENT (chaîne de hachage) mais entièrement RECALCULABLE depuis
genesis par quiconque contrôle PostgreSQL : un attaquant (ou un insider) qui réécrit une
entrée passée peut recomposer tous les hash suivants et présenter une chaîne « intacte ».
La propriété « immuable même pour l'admin » n'est vraie qu'à travers l'application.

On ancre donc périodiquement la TÊTE de chaîne (seq + curr_hash) dans un bucket MinIO en
Object Lock COMPLIANCE : l'ancre devient immuable même pour un admin MinIO, hors du
périmètre PostgreSQL. Une réécriture de l'historique en base ne peut alors plus
correspondre aux hash ancrés — la falsification redevient DÉTECTABLE.

Décision d'architecture (assumée) : l'ancrage RFC 3161 (horodatage signé par une TSA
tierce) est volontairement DIFFÉRÉ — il impose un service externe en ligne, contraire au
principe offline-first (DAT §2.2). L'ancrage WORM apporte l'immuabilité externe DANS la
frontière de confiance ; un ancrage TSA/notarisation pourra s'y greffer le jour où une
connectivité tierce est admise (le point d'extension est `build_anchor_payload`).
"""
from __future__ import annotations

import json
from datetime import datetime

ANCHOR_VERSION = 1
_KEY_PREFIX = "journal-head/"


def build_anchor_payload(
    *, seq: int, curr_hash: str, count: int, sealed_at_iso: str, anchored_at_iso: str
) -> dict:
    """Construit la charge d'ancre. Point d'extension pour un futur horodatage TSA."""
    return {
        "version": ANCHOR_VERSION,
        "seq": seq,
        "curr_hash": curr_hash,
        "count": count,
        "sealed_at": sealed_at_iso,
        "anchored_at": anchored_at_iso,
    }


def serialize(payload: dict) -> bytes:
    """Sérialisation déterministe (clés triées) — l'ancre stockée est reproductible."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def deserialize(data: bytes) -> dict:
    return json.loads(data.decode("utf-8"))


def anchor_object_key(seq: int, anchored_at: datetime) -> str:
    """Clé d'objet immuable, préfixée par le seq zero-paddé pour que le tri
    lexicographique des clés donne l'ancre la plus récente en dernier."""
    return f"{_KEY_PREFIX}{seq:012d}-{anchored_at.strftime('%Y%m%dT%H%M%SZ')}.json"


def check_anchor_consistency(
    anchor: dict, *, current_max_seq: int | None, hash_at_anchor_seq: str | None
) -> tuple[bool, str]:
    """Confronte une ancre (immuable) à l'état courant du journal en base.

    - `hash_at_anchor_seq` : curr_hash actuellement en base à la ligne seq=anchor['seq']
      (None si la ligne n'existe plus).
    - `current_max_seq` : seq maximal actuel du journal (None si vide).

    Renvoie (cohérent, raison). Une incohérence = preuve d'altération HORS application."""
    if hash_at_anchor_seq is None:
        return False, "anchored_seq_missing"  # troncature / suppression d'historique
    if hash_at_anchor_seq != anchor.get("curr_hash"):
        return False, "hash_mismatch"  # entrée passée réécrite
    if current_max_seq is not None and current_max_seq < anchor.get("seq", 0):
        return False, "chain_shorter_than_anchor"  # journal raccourci sous l'ancre
    return True, "ok"
