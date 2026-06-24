"""
Modèles de stockage des référentiels de sécurité.

Chaque référentiel (owasp, cwe, capec) est stocké sous forme d'entrées
individuelles dans ReferentialEntry, avec une ligne de métadonnées dans
ReferentialMeta (version, date de sync, nombre d'entrées).
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.core.database import Base


class ReferentialMeta(Base):
    """Métadonnées d'un référentiel (une ligne par référentiel)."""

    __tablename__ = "referential_meta"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False, index=True)  # owasp | cwe | capec
    version = Column(String, default="")       # ex. "2021", "4.15", "3.9"
    entry_count = Column(Integer, default=0)
    synced_at = Column(DateTime, nullable=True)
    source_url = Column(String, default="")


class ReferentialEntry(Base):
    """
    Une entrée dans un référentiel de sécurité.

    Exemples :
      - owasp : ref_id="A03:2021", name="Injection", description="..."
      - cwe   : ref_id="CWE-89",   name="SQL Injection", description="..."
      - capec : ref_id="CAPEC-66", name="SQL Injection", description="..."
    """

    __tablename__ = "referential_entries"

    id = Column(Integer, primary_key=True)
    referential = Column(String, nullable=False, index=True)  # owasp | cwe | capec
    ref_id = Column(String, nullable=False, index=True)       # identifiant officiel
    name = Column(String, default="")
    description = Column(Text, default="")
