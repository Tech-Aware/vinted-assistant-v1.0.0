# domain/description_engine.py

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from domain.description_builder import (
    build_jacket_carhart_description,
    build_jean_levis_description,
    build_pull_tommy_description,
)
from domain.templates import AnalysisProfileName

logger = logging.getLogger(__name__)


def build_description_jean_levis(
    features: Dict[str, Any], ai_description: Optional[str] = None, ai_defects: Optional[str] = None
) -> str:
    return build_jean_levis_description(features, ai_description=ai_description, ai_defects=ai_defects)


def build_description_pull_tommy(
    features: Dict[str, Any], ai_description: Optional[str] = None, ai_defects: Optional[str] = None
) -> str:
    return build_pull_tommy_description(features, ai_description=ai_description, ai_defects=ai_defects)


def build_description_jacket_carhart(
    features: Dict[str, Any], ai_description: Optional[str] = None, ai_defects: Optional[str] = None
) -> str:
    return build_jacket_carhart_description(features, ai_description=ai_description, ai_defects=ai_defects)


def build_description(
    profile_name: AnalysisProfileName,
    features: Dict[str, Any],
    ai_description: Optional[str] = None,
    ai_defects: Optional[str] = None,
) -> str:
    """
    Point d'entrée unique pour construire les descriptions finales depuis les features.
    Expose aussi des fonctions dédiées par profil pour clarifier la logique métier.
    """
    try:
        if profile_name == AnalysisProfileName.JEAN_LEVIS:
            return build_description_jean_levis(features, ai_description=ai_description, ai_defects=ai_defects)
        if profile_name == AnalysisProfileName.PULL_TOMMY:
            return build_description_pull_tommy(features, ai_description=ai_description, ai_defects=ai_defects)
        if profile_name == AnalysisProfileName.JACKET_CARHART:
            return build_description_jacket_carhart(features, ai_description=ai_description, ai_defects=ai_defects)

        fallback = (ai_description or "").strip()
        logger.debug("Profil %s non géré par le moteur de description, fallback brut.", profile_name)
        return fallback
    except Exception as exc:  # pragma: no cover - robustesse
        logger.error(
            "build_description: erreur lors de la génération de la description (%s)",
            exc,
            exc_info=True,
        )
        return (ai_description or "").strip()
