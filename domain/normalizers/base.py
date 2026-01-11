# domain/normalizers/base.py

"""
Fonctions de base et constantes pour les normalizers.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from domain.templates import AnalysisProfileName

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Alias de champs et normalisation générique
# ---------------------------------------------------------------------------

ALIASES = {
    "titre": "title",
    "nom": "title",
    "name": "title",
    "marque": "brand",
    "brand": "brand",
    "modele": "style",
    "style": "style",
    "motif": "pattern",
    "pattern": "pattern",
    "col": "neckline",
    "neckline": "neckline",
    "saison": "season",
    "season": "season",
    "defaut": "defects",
    "defects": "defects",
}

REQUIRED_KEYS = [
    "title",
    "description",
    "brand",
    "style",
    "pattern",
    "neckline",
    "season",
    "defects",
]

FEATURE_DEFAULTS: Dict[AnalysisProfileName, Dict[str, Any]] = {
    AnalysisProfileName.JEAN_LEVIS: {
        "brand": None,
        "model": None,
        "fit": None,
        "color": None,
        "size_fr": None,
        "size_us": None,
        "length": None,
        "cotton_percent": None,
        "elasthane_percent": None,
        "rise_type": None,
        "rise_cm": None,
        "gender": None,
        "sku": None,
        "sku_status": None,
    },
    AnalysisProfileName.PULL: {
        "brand": None,
        "is_vintage": None,
        "garment_type": None,
        "neckline": None,
        "pattern": None,
        "main_colors": None,
        "material": None,
        "cotton_percent": None,
        "wool_percent": None,
        "gender": None,
        "size": None,
        "size_estimated": None,
        "size_source": None,
        "sku": None,
        "sku_status": None,
        "is_pima": None,
        "colors": None,
    },
    AnalysisProfileName.JACKET_CARHART: {
        "brand": None,
        "model": None,
        "size": None,
        "color": None,
        "gender": None,
        "has_hood": None,
        "pattern": None,
        "lining": None,
        "closure": None,
        "patch_material": None,
        "is_camouflage": None,
        "is_realtree": None,
        "is_new_york": None,
        "sku": None,
        "sku_status": None,
    },
}


def normalize_listing(data: dict) -> dict:
    """
    Normalisation générique du JSON d'annonce :
    - applique les ALIASES
    - filtre les champs inattendus
    - remplit les clés requises manquantes à None.
    """
    if not isinstance(data, dict):
        logger.warning("normalize_listing: input is not dict (%r)", data)
        return {k: None for k in REQUIRED_KEYS}

    clean: Dict[str, Any] = {}

    for k, v in data.items():
        key = ALIASES.get(k.lower(), k.lower())
        if key not in REQUIRED_KEYS:
            logger.info("normalize_listing: unexpected field removed: %s", k)
            continue
        clean[key] = v

    for req in REQUIRED_KEYS:
        if req not in clean:
            clean[req] = None
            logger.info("normalize_listing: missing key filled as null: %s", req)

    return clean


def coerce_profile_name(
    profile_name: Optional[object],
) -> Optional[AnalysisProfileName]:
    """Convertit une chaîne ou un enum en AnalysisProfileName."""
    if isinstance(profile_name, AnalysisProfileName):
        return profile_name
    if isinstance(profile_name, str):
        value = profile_name.strip().lower()
        for enum_val in AnalysisProfileName:
            if enum_val.value == value:
                return enum_val
    return None


def apply_feature_defaults(
    profile_name: AnalysisProfileName, features: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Garantit un dictionnaire de features stable pour chaque profil,
    en pré-remplissant les clés attendues à None.
    """
    try:
        defaults = FEATURE_DEFAULTS.get(profile_name)
        if not defaults:
            return features
        merged = {**defaults}
        merged.update(features or {})
        return merged
    except Exception as exc:
        logger.warning("apply_feature_defaults: impossible d'appliquer les defaults (%s)", exc)
        return features


def normalize_tommy_brand(raw_brand: Optional[Any]) -> Optional[str]:
    """Normalise les variantes Tommy pour eviter "Hilfiger Denim"."""
    try:
        if raw_brand is None:
            return None
        brand_str = str(raw_brand).strip()
        if not brand_str:
            return None
        lowered = brand_str.lower()
        aliases = ["hilfiger denim", "tommy hilfiger denim"]
        for alias in aliases:
            if alias in lowered:
                logger.debug(
                    "normalize_tommy_brand: alias '%s' detecte, normalisation en Tommy Hilfiger",
                    alias,
                )
                return "Tommy Hilfiger"
        return brand_str
    except Exception as exc:
        logger.exception("normalize_tommy_brand: erreur de normalisation (%s)", exc)
        try:
            return str(raw_brand).strip()
        except Exception:
            return None


def normalize_pull_brand(raw_brand: Optional[Any]) -> Optional[str]:
    """
    Normalise les marques pour les pulls.

    Gere:
      - Tommy Hilfiger et ses variantes
      - Ralph Lauren et ses variantes
      - Autres marques connues
      - Retourne None si pas de marque (= vintage/unbranded)
    """
    try:
        if raw_brand is None:
            return None
        brand_str = str(raw_brand).strip()
        if not brand_str:
            return None

        lowered = brand_str.lower()

        # Tommy Hilfiger et variantes
        tommy_aliases = ["hilfiger denim", "tommy hilfiger denim", "tommy jeans"]
        for alias in tommy_aliases:
            if alias in lowered:
                logger.debug(
                    "normalize_pull_brand: alias Tommy '%s' detecte, normalisation en Tommy Hilfiger",
                    alias,
                )
                return "Tommy Hilfiger"
        if "tommy hilfiger" in lowered:
            return "Tommy Hilfiger"

        # Ralph Lauren et variantes
        ralph_aliases = [
            "polo ralph lauren",
            "polo by ralph lauren",
            "ralph lauren polo",
            "chaps ralph lauren",
        ]
        for alias in ralph_aliases:
            if alias in lowered:
                logger.debug(
                    "normalize_pull_brand: alias Ralph Lauren '%s' detecte",
                    alias,
                )
                return "Ralph Lauren"
        if "ralph lauren" in lowered:
            return "Ralph Lauren"

        # Retourne la marque telle quelle si detectee
        return brand_str

    except Exception as exc:
        logger.exception("normalize_pull_brand: erreur de normalisation (%s)", exc)
        try:
            return str(raw_brand).strip()
        except Exception:
            return None


def normalize_sizes(features: dict) -> dict:
    """
    Corrige les tailles US issues du modèle.
    Gère : "W28 L30", "W28L30", "W 28 L 30", "W28", "L30"
    """
    import re

    raw = features.get("size_us")
    if not raw:
        return features

    text = str(raw).upper().replace(" ", "")
    w_match = re.search(r"W(\d+)", text)
    l_match = re.search(r"L(\d+)", text)

    w = f"W{w_match.group(1)}" if w_match else None
    l = f"L{l_match.group(1)}" if l_match else None

    if w:
        features["size_us"] = w

    if l:
        if not features.get("length"):
            features["length"] = l

    return features
