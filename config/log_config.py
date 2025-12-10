# config/log_config.py

from __future__ import annotations

import logging
import logging.config


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": (
                "%(asctime)s | %(levelname)-8s | %(name)s | "
                "%(funcName)s:%(lineno)d | %(message)s"
            ),
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
    """
    Initialise la configuration de logging de l'application.

    À appeler une seule fois au démarrage de l'application
    (par exemple dans main.py).
    """
    config = LOGGING_CONFIG.copy()
    # Surcharge possible du niveau de log racine via l'argument
    config["root"]["level"] = logging.getLevelName(level)
    logging.config.dictConfig(config)
