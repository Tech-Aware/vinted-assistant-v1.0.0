# main.py

from __future__ import annotations

import logging
import sys
import traceback

from config.log_config import setup_logging
from config.settings import load_settings
from infrastructure.ai_factory import build_providers
from presentation.ui_app import VintedAIApp


def main() -> None:
    """
    Point d'entrée principal de l'application.

    - Initialise le logging
    - Charge la configuration (Settings)
    - Construit les providers IA (Gemini / OpenAI)
    - Lance l'interface graphique
    """
    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    setup_logging(logging.DEBUG)
    logger = logging.getLogger(__name__)
    logger.info("Démarrage de l'application Vinted Assistant (multi-provider).")

    # ------------------------------------------------------------------
    # Chargement Settings
    # ------------------------------------------------------------------
    try:
        settings = load_settings()
        logger.debug("Settings chargés: %r", settings)
    except Exception as exc:
        logger.critical(
            "Impossible de charger la configuration (Settings). Erreur: %s",
            exc,
        )
        sys.exit(1)

    # ------------------------------------------------------------------
    # Initialisation des providers IA (Gemini / OpenAI)
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
