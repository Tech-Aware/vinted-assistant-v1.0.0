# domain/templates/__init__.py

from __future__ import annotations

import logging
from typing import Dict

from .base import AnalysisProfile, AnalysisProfileName, BASE_LISTING_SCHEMA
from .jeans import JEANS_PROFILES
from .jackets import JACKETS_PROFILES
from .polaires import POLAIRES_PROFILES
from .pulls import PULLS_PROFILES

logger = logging.getLogger(__name__)

# Dictionnaire global de tous les profils disponibles
ALL_PROFILES: Dict[AnalysisProfileName, AnalysisProfile] = {
    **JEANS_PROFILES,
    **JACKETS_PROFILES,
    **POLAIRES_PROFILES,
    **PULLS_PROFILES,
}

logger.debug(
    "ALL_PROFILES initialisé avec %d profils: %s",
    len(ALL_PROFILES),
    [name.value for name in ALL_PROFILES.keys()],
)


def get_profile(name: AnalysisProfileName) -> AnalysisProfile:
    """
    Récupère un profil d'analyse à partir de son enum AnalysisProfileName.
    Lève KeyError si le profil n'existe pas.
    """
    return ALL_PROFILES[name]


def list_profiles() -> Dict[AnalysisProfileName, AnalysisProfile]:
    """
    Retourne une copie du dict global de profils.
    Utile si tu veux itérer dessus sans le modifier.
    """
    return dict(ALL_PROFILES)
