# main.py

from __future__ import annotations

import warnings

# Suppress FutureWarnings from Google API packages before importing them
# - google.generativeai deprecation warning (package replaced by google.genai)
# - google.api_core Python version support warning
warnings.filterwarnings("ignore", category=FutureWarning, message=".*google.generativeai.*")
warnings.filterwarnings("ignore", category=FutureWarning, message=".*Python version.*google.*")

import argparse
import importlib
import logging
import os
import signal
import sys
import threading
import traceback

from config.log_config import setup_logging
from config.settings import load_settings
from domain.ai_provider import AIProviderName
from infrastructure.ai_factory import build_providers
from infrastructure.browser_bridge import start_bridge, stop_bridge


def _get_log_level() -> int:
    """
    Récupère le niveau de log depuis la variable d'environnement LOG_LEVEL.
    Par défaut : INFO en production pour éviter l'exposition de données sensibles.
    Valeurs acceptées : DEBUG, INFO, WARNING, ERROR, CRITICAL
    """
    level_name = os.getenv("LOG_LEVEL", "INFO").upper().strip()
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "WARN": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    return level_map.get(level_name, logging.INFO)


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
    - Lance l'interface graphique ou le mode headless (--headless)
    """
    # ------------------------------------------------------------------
    # Arguments CLI
    # ------------------------------------------------------------------
    parser = argparse.ArgumentParser(description="Vinted Assistant")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Mode headless : serveur API seulement, sans interface graphique.",
    )
    args = parser.parse_args()

    # ------------------------------------------------------------------
    # Logging (configurable via LOG_LEVEL env var, default: INFO)
    # ------------------------------------------------------------------
    log_level = _get_log_level()
    setup_logging(log_level)
    logger = logging.getLogger(__name__)
    mode_label = "headless (API)" if args.headless else "GUI"
    logger.info(
        "Démarrage de l'application Vinted Assistant (mode %s). Log level: %s",
        mode_label,
        logging.getLevelName(log_level),
    )
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

    # Récupérer le provider Gemini pour le bridge
    gemini_provider = providers.get(AIProviderName.GEMINI)

    # ------------------------------------------------------------------
    # Serveur HTTP Bridge (communication avec extension Chrome)
    # ------------------------------------------------------------------
    try:
        bridge = start_bridge(port=8765, provider=gemini_provider)
        logger.info("Serveur HTTP Bridge démarré sur http://localhost:8765")
    except Exception as exc:
        logger.warning(
            "Impossible de démarrer le serveur HTTP Bridge: %s. "
            "Le transfert vers Vinted ne sera pas disponible.",
            exc,
        )
        bridge = None

    # ------------------------------------------------------------------
    # Mode headless ou GUI
    # ------------------------------------------------------------------
    if args.headless:
        logger.info(
            "Mode headless actif : serveur API sur http://localhost:8765 "
            "(Ctrl+C pour arrêter)"
        )
        shutdown_event = threading.Event()
        signal.signal(signal.SIGINT, lambda *_: shutdown_event.set())
        signal.signal(signal.SIGTERM, lambda *_: shutdown_event.set())
        try:
            shutdown_event.wait()
        except KeyboardInterrupt:
            pass
        logger.info("Arrêt du mode headless.")
    else:
        # Import GUI seulement si nécessaire (évite besoin de display en headless)
        from presentation.ui_app import VintedAIApp

        try:
            app = VintedAIApp(providers)
            app.mainloop()

        except KeyboardInterrupt:
            logger.warning("Interruption clavier - fermeture.")

        except Exception as exc:
            logger.critical(
                "Erreur fatale inattendue dans mainloop:\n%s",
                traceback.format_exc(),
            )
            sys.exit(1)

    # Arrêt propre du serveur HTTP
    if bridge:
        try:
            stop_bridge()
            logger.info("Serveur HTTP Bridge arrêté proprement.")
        except Exception as exc_stop:
            logger.warning("Erreur lors de l'arrêt du serveur HTTP: %s", exc_stop)


if __name__ == "__main__":
    main()
