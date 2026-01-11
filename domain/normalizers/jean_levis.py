# domain/normalizers/jean_levis.py

"""
Builder de features pour le profil JEAN_LEVIS.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from domain.normalizers.text_extractors import (
    extract_model_from_text,
    extract_fit_from_text,
    extract_color_from_text,
    extract_sizes_from_text,
    normalize_fit_label,
    normalize_sku_value,
)

logger = logging.getLogger(__name__)


def build_features_for_jean_levis(
    ai_data: Dict[str, Any],
    ui_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Construit le dict 'features' attendu par build_jean_levis_title à partir :
      - ai_data : JSON renvoyé par l'IA (Gemini)
      - ui_data : données saisies dans l'UI (taille FR/US, corrections SKU/genre, etc.)

    Règles :
      - On utilise en priorité le bloc ai_data["features"] (cas Gemini).
      - Si une info manque, on va la chercher dans ai_data (titre + description).
      - On n'invente pas de valeurs précises.
    """
    ui_data = ui_data or {}
    raw_features = ai_data.get("features") or {}

    title = ai_data.get("title") or ""
    description = ai_data.get("description") or ""
    full_text = f"{title} {description}"

    # --- Brand -------------------------------------------------------------
    brand = raw_features.get("brand") or ai_data.get("brand")

    # --- Model -------------------------------------------------------------
    model = raw_features.get("model") or ai_data.get("model")
    if not model:
        model = extract_model_from_text(full_text)

    # --- Fit ---------------------------------------------------------------
    fit = raw_features.get("fit") or ai_data.get("fit")
    fit = normalize_fit_label(fit)
    if not fit:
        fit = extract_fit_from_text(full_text)

    # --- Color -------------------------------------------------------------
    color = raw_features.get("color") or ai_data.get("color")
    if not color:
        color = extract_color_from_text(full_text)

    # --- Taille FR / US ----------------------------------------------------
    size_fr = (
        ui_data.get("size_fr")
        or raw_features.get("size_fr")
        or ai_data.get("size_fr")
    )

    size_us = (
        ui_data.get("size_us")
        or raw_features.get("size_us")
        or ai_data.get("size_us")
    )
    length = raw_features.get("length") or ai_data.get("length")

    if not size_us or not length:
        inferred_us, inferred_len = extract_sizes_from_text(full_text)
        if not size_us and inferred_us:
            size_us = inferred_us
        if not length and inferred_len:
            length = inferred_len

    # --- Composition -------------------------------------------------------
    cotton_percent = raw_features.get("cotton_percent") or ai_data.get("cotton_percent")
    elasthane_percent = raw_features.get("elasthane_percent") or ai_data.get("elasthane_percent")

    # --- Rise --------------------------------------------------------------
    rise_cm = raw_features.get("rise_cm") or ai_data.get("rise_cm")
    rise_type = raw_features.get("rise_type") or ai_data.get("rise_type")

    # --- Genre -------------------------------------------------------------
    gender = (
        ui_data.get("gender")
        or raw_features.get("gender")
        or ai_data.get("gender")
    )

    # --- SKU ---------------------------------------------------------------
    raw_sku = ui_data.get("sku") or raw_features.get("sku") or ai_data.get("sku")
    sku = normalize_sku_value(raw_sku)

    if sku is None:
        if raw_sku:
            sku_status = "invalid"
            logger.info(
                "build_features_for_jean_levis: SKU détecté mais invalide (%r)",
                raw_sku,
            )
        else:
            sku_status = "missing"
    else:
        sku_status = "ok"

    if sku is None and raw_sku:
        logger.info(
            "build_features_for_jean_levis: SKU ignoré (placeholder/invalid) raw=%r",
            raw_sku,
        )

    features: Dict[str, Any] = {
        "brand": brand,
        "model": model,
        "fit": fit,
        "color": color,
        "size_fr": size_fr,
        "size_us": size_us,
        "length": length,
        "cotton_percent": cotton_percent,
        "elasthane_percent": elasthane_percent,
        "rise_type": rise_type,
        "rise_cm": rise_cm,
        "gender": gender,
        "sku": sku,
        "sku_status": sku_status,
    }

    logger.debug("build_features_for_jean_levis: features=%s", features)
    return features
