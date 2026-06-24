# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

# psycopg2 a besoin de libpq au runtime ; build-essential pour la compilation éventuelle
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Couche dépendances (cache tant que requirements.txt ne change pas)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code applicatif
COPY app ./app
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Utilisateur non-root
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
