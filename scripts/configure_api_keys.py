#!/usr/bin/env python3
"""Assistant interactif pour configurer les clés API et modèles par défaut.

- Propose Gemini et OpenAI
- Enregistre les variables dans un fichier .env local
- Affiche un message rappelant que Gemini donne les meilleurs résultats
  actuels par rapport à ChatGPT dans cette application

Pensé pour les nouvelles machines (dont Chromebook/Crostini) où aucune
clé n'est encore paramétrée. Le script privilégie une journalisation
lisible et une gestion d'erreurs explicite.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Dict

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

PROVIDERS: Dict[str, Dict[str, str]] = {
    "gemini": {
        "api_key_env": "GEMINI_API_KEY",
        "model_env": "GEMINI_MODEL",
        "default_model": "gemini-2.5-flash",
    },
    "openai": {
        "api_key_env": "OPENAI_API_KEY",
        "model_env": "OPENAI_MODEL",
        "default_model": "gpt-4o-mini",
    },
}


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(message)s",
    )


def _safe_input(prompt: str) -> str:
    try:
        return input(prompt)
    except KeyboardInterrupt:
        logging.error("Arrêt utilisateur. Configuration abandonnée.")
        sys.exit(1)
    except Exception as exc:  # pragma: no cover - robustesse
        logging.exception("Erreur inattendue pendant la saisie: %s", exc)
        sys.exit(1)


def _load_existing_env(env_path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not env_path.exists():
        logging.info("Aucun fichier .env existant, une nouvelle configuration sera créée.")
        return values

    logging.info("Chargement des variables existantes depuis %s", env_path)
    try:
        for line_no, raw_line in enumerate(env_path.read_text(encoding="utf-8").splitlines(), start=1):
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                logging.debug("Ligne %d ignorée dans le .env", line_no)
                continue
            key, value = line.split("=", 1)
            if key:
                values[key.strip()] = value.strip()
    except Exception as exc:  # pragma: no cover - robustesse
        logging.exception("Impossible de lire le fichier .env: %s", exc)
        sys.exit(1)

    return values


def _prompt_provider() -> str:
    logging.info(
        "Conseil : Gemini fournit actuellement les meilleurs résultats visuels et textuels sur l'application."
    )
    logging.info("Tu peux tout de même sélectionner OpenAI si tu préfères ChatGPT.")

    providers_list = ", ".join(PROVIDERS.keys())
    while True:
        choice = _safe_input(f"Quel provider veux-tu utiliser par défaut ? ({providers_list}) : ").strip().lower()
        if choice in PROVIDERS:
            logging.info("Provider sélectionné: %s", choice)
            return choice
        logging.warning("Choix invalide. Merci de saisir l'une des valeurs: %s", providers_list)


def _prompt_api_key(provider: str) -> str:
    env_name = PROVIDERS[provider]["api_key_env"]
    while True:
        key = _safe_input(f"Saisis la clé API pour {provider} ({env_name}) : ").strip()
        if key:
            logging.info("Clé %s capturée (longueur: %d).", env_name, len(key))
            return key
        logging.warning("La clé ne peut pas être vide. Recommence.")


def _prompt_model(provider: str) -> str:
    default_model = PROVIDERS[provider]["default_model"]
    model = _safe_input(
        f"Modèle à utiliser pour {provider} (Entrée pour défaut '{default_model}') : "
    ).strip()
    if not model:
        model = default_model
    logging.info("Modèle retenu pour %s: %s", provider, model)
    return model


def _maybe_store_secondary(provider_selected: str, env_data: Dict[str, str]) -> None:
    """Propose d'ajouter la clé de l'autre provider (facultatif)."""
    secondary = "openai" if provider_selected == "gemini" else "gemini"
    answer = _safe_input(f"Souhaites-tu aussi renseigner la clé {secondary} (o/n) ? ").strip().lower()
    if not answer or answer.startswith("n"):
        logging.info("Clé %s laissée vide.", secondary)
        return

    key = _prompt_api_key(secondary)
    model = _prompt_model(secondary)
    env_data[PROVIDERS[secondary]["api_key_env"]] = key
    env_data[PROVIDERS[secondary]["model_env"]] = model


def _write_env(env_path: Path, env_data: Dict[str, str]) -> None:
    try:
        lines = [f"{key}={value}" for key, value in env_data.items()]
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        logging.info("Fichier .env mis à jour dans %s", env_path)
    except Exception as exc:  # pragma: no cover - robustesse
        logging.exception("Impossible d'écrire le fichier .env: %s", exc)
        sys.exit(1)


def main() -> None:
    setup_logging()
    logging.info("===== Assistant de configuration des clés API =====")
    logging.info("Ce guide va enregistrer les clés et modèles dans .env pour l'application.")

    env_data = _load_existing_env(ENV_PATH)

    provider = _prompt_provider()
    env_data[PROVIDERS[provider]["api_key_env"]] = _prompt_api_key(provider)
    env_data[PROVIDERS[provider]["model_env"]] = _prompt_model(provider)

    _maybe_store_secondary(provider, env_data)
    _write_env(ENV_PATH, env_data)

    logging.info("Configuration terminée. Les prochaines exécutions utiliseront %s par défaut.", provider)


if __name__ == "__main__":
    main()
