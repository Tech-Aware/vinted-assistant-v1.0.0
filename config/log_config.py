# config/log_config.py

from __future__ import annotations

import logging
import logging.config
from typing import Any, Dict

# -----------------------------
# Niveau custom "SUCCESS"
# -----------------------------
SUCCESS_LEVEL = 25  # entre INFO (20) et WARNING (30)
logging.addLevelName(SUCCESS_LEVEL, "SUCCESS")


def success(self: logging.Logger, msg: str, *args: Any, **kwargs: Any) -> None:
    if self.isEnabledFor(SUCCESS_LEVEL):
        self._log(SUCCESS_LEVEL, msg, args, **kwargs)


if not hasattr(logging.Logger, "success"):
    setattr(logging.Logger, "success", success)


LOGGING_CONFIG: Dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
            "level": "DEBUG",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "DEBUG",
    },
}


def setup_logging(level: int = logging.DEBUG) -> None:
    """Initialise la configuration de logging de l'application."""
    try:
        config = dict(LOGGING_CONFIG)
        config["root"]["level"] = logging.getLevelName(level)
        logging.config.dictConfig(config)

        logger = logging.getLogger(__name__)
        logger.debug("Logging initialisé (sans coloration ANSI).")
        logger.success("Niveau SUCCESS activé (niveau=%s).", SUCCESS_LEVEL)

    except Exception:
        # Filet de sécurité : ne jamais casser l'app à cause du logging
        logging.basicConfig(level=level)
        logging.getLogger(__name__).exception("Échec setup_logging, fallback basicConfig.")
