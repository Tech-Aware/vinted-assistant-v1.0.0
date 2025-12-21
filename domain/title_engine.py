# domain/title_engine.py

from __future__ import annotations

import logging
from typing import Dict, Any

from domain.templates import AnalysisProfileName
from domain.title_builder import (
    build_jean_levis_title,
    build_pull_tommy_title,
    build_jacket_carhart_title,
)

logger = logging.getLogger(__name__)


def build_title_jean_levis(features: Dict[str, Any]) -> str:
    return build_jean_levis_title(features)


def build_title_pull_tommy(features: Dict[str, Any]) -> str:
    return build_pull_tommy_title(features)


def build_title_jacket_carhart(features: Dict[str, Any]) -> str:
    return build_jacket_carhart_title(features)


def build_title(profile_name: AnalysisProfileName, features: Dict[str, Any]) -> str:
    """
    Point d'entrée unique pour construire les titres depuis les features normalisées.
    Expose aussi des fonctions dédiées par profil pour clarifier la logique métier.
    """
    try:
        if profile_name == AnalysisProfileName.JEAN_LEVIS:
            return build_title_jean_levis(features)
        if profile_name == AnalysisProfileName.PULL_TOMMY:
            return build_title_pull_tommy(features)
        if profile_name == AnalysisProfileName.JACKET_CARHART:
            return build_title_jacket_carhart(features)

        fallback = str(features.get("title") or "").strip()
        logger.debug("Profil %s non géré par le moteur de titre, fallback brut.", profile_name)
        return fallback
    except Exception as exc:  # pragma: no cover - robustesse
        logger.error("build_title: erreur lors de la génération du titre (%s)", exc, exc_info=True)
        return str(features.get("title") or "").strip()
