# infrastructure/ai_factory.py

from __future__ import annotations

import logging
from typing import Dict

from config.settings import Settings
from domain.ai_provider import AIProviderName, AIListingProvider
from infrastructure.gemini_client import GeminiListingClient

logger = logging.getLogger(__name__)


def build_providers(settings: Settings) -> Dict[AIProviderName, AIListingProvider]:
    """
    Instancie les providers IA disponibles.

    Retourne un mapping avec uniquement Gemini :
        {AIProviderName.GEMINI: GeminiListingClient(...)}

    Si aucune clé n'est définie, loggue et retourne un dict vide.
    """
    providers: Dict[AIProviderName, AIListingProvider] = {}

    # Gemini = provider unique
    try:
        gemini_client = GeminiListingClient(settings)
        providers[AIProviderName.GEMINI] = gemini_client
        logger.info("Provider Gemini initialisé.")
    except Exception as exc:
        logger.error("Impossible d'initialiser Gemini: %s", exc)

    if not providers:
        logger.critical("Aucun provider IA disponible.")
    else:
        logger.debug("Providers IA disponibles: %s", list(providers.keys()))

    return providers
