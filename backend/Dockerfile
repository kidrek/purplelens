# Image unique servant l'API, les workers Celery, beat et le pdf-renderer.
# La commande est fournie par docker-compose (uvicorn / celery / python -m ...).
#
# Multi-étages :
#   base    → dépendances d'exécution + code applicatif ;
#   test    → base + outils de test (pytest, ruff…) + répertoire tests/.
#             Utilisé par le service compose `api-test` (make test). JAMAIS livré.
#   runtime → étage FINAL (défaut) : durci, non-root, sans outillage de test.
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

# netcat pour les healthchecks ClamAV ; libmagic non requis (détection par signatures maison).
RUN apt-get update && apt-get install -y --no-install-recommends \
        netcat-openbsd curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
# Installe les dépendances d'exécution + l'extra `render` (playwright), requis
# par le pdf-renderer. playwright est un optional-dependency : un `pip install .`
# nu ne l'installe pas — d'où le rendu jamais opérationnel jusqu'ici.
RUN pip install --upgrade pip && pip install ".[render]"

# Navigateur du pdf-renderer : le paquet pip `playwright` n'embarque PAS le
# binaire Chromium ni ses libs système. Sans ça, page.pdf() échoue et le
# renderer se rabat sur du HTML → un « .pdf » qui contient du HTML.
# `--with-deps` installe aussi les dépendances système (apt) nécessaires.
# Installé dans PLAYWRIGHT_BROWSERS_PATH (/opt) — chemin partagé, lisible par
# l'utilisateur non-root du runtime (l'install par défaut irait dans /root).
RUN python -m playwright install --with-deps chromium \
    && chmod -R a+rX /opt/playwright \
    && rm -rf /var/lib/apt/lists/*

COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
COPY sql ./sql

# ── Étage de TEST (make test) ────────────────────────────────────────────────
FROM base AS test
RUN pip install .[dev]
COPY tests ./tests
CMD ["pytest", "-q"]

# ── Étage FINAL de production (défaut du build) ─────────────────────────────
FROM base AS runtime

# Utilisateur non-root (durcissement — DAT §4).
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
