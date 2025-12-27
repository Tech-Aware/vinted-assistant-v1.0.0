# main.py

from __future__ import annotations

import importlib
import logging
import sys
import traceback

from config.log_config import setup_logging
from config.settings import load_settings
from infrastructure.ai_factory import build_providers
from presentation.ui_app import VintedAIApp


def _verifier_dependances_images(logger: logging.Logger) -> None:
    """Vérifie la présence des dépendances images nécessaires (olefile pour Pillow)."""
    olefile_spec = importlib.util.find_spec("olefile")
    if olefile_spec is None:
        logger.error(
            "Dépendance image manquante : le paquet 'olefile' est absent. "
            "Installez-le (requirements.txt) pour éviter les avertissements Pillow et "
            "permettre le chargement des images OLE/Mic.",
        )
        return

    olefile_module = importlib.import_module("olefile")
    olefile_version = getattr(olefile_module, "__version__", "inconnue")
    logger.debug("Dépendance image 'olefile' détectée (version %s).", olefile_version)


def main() -> None:
    """
    Point d'entrée principal de l'application.

    - Initialise le logging
    - Charge la configuration (Settings)
    - Construit le provider IA (Gemini)
    - Lance l'interface graphique
    """
    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    setup_logging(logging.DEBUG)
    logger = logging.getLogger(__name__)
    logger.info("Démarrage de l'application Vinted Assistant (Gemini uniquement).")
    _verifier_dependances_images(logger)

    # ------------------------------------------------------------------
    # Chargement Settings
    # ------------------------------------------------------------------
    try:
        settings = load_settings()
        logger.debug("Settings chargés: %r", "good api key for gemini")
    except Exception as exc:
        logger.critical(
            "Impossible de charger la configuration (Settings). Erreur: %s",
            exc,
        )
        sys.exit(1)

    # ------------------------------------------------------------------
    # Initialisation du provider IA (Gemini)
    # ------------------------------------------------------------------
    try:
        providers = build_providers(settings)
        if not providers:
            logger.critical("Aucun provider IA disponible. Fermeture.")
            sys.exit(1)

        logger.info(
            "Providers IA initialisés: %s",
            [p.value for p in providers.keys()],
        )
    except Exception as exc:
        logger.critical(
            "Erreur lors de l'initialisation des providers IA: %s",
            exc,
        )
        sys.exit(1)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    try:
        app = VintedAIApp(providers)
        app.mainloop()

    except KeyboardInterrupt:
        logger.warning("Interruption clavier - fermeture.")
        sys.exit(0)

    except Exception as exc:
        logger.critical(
            "Erreur fatale inattendue dans mainloop:\n%s",
            traceback.format_exc(),
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
