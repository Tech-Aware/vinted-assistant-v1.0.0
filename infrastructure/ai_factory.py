# infrastructure/ai_factory.py

from __future__ import annotations

import logging
from typing import Dict

from config.settings import Settings
from domain.ai_provider import AIProviderName, AIListingProvider
from infrastructure.gemini_client import GeminiListingClient

# Import OpenAI seulement si clé présente (logique runtime)
try:
    from infrastructure.openai_client import OpenAIListingClient
except ImportError:
    OpenAIListingClient = None  # Ignoré si le fichier n'existe pas encore

logger = logging.getLogger(__name__)


def build_providers(settings: Settings) -> Dict[AIProviderName, AIListingProvider]:
    """
    Instancie les providers IA selon les clés API disponibles.

    Retourne un mapping :
        {
            AIProviderName.GEMINI: GeminiListingClient(...),
            AIProviderName.OPENAI: OpenAIListingClient(...),
        }

    Si aucune clé n'est définie, loggue et retourne un dict vide.
    """
    providers: Dict[AIProviderName, AIListingProvider] = {}

    # Gemini = toujours activé
    try:
        gemini_client = GeminiListingClient(settings)
        providers[AIProviderName.GEMINI] = gemini_client
        logger.info("Provider Gemini initialisé.")
    except Exception as exc:
        logger.error("Impossible d'initialiser Gemini: %s", exc)

    # OpenAI = seulement si clé présente
    if settings.openai_api_key:
        if OpenAIListingClient is not None:
            try:
                openai_client = OpenAIListingClient(settings)
                providers[AIProviderName.OPENAI] = openai_client
                logger.info("Provider OpenAI initialisé.")
            except Exception as exc:
                logger.error("Impossible d'initialiser OpenAI: %s", exc)
        else:
            logger.warning(
                "OPENAI_API_KEY définie mais OpenAIListingClient indisponible "
                "(fichier manquant)."
            )
    else:
        logger.info("OPENAI_API_KEY absente : OpenAI désactivé.")

    if not providers:
        logger.critical("Aucun provider IA disponible.")
    else:
        logger.debug("Providers IA disponibles: %s", list(providers.keys()))

    return providers
