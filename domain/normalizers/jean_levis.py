# domain/normalizers/jean_levis.py

"""
Builder de features pour le profil JEAN_LEVIS.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, List

from domain.normalizers.text_extractors import (
    extract_model_from_text,
    extract_fit_from_text,
    extract_color_from_text,
    extract_sizes_from_text,
    normalize_fit_label,
    normalize_sku_value,
    extract_gender_from_sku_prefix,
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
    material = raw_features.get("material") or ai_data.get("material")

    # --- Rise --------------------------------------------------------------
    rise_cm = raw_features.get("rise_cm") or ai_data.get("rise_cm")
    rise_type = raw_features.get("rise_type") or ai_data.get("rise_type")

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

    # --- OCR structuré (fallback SKU + composition) -----------------------
    ocr_structured = ui_data.get("ocr_structured") if isinstance(ui_data, dict) else None
    ocr_sku_candidates = ai_data.get("_ocr_sku_candidates")
    if not isinstance(ocr_sku_candidates, list):
        ocr_sku_candidates = []

    if ocr_structured and isinstance(ocr_structured, dict):
        ocr_candidates_from_structured = ocr_structured.get("sku_candidates") or []
        if isinstance(ocr_candidates_from_structured, list):
            ocr_sku_candidates.extend(ocr_candidates_from_structured)
        else:
            logger.warning(
                "build_features_for_jean_levis: sku_candidates OCR structuré invalide (%r)",
                type(ocr_candidates_from_structured),
            )

        if not material:
            material = _build_material_from_ocr(ocr_structured)
            if material:
                logger.info(
                    "build_features_for_jean_levis: composition OCR structurée retenue (%s)",
                    material,
                )
            else:
                logger.debug(
                    "build_features_for_jean_levis: composition OCR structurée absente ou illisible."
                )

        if cotton_percent is None or elasthane_percent is None:
            ocr_cotton, ocr_elasthane = _extract_cotton_elasthane(ocr_structured)
            if cotton_percent is None and ocr_cotton is not None:
                cotton_percent = ocr_cotton
                logger.info(
                    "build_features_for_jean_levis: coton OCR structuré retenu (%s%%)",
                    cotton_percent,
                )
            if elasthane_percent is None and ocr_elasthane is not None:
                elasthane_percent = ocr_elasthane
                logger.info(
                    "build_features_for_jean_levis: élasthanne OCR structuré retenu (%s%%)",
                    elasthane_percent,
                )
    elif ocr_structured:
        logger.warning(
            "build_features_for_jean_levis: ocr_structured ignoré (format inattendu=%r)",
            type(ocr_structured),
        )

    if sku is None:
        sku = _pick_sku_from_ocr_candidates(ocr_sku_candidates)
        if sku:
            sku_status = "ok"
            logger.info(
                "build_features_for_jean_levis: SKU OCR structuré retenu (%s)",
                sku,
            )

    # --- Genre -------------------------------------------------------------
    # Priorité : UI > IA > SKU prefix
    ai_gender = (
        ui_data.get("gender")
        or raw_features.get("gender")
        or ai_data.get("gender")
    )

    # Extraire le genre depuis le préfixe du SKU (JLF=femme, JLH=homme)
    sku_gender = extract_gender_from_sku_prefix(sku)

    # Validation de cohérence SKU ↔ genre IA
    if sku_gender and ai_gender:
        ai_gender_normalized = ai_gender.strip().lower()
        if ai_gender_normalized != sku_gender:
            logger.warning(
                "build_features_for_jean_levis: INCOHÉRENCE genre IA (%s) vs SKU (%s) - "
                "utilisation du genre SKU (%s)",
                ai_gender,
                sku,
                sku_gender,
            )
            gender = sku_gender
        else:
            gender = ai_gender
    elif sku_gender:
        # Le SKU indique le genre, l'IA n'a rien détecté
        logger.info(
            "build_features_for_jean_levis: genre déduit du SKU %s -> %s",
            sku,
            sku_gender,
        )
        gender = sku_gender
    elif ai_gender:
        # L'IA a détecté le genre, pas de SKU pour valider
        gender = ai_gender
    else:
        # Aucune information sur le genre
        gender = None

    # --- Order ID ----------------------------------------------------------
    order_id = ui_data.get("order_id")

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
        "order_id": order_id,
        "material": material,
    }

    logger.debug("build_features_for_jean_levis: features=%s", features)
    return features


def _pick_sku_from_ocr_candidates(candidates: List[Any]) -> Optional[str]:
    if not candidates:
        return None
    for raw in candidates:
        candidate = normalize_sku_value(raw)
        if candidate:
            logger.debug(
                "_pick_sku_from_ocr_candidates: SKU OCR candidat accepté (%r -> %s)",
                raw,
                candidate,
            )
            return candidate
        logger.debug(
            "_pick_sku_from_ocr_candidates: SKU OCR candidat rejeté (%r)",
            raw,
        )
    return None


def _extract_cotton_elasthane(ocr_structured: Dict[str, Any]) -> tuple[Optional[int], Optional[int]]:
    items = ocr_structured.get("composition_items") or []
    if not isinstance(items, list):
        logger.warning(
            "_extract_cotton_elasthane: composition_items invalide (%r)",
            type(items),
        )
        return None, None

    cotton = None
    elasthane = None
    for item in items:
        if not isinstance(item, dict):
            continue
        material = str(item.get("material") or "").strip().lower()
        percent = item.get("percent")
        try:
            percent_value = int(percent) if percent is not None else None
        except (TypeError, ValueError):
            logger.debug(
                "_extract_cotton_elasthane: pourcentage illisible (%r)",
                percent,
            )
            percent_value = None

        if percent_value is None:
            continue

        if material == "coton":
            cotton = percent_value
        elif material in {"élasthanne", "elasthanne", "elastane", "élasthane", "elasthane"}:
            elasthane = percent_value

    return cotton, elasthane


def _build_material_from_ocr(ocr_structured: Dict[str, Any]) -> Optional[str]:
    items = ocr_structured.get("composition_items") or []
    if not isinstance(items, list):
        logger.warning(
            "_build_material_from_ocr: composition_items invalide (%r)",
            type(items),
        )
        return None

    parts: List[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        material = str(item.get("material") or "").strip().lower()
        percent = item.get("percent")
        if not material:
            continue
        try:
            percent_value = int(percent) if percent is not None else None
        except (TypeError, ValueError):
            logger.debug(
                "_build_material_from_ocr: pourcentage illisible (%r) pour %r",
                percent,
                material,
            )
            percent_value = None
        if percent_value is not None:
            parts.append(f"{percent_value}% {material}")
        else:
            parts.append(material)

    if not parts:
        return None

    return ", ".join(parts)
