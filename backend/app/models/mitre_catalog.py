"""
Modèle de stockage du catalogue MITRE ATT&CK Enterprise complet.

Distinct du modèle Technique (techniques utilisées dans les scénarios),
MitreTechnique contient l'intégralité du catalogue officiel téléchargé
depuis le dépôt STIX de MITRE. Il sert de dénominateur pour calculer
le vrai taux de couverture ATT&CK d'une application.
"""

from sqlalchemy import Column, Integer, String, Text, Boolean

from app.core.database import Base


class MitreTechnique(Base):
    """Une technique (ou sous-technique) du catalogue ATT&CK Enterprise."""

    __tablename__ = "mitre_catalog"

    id          = Column(Integer, primary_key=True)
    mitre_id    = Column(String, unique=True, nullable=False, index=True)  # ex. T1566, T1566.001
    name        = Column(String, nullable=False)
    tactic      = Column(String, default="")       # tactique principale
    description = Column(Text, default="")
    is_subtechnique = Column(Boolean, default=False)  # True si T1566.001
    is_deprecated   = Column(Boolean, default=False)  # à exclure des calculs
