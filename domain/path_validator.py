# domain/path_validator.py

"""
Validation sécurisée des chemins de fichiers.

Ce module fournit des utilitaires pour valider les chemins de fichiers
et prévenir les attaques de type path traversal.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Optional, Sequence

logger = logging.getLogger(__name__)

# Extensions d'images autorisées
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff"}

# Taille maximale d'un fichier image (50 MB)
MAX_IMAGE_SIZE_BYTES = 50 * 1024 * 1024


class PathValidationError(ValueError):
    """Exception levée lors d'une erreur de validation de chemin."""

    pass


def _get_allowed_directories() -> List[Path]:
    """
    Retourne la liste des répertoires autorisés pour les fichiers images.

    Par défaut :
    - Répertoire de l'utilisateur (home)
    - Répertoires temporaires système
    - Répertoire courant de l'application

    Peut être étendu via la variable d'environnement VINTED_ALLOWED_DIRS
    (chemins séparés par des point-virgules).
    """
    allowed = []

    # Répertoire home de l'utilisateur
    try:
        home = Path.home()
        if home.exists():
            allowed.append(home)
    except Exception:
        pass

    # Répertoire courant
    try:
        cwd = Path.cwd()
        if cwd.exists():
            allowed.append(cwd)
    except Exception:
        pass

    # Répertoires temporaires
    import tempfile

    try:
        temp_dir = Path(tempfile.gettempdir())
        if temp_dir.exists():
            allowed.append(temp_dir)
    except Exception:
        pass

    # Répertoires personnalisés via variable d'environnement
    custom_dirs = os.getenv("VINTED_ALLOWED_DIRS", "")
    if custom_dirs:
        for dir_path in custom_dirs.split(";"):
            try:
                p = Path(dir_path.strip())
                if p.exists() and p.is_dir():
                    allowed.append(p)
            except Exception:
                continue

    return allowed


def is_path_safe(path: Path, allowed_dirs: Optional[List[Path]] = None) -> bool:
    """
    Vérifie si un chemin est sûr (pas de path traversal).

    Args:
        path: Le chemin à vérifier
        allowed_dirs: Liste des répertoires autorisés (par défaut: home, temp, cwd)

    Returns:
        True si le chemin est sûr, False sinon
    """
    if allowed_dirs is None:
        allowed_dirs = _get_allowed_directories()

    try:
        # Résoudre le chemin pour éliminer les .. et liens symboliques
        resolved = path.resolve()

        # Vérifier que le chemin résolu est dans un répertoire autorisé
        for allowed in allowed_dirs:
            try:
                allowed_resolved = allowed.resolve()
                # is_relative_to disponible en Python 3.9+
                if resolved.is_relative_to(allowed_resolved):
                    return True
            except (ValueError, AttributeError):
                # Fallback pour Python < 3.9
                try:
                    resolved.relative_to(allowed_resolved)
                    return True
                except ValueError:
                    continue

        return False

    except (OSError, ValueError) as exc:
        logger.warning("Impossible de valider le chemin %s: %s", path, exc)
        return False


def validate_image_path(
    path: Path,
    allowed_dirs: Optional[List[Path]] = None,
    check_exists: bool = True,
    check_extension: bool = True,
    check_size: bool = True,
) -> Path:
    """
    Valide un chemin d'image et retourne le chemin résolu.

    Args:
        path: Le chemin de l'image à valider
        allowed_dirs: Liste des répertoires autorisés
        check_exists: Vérifier que le fichier existe
        check_extension: Vérifier que l'extension est autorisée
        check_size: Vérifier que la taille du fichier est raisonnable

    Returns:
        Le chemin résolu et validé

    Raises:
        PathValidationError: Si la validation échoue
    """
    try:
        resolved = path.resolve()
    except (OSError, ValueError) as exc:
        raise PathValidationError(f"Chemin invalide '{path}': {exc}") from exc

    # Vérification path traversal
    if not is_path_safe(resolved, allowed_dirs):
        logger.warning(
            "Tentative d'accès à un chemin non autorisé: %s (résolu: %s)",
            path,
            resolved,
        )
        raise PathValidationError(
            f"Chemin non autorisé: {path}. "
            "Le fichier doit être dans le répertoire utilisateur ou un répertoire autorisé."
        )

    # Vérification existence
    if check_exists and not resolved.exists():
        raise PathValidationError(f"Fichier introuvable: {resolved}")

    # Vérification que c'est bien un fichier (pas un répertoire)
    if check_exists and not resolved.is_file():
        raise PathValidationError(f"Le chemin n'est pas un fichier: {resolved}")

    # Vérification extension
    if check_extension:
        ext = resolved.suffix.lower()
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            raise PathValidationError(
                f"Extension non autorisée: {ext}. "
                f"Extensions acceptées: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}"
            )

    # Vérification taille
    if check_size and check_exists:
        try:
            size = resolved.stat().st_size
            if size > MAX_IMAGE_SIZE_BYTES:
                raise PathValidationError(
                    f"Fichier trop volumineux: {size / (1024*1024):.1f} MB. "
                    f"Maximum: {MAX_IMAGE_SIZE_BYTES / (1024*1024):.0f} MB"
                )
            if size == 0:
                raise PathValidationError(f"Fichier vide: {resolved}")
        except OSError as exc:
            raise PathValidationError(f"Impossible de lire le fichier: {exc}") from exc

    logger.debug("Chemin image validé: %s", resolved)
    return resolved


def validate_image_paths(
    paths: Sequence[Path],
    allowed_dirs: Optional[List[Path]] = None,
    check_exists: bool = True,
    check_extension: bool = True,
    check_size: bool = True,
) -> List[Path]:
    """
    Valide une liste de chemins d'images.

    Args:
        paths: Liste des chemins à valider
        allowed_dirs: Liste des répertoires autorisés
        check_exists: Vérifier que les fichiers existent
        check_extension: Vérifier les extensions
        check_size: Vérifier les tailles

    Returns:
        Liste des chemins validés et résolus

    Raises:
        PathValidationError: Si au moins un chemin est invalide
    """
    validated = []
    errors = []

    for path in paths:
        try:
            validated_path = validate_image_path(
                path,
                allowed_dirs=allowed_dirs,
                check_exists=check_exists,
                check_extension=check_extension,
                check_size=check_size,
            )
            validated.append(validated_path)
        except PathValidationError as exc:
            errors.append(str(exc))

    if errors:
        raise PathValidationError(
            f"Erreurs de validation pour {len(errors)} fichier(s):\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    return validated
