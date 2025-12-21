#!/usr/bin/env python3
"""Assistant interactif pour configurer les clés API et modèles par défaut.

- Propose Gemini avec deux modèles (gemini-3-pro-preview par défaut, gemini-2.5-flash en option)
- Enregistre les variables dans un fichier .env local

Pensé pour les nouvelles machines (dont Chromebook/Crostini) où aucune
clé n'est encore paramétrée. Le script privilégie une journalisation
lisible et une gestion d'erreurs explicite.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Dict, Iterable

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
DEFAULT_SHELL_RC = Path.home() / ".bashrc"

GEMINI_API_ENV = "GEMINI_API_KEY"
GEMINI_MODEL_ENV = "GEMINI_MODEL"
DEFAULT_GEMINI_MODEL = "gemini-3-pro-preview"
FALLBACK_GEMINI_MODEL = "gemini-2.5-flash"
ALLOWED_GEMINI_MODELS = (DEFAULT_GEMINI_MODEL, FALLBACK_GEMINI_MODEL)


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
    logging.info("Seul le provider Gemini est disponible dans cette version.")
    return "gemini"


def _prompt_api_key(provider: str) -> str:
    env_name = GEMINI_API_ENV
    while True:
        key = _safe_input(f"Saisis la clé API pour {provider} ({env_name}) : ").strip()
        if key:
            logging.info("Clé %s capturée (longueur: %d).", env_name, len(key))
            return key
        logging.warning("La clé ne peut pas être vide. Recommence.")


def _prompt_model(provider: str) -> str:
    default_model = DEFAULT_GEMINI_MODEL
    choice_list = " / ".join(ALLOWED_GEMINI_MODELS)
    while True:
        model = _safe_input(
            f"Modèle Gemini à utiliser ({choice_list}) [Entrée pour '{default_model}'] : "
        ).strip()
        if not model:
            model = default_model
        if model not in ALLOWED_GEMINI_MODELS:
            logging.warning(
                "Modèle inconnu. Merci de choisir parmi: %s.",
                choice_list,
            )
            continue
        cleaned = _normalize_model_name(model)
        logging.info("Modèle retenu pour %s: %s", provider, cleaned)
        return cleaned


def _normalize_model_name(model_name: str) -> str:
    """Assure un format compatible (ex: "models/gemini-2.5-flash")."""

    cleaned = (model_name or "").strip().strip("\"' ")
    if not cleaned:
        logging.error("Nom de modèle vide ou invalide.")
        raise SystemExit(1)

    if not cleaned.startswith("models/"):
        logging.warning(
            "Nom de modèle sans préfixe 'models/': %s. Préfixage automatique...",
            cleaned,
        )
        cleaned = f"models/{cleaned}"

    return cleaned


def _append_shell_exports(env_data: Dict[str, str], targets: Iterable[Path]) -> None:
    lines = ["# Variables Vinted Assistant (Gemini)"]

    for key, value in env_data.items():
        if "API_KEY" in key:
            lines.append(f"export {key}=\"{value}\"")

    block = "\n" + "\n".join(lines) + "\n"

    for target in targets:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            content = ""
            if target.exists():
                content = target.read_text(encoding="utf-8")
                if "Variables Vinted Assistant" in content:
                    logging.info("Bloc d'export déjà présent dans %s, aucune modification.", target)
                    continue

            target.write_text(content + block, encoding="utf-8")
            logging.info("Exports shell ajoutés dans %s", target)
        except Exception as exc:  # pragma: no cover - robustesse
            logging.exception("Impossible d'ajouter les exports dans %s: %s", target, exc)


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
    logging.info("Ce guide va enregistrer la clé et le modèle Gemini dans .env pour l'application.")

    env_data = _load_existing_env(ENV_PATH)

    provider = _prompt_provider()
    env_data[GEMINI_API_ENV] = _prompt_api_key(provider)
    env_data[GEMINI_MODEL_ENV] = _prompt_model(provider)

    _write_env(ENV_PATH, env_data)

    answer = _safe_input(
        "Ajouter aussi les exports GEMINI dans ton shell (~/.bashrc) ? (o/N) : "
    ).strip().lower()
    if answer.startswith("o"):
        _append_shell_exports(env_data, targets=[DEFAULT_SHELL_RC])
    else:
        logging.info("Exports shell non ajoutés (réponse: %s).", answer or "entrée vide")

    logging.info("Configuration terminée. Les prochaines exécutions utiliseront %s par défaut.", provider)


if __name__ == "__main__":
    main()
