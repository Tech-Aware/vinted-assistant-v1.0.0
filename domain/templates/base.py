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
    JACKET_CARHART = "jacket_carhart"



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


# --------------------------------------------------------------------
# Enveloppe IA standard (statut + champs manquants + avertissements)
# --------------------------------------------------------------------

AI_STATUS_ENUM = [
    "ok",
    "needs_user_input",
    "insufficient_images",
    "refused",
    "error",
]

AI_ENVELOPE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": AI_STATUS_ENUM,
            "description": "Statut global du résultat IA.",
        },
        "reason": {
            "type": ["string", "null"],
            "description": "Raison courte si status != ok (ou info utile).",
        },
        "missing": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Liste des champs manquants (ex: ['sku', 'composition']).",
            "minItems": 0,
        },
        "warnings": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Avertissements non bloquants.",
            "minItems": 0,
        },
    },
    "required": ["status", "reason", "missing", "warnings"],
    "additionalProperties": False,
}


# Schéma JSON commun à tous les profils (aligné avec PROMPT_CONTRACT)
BASE_LISTING_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "ai": AI_ENVELOPE_SCHEMA,
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
        "ai",
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
