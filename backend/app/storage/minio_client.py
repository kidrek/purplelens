"""MinIO — objets chiffrés + WORM (cahier §6quater.2 / §6quater.6).

- Object Lock activé À LA CRÉATION des buckets (impératif : ne s'active pas a posteriori).
- Aucun binaire via l'API : upload direct vers la quarantaine et download par URL
  présignées (≤ 5 min), l'API signe avec l'URL PUBLIQUE (l'hôte est dans la signature).

Deux clients distincts :
- `client()` — hôte interne Docker (`minio_endpoint`, ex. "minio:9000"), pour les
  opérations serveur (put/get/make_bucket) : le serveur API parle à MinIO sur le
  réseau interne, jamais via l'edge.
- `_public_client(origin)` — hôte PUBLIC, pour signer les URL présignées consommées
  par le navigateur. Cet hôte n'est PAS lu dans une variable de config figée : il est
  dérivé de la requête entrante (`public_origin(request)`, ci-dessous), sur le même
  principe que le X-Forwarded-Host déjà utilisé pour Keycloak (nginx.conf). Ainsi le
  port exposé par l'edge (EDGE_HTTPS_PORT) reste librement personnalisable — rien à
  garder synchronisé côté API. La signature SigV4 couvre le header `Host` (présent
  dans `X-Amz-SignedHeaders=host`) : une URL signée avec le mauvais hôte échoue
  silencieusement (host injoignable ou mauvais port) plutôt qu'avec une signature
  invalide, ce qui a longtemps masqué l'absence de ce mécanisme.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit, urlunsplit

from minio import Minio
from minio.commonconfig import COMPLIANCE
from minio.retention import Retention
from starlette.requests import Request

from app.config import settings


def client() -> Minio:
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_root_user,
        secret_key=settings.minio_root_password,
        secure=settings.minio_secure,
        region=settings.minio_region,
    )


def public_origin(request: Request) -> str:
    """scheme://host[:port] tel que vu par le navigateur pour CETTE requête —
    jamais lu dans une variable figée, pour que le port de l'edge
    (EDGE_HTTPS_PORT) reste personnalisable sans rien resynchroniser côté API.
    Repli sur Host/l'URL de la requête si l'appel n'est pas derrière nginx
    (ex. accès direct à uvicorn en dev, tests)."""
    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or request.url.netloc
    )
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    return f"{scheme}://{host}"


def _public_client(origin: str) -> Minio:
    parts = urlsplit(origin)
    return Minio(
        parts.netloc,  # host[:port], ex. "localhost:7443" — celui de la requête
        access_key=settings.minio_root_user,
        secret_key=settings.minio_root_password,
        secure=(parts.scheme == "https"),
        # Région fixée => signature purement locale. Sans elle, minio-py appelle le
        # serveur (GET /?location) pour la découvrir AVANT de signer, sur cet hôte
        # public que le conteneur api ne peut pas joindre => Connection refused.
        region=settings.minio_region,
    )


def _with_prefix(url: str, prefix: str) -> str:
    if not prefix:
        return url
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, prefix + p.path, p.query, p.fragment))


def evidence_bucket(client_code: str) -> str:
    return f"{settings.minio_evidence_bucket_prefix}-{client_code.lower()}"


def object_key(client_code: str, audit_id: str, evidence_id: str) -> str:
    """Arborescence par préfixes (cahier §6quater.2)."""
    return f"client/{client_code}/audit/{audit_id}/evidence/{evidence_id}"


def ensure_buckets(client_codes: list[str]) -> None:
    """Crée la quarantaine (sans lock) et un bucket par client AVEC Object Lock."""
    mc = client()
    if not mc.bucket_exists(settings.minio_quarantine_bucket):
        mc.make_bucket(settings.minio_quarantine_bucket)  # préfixe non servi
    for code in client_codes:
        bucket = evidence_bucket(code)
        if not mc.bucket_exists(bucket):
            mc.make_bucket(bucket, object_lock=True)  # WORM impératif


def presign_upload(bucket: str, key: str, *, origin: str) -> str:
    pub = _public_client(origin)
    url = pub.presigned_put_object(
        bucket, key, expires=timedelta(seconds=settings.presign_upload_ttl_seconds)
    )
    return _with_prefix(url, settings.minio_public_path_prefix)


def presign_download(bucket: str, key: str, *, origin: str) -> str:
    pub = _public_client(origin)
    url = pub.presigned_get_object(
        bucket, key, expires=timedelta(seconds=settings.presign_download_ttl_seconds)
    )
    return _with_prefix(url, settings.minio_public_path_prefix)


def put_locked_object(bucket: str, key: str, data: bytes, lock_until: datetime) -> None:
    """Écrit l'objet chiffré avec Object Lock mode compliance (personne, pas même un
    admin MinIO, ne peut l'altérer/supprimer avant échéance).

    Ceinture + bretelles : le bucket cible doit exister AVANT le put. Le provisioning
    nominal (ensure_buckets à la création du client / au bootstrap) peut avoir échoué
    ou être en retard ; on crée donc le bucket manquant à la volée. L'Object Lock ne
    s'activant QU'À la création (jamais a posteriori), on le crée impérativement avec
    object_lock=True — un bucket sans lock trahirait la garantie WORM. Un bucket
    préexistant est laissé intact (s'il avait été créé sans lock, le put ci-dessous
    échouerait, ce qui est le bon comportement : mieux vaut rejeter que stocker sans
    immuabilité)."""
    import io

    mc = client()
    if not mc.bucket_exists(bucket):
        mc.make_bucket(bucket, object_lock=True)  # WORM impératif — jamais sans lock
    retention = Retention(COMPLIANCE, retain_until_date=lock_until)
    mc.put_object(
        bucket,
        key,
        io.BytesIO(data),
        length=len(data),
        retention=retention,
    )


def default_lock_until(days: int) -> datetime:
    return datetime.now(UTC) + timedelta(days=days)


# ── Ancres WORM du journal (durcissement P1) ────────────────────────────────
def ensure_anchor_bucket() -> None:
    """Crée (idempotent) le bucket d'ancres du journal AVEC Object Lock (WORM)."""
    mc = client()
    if not mc.bucket_exists(settings.journal_anchor_bucket):
        mc.make_bucket(settings.journal_anchor_bucket, object_lock=True)


def put_anchor(key: str, data: bytes, lock_until: datetime) -> None:
    """Écrit une ancre immuable (Object Lock COMPLIANCE) dans le bucket d'ancres."""
    put_locked_object(settings.journal_anchor_bucket, key, data, lock_until)


def latest_anchor() -> bytes | None:
    """Renvoie l'ancre la plus récente (seq max), ou None si aucune. Les clés sont
    préfixées par le seq zero-paddé : le max lexicographique = l'ancre la plus récente."""
    mc = client()
    if not mc.bucket_exists(settings.journal_anchor_bucket):
        return None
    keys = [
        o.object_name
        for o in mc.list_objects(
            settings.journal_anchor_bucket, prefix="journal-head/", recursive=True
        )
    ]
    if not keys:
        return None
    return read_object(settings.journal_anchor_bucket, max(keys))


def read_object(bucket: str, key: str) -> bytes:
    resp = client().get_object(bucket, key)
    try:
        return resp.read()
    finally:
        resp.close()
        resp.release_conn()


def purge_quarantine(key: str) -> None:
    try:
        client().remove_object(settings.minio_quarantine_bucket, key)
    except Exception:
        pass  # purge best-effort ; la ligne de métadonnées conserve la trace
