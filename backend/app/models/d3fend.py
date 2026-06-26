"""
Modèle de stockage du mapping D3FEND (ATT&CK → contre-mesures défensives).

Une entrée = une contre-mesure D3FEND associée à un T-code ATT&CK.
"""
from sqlalchemy import Boolean, Column, Integer, String, Text

from app.core.database import Base


class D3fendMapping(Base):
    """Contre-mesure D3FEND associée à une technique ATT&CK."""

    __tablename__ = "d3fend_mappings"

    id         = Column(Integer, primary_key=True)
    mitre_id   = Column(String, nullable=False, index=True)  # ex. T1566
    d3f_id     = Column(String, nullable=False, index=True)  # ex. Multi-factorAuthentication
    name       = Column(String, nullable=False)               # libellé lisible
    category   = Column(String, default="")                   # harden|detect|isolate|deceive|evict|restore
    description = Column(Text, default="")
