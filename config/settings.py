# config/settings.py

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Settings:
    """
    Configuration applicative centrale.

    - gemini_api_key  : clé API Gemini (obligatoire aujourd'hui)
    - gemini_model    : nom du modèle Gemini
    - openai_api_key  : clé API OpenAI (optionnelle)
    - openai_model    : nom du modèle OpenAI (par défaut gpt-4o-mini)
    """
    gemini_api_key: str
    gemini_model: str = "gemini-2.5-flash"

    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"


def load_settings() -> Settings:
    """
    Charge la configuration à partir des variables d’environnement.

    Variables prises en compte :
    - GEMINI_API_KEY  (obligatoire)
    - GEMINI_MODEL    (optionnelle)
    - OPENAI_API_KEY  (optionnelle)
    - OPENAI_MODEL    (optionnelle)

    Lève RuntimeError en cas de problème bloquant
    et loggue en détail l’erreur.
    """
    logger.debug("Chargement des Settings depuis les variables d'environnement.")

    try:
        # GEMINI
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key is None or not gemini_key.strip():
            logger.error(
                "La variable d'environnement GEMINI_API_KEY est manquante ou vide."
            )
            raise RuntimeError(
                "GEMINI_API_KEY est manquante ou vide. "
                "Définis-la dans ton système ou dans la configuration de ton IDE."
            )

        gemini_model_env = os.getenv("GEMINI_MODEL")
        if gemini_model_env is not None and gemini_model_env.strip():
            gemini_model = gemini_model_env.strip()
        else:
            gemini_model = "gemini-2.5-flash"
            if gemini_model_env is not None:
                logger.warning(
                    "GEMINI_MODEL est défini mais vide, utilisation du modèle par défaut '%s'.",
                    gemini_model,
                )

        # OPENAI (optionnel)
        openai_key_env = os.getenv("OPENAI_API_KEY")
        openai_key = openai_key_env.strip() if openai_key_env and openai_key_env.strip() else None

        openai_model_env = os.getenv("OPENAI_MODEL")
        if openai_model_env is not None and openai_model_env.strip():
            openai_model = openai_model_env.strip()
        else:
            openai_model = "gpt-4o-mini"
            if openai_model_env is not None:
                logger.warning(
                    "OPENAI_MODEL est défini mais vide, utilisation du modèle par défaut '%s'.",
                    openai_model,
                )

        settings = Settings(
            gemini_api_key=gemini_key.strip(),
            gemini_model=gemini_model,
            openai_api_key=openai_key,
            openai_model=openai_model,
        )

        logger.info(
            "Settings chargés avec succès (Gemini='%s', OpenAI_model='%s', OpenAI_key=%s).",
            settings.gemini_model,
            settings.openai_model,
            "présente" if settings.openai_api_key else "absente",
        )
        return settings

    except RuntimeError:
        # Erreur fonctionnelle déjà logguée, on la propage telle quelle
        raise
    except Exception as exc:
        # Erreur inattendue : on loggue et on encapsule
        logger.exception("Erreur inattendue lors du chargement des Settings.")
        raise RuntimeError(
            f"Erreur inattendue lors du chargement de la configuration: {exc}"
        ) from exc
