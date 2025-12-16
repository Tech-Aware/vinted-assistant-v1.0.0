# config/settings.py

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _load_dotenv_if_present(env_file: str | Path = ".env") -> None:
    """
    Charge un fichier `.env` local si présent et injecte les variables
    manquantes dans l'environnement process.

    Le chargement est volontairement minimaliste (pas de dépendance
    externe) et robuste :
    - ignore les lignes vides ou commentées
    - ne surcharge jamais une variable déjà définie dans l'environnement
    - journalise chaque variable ajoutée pour faciliter le diagnostic
    """
    env_path = Path(env_file)
    logger.debug("Recherche d'un fichier .env local à charger: %s", env_path)

    if not env_path.exists():
        logger.info("Aucun fichier .env trouvé à %s, passage en mode variables système.", env_path)
        return

    try:
        for line_no, raw_line in enumerate(env_path.read_text(encoding="utf-8").splitlines(), start=1):
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                logger.debug("Ligne %d ignorée dans .env (vide ou commentaire).", line_no)
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()

            if not key:
                logger.warning("Ligne %d du .env ignorée (clé vide).", line_no)
                continue

            if os.getenv(key) is None:
                os.environ[key] = value
                logger.debug("Variable %s chargée depuis .env.", key)
            else:
                logger.debug("Variable %s déjà définie dans l'environnement, .env laissé intact.", key)

        logger.info("Chargement du fichier .env terminé.")
    except Exception as exc:  # pragma: no cover - robustesse
        logger.exception("Echec du chargement du fichier .env: %s", exc)
        raise RuntimeError(f"Erreur lors du chargement du fichier .env: {exc}") from exc


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

    # ------------------------------------------------------------------
    # Chargement optionnel d'un fichier .env local
    # ------------------------------------------------------------------
    try:
        _load_dotenv_if_present()
    except Exception as env_exc:
        logger.error("Impossible de précharger le fichier .env: %s", env_exc, exc_info=True)
        raise

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
