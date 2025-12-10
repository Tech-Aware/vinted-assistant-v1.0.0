# domain/templates/base.py

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any

logger = logging.getLogger(__name__)


class AnalysisProfileName(Enum):
    """
    Nom logique des profils d'analyse.
    Chaque valeur correspond à un type de pièce / famille de vêtements.
    """
    JEAN_LEVIS = "jean_levis"
    POLAIRE_OUTDOOR = "polaire_outdoor"
    PULL_TOMMY = "pull_tommy"


@dataclass
class AnalysisProfile:
    """
    Profil d'analyse pour un type de vêtement.

    - name          : identifiant logique du profil
    - prompt_suffix : texte ajouté au prompt de base, spécifique à ce type de pièce
    - json_schema   : schéma JSON (JSON Schema) attendu en sortie de l'IA
    """
    name: AnalysisProfileName
    prompt_suffix: str
    json_schema: Dict[str, Any]

    def describe(self) -> str:
        """
        Retourne une courte description textuelle utile pour le debug/log.
        """
        desc = (
            f"AnalysisProfile(name={self.name.value}, "
            f"schema_keys={list(self.json_schema.get('properties', {}).keys())})"
        )
        logger.debug("Description profil: %s", desc)
        return desc


# Schéma JSON commun à tous les profils (aligné avec PROMPT_CONTRACT)
BASE_LISTING_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "brand": {"type": ["string", "null"]},
        "style": {"type": ["string", "null"]},
        "pattern": {"type": ["string", "null"]},
        "neckline": {"type": ["string", "null"]},
        "season": {"type": ["string", "null"]},
        "defects": {"type": ["string", "null"]},
    },
    "required": [
        "title",
        "description",
        "brand",
        "style",
        "pattern",
        "neckline",
        "season",
        "defects",
    ],
}
