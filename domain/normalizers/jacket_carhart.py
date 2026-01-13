# domain/normalizers/jacket_carhart.py

"""
Builder de features pour le profil JACKET_CARHART.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from domain.normalizers.text_extractors import (
    strip_parentheses_notes,
    strip_composition_prefixes,
    extract_color_from_text,
    extract_lining_from_text,
    extract_body_lining_composition,
    extract_exterior_from_text,
    extract_sleeve_lining_from_text,
    extract_closure_from_text,
    extract_patch_material_from_text,
    extract_collar_from_text,
    extract_zip_material_from_text,
    extract_origin_country_from_text,
    extract_carhartt_model_from_text,
    extract_carhartt_composition_from_ocr_structured,
    split_carhartt_composition_blocks,
    normalize_carhartt_model,
    normalize_jcr_sku,
    detect_flag_from_text,
    detect_chest_pocket_from_text,
)

logger = logging.getLogger(__name__)


def _pick_carhartt_sku_from_candidates(candidates: List[str]) -> Optional[str]:
    """Sélectionne le SKU JCR depuis une liste de candidats."""
    if not candidates:
        return None
    for c in candidates:
        if re.fullmatch(r"JCR\d+", c, flags=re.IGNORECASE):
            return c.upper()
    return None


def build_features_for_jacket_carhart(
    ai_data: Dict[str, Any],
    ui_data: Optional[Dict[str, Any]] = None,
    ocr_sku_candidates: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Construit les features nécessaires au titre/description Carhartt."""

    try:
        ui_data = ui_data or {}
        raw_features = ai_data.get("features") or {}

        title = ai_data.get("title") or ""
        description = ai_data.get("description") or ""

        full_text = f"{title} {description}".strip()
        composition_text = (ai_data.get("description") or "").strip()

        # --- Composition: priorité OCR structuré si disponible ---
        ocr_structured = ui_data.get("ocr_structured") or {}
        ocr_composition_text = ""
        try:
            ocr_composition_text = (ocr_structured.get("filtered_text") or "").strip()
        except Exception:
            ocr_composition_text = ""

        composition_source_text = ocr_composition_text or composition_text

        brand = raw_features.get("brand") or ai_data.get("brand") or "Carhartt"
        model = raw_features.get("model") or ai_data.get("model")
        model = normalize_carhartt_model(model, full_text)
        if not model:
            model = extract_carhartt_model_from_text(full_text)

        size = (
            ui_data.get("size_fr")
            or ui_data.get("size")
            or raw_features.get("size")
            or ai_data.get("size")
        )

        color = raw_features.get("color") or ai_data.get("color")
        if not color:
            color = extract_color_from_text(full_text)

        gender = (
            ui_data.get("gender")
            or raw_features.get("gender")
            or ai_data.get("gender")
        )

        has_hood = raw_features.get("has_hood")
        if has_hood is None:
            has_hood = detect_flag_from_text(full_text, ("capuche", "hood"))

        pattern = raw_features.get("pattern") or ai_data.get("pattern")

        # LINING
        lining = raw_features.get("lining") or ai_data.get("lining")
        if lining is None:
            lining = extract_lining_from_text(full_text)

        if lining is None or "%" not in str(lining):
            lining_composition = extract_body_lining_composition(composition_source_text)
            if lining_composition:
                lining = lining_composition

        if isinstance(lining, str) and lining.strip().upper() in {"DU", "D U"}:
            lining = None

        closure = raw_features.get("closure") or ai_data.get("closure")
        if closure is None:
            closure = extract_closure_from_text(full_text)

        patch_material = raw_features.get("patch_material") or ai_data.get("patch_material")
        if patch_material is None:
            patch_material = extract_patch_material_from_text(full_text)

        collar = raw_features.get("collar") or ai_data.get("collar")
        if collar is None:
            collar = extract_collar_from_text(full_text)

        zip_material = raw_features.get("zip_material") or ai_data.get("zip_material")
        if zip_material is None:
            zip_material = extract_zip_material_from_text(full_text)

        origin_country = raw_features.get("origin_country") or ai_data.get("origin_country")
        if origin_country is None:
            origin_country = extract_origin_country_from_text(full_text)

        # EXTERIOR
        exterior = raw_features.get("exterior") or ai_data.get("exterior")
        if exterior is None:
            exterior = extract_exterior_from_text(composition_source_text)

        # SLEEVE LINING
        sleeve_lining = raw_features.get("sleeve_lining") or ai_data.get("sleeve_lining")
        if sleeve_lining is None:
            sleeve_lining = extract_sleeve_lining_from_text(composition_source_text)

        split_blocks: Dict[str, str] = split_carhartt_composition_blocks(composition_source_text)

        if split_blocks.get("exterior"):
            exterior = split_blocks["exterior"]
        if split_blocks.get("lining"):
            lining = split_blocks["lining"]
        if split_blocks.get("sleeve_lining"):
            sleeve_lining = split_blocks["sleeve_lining"]

        has_chest_pocket = raw_features.get("has_chest_pocket")
        if has_chest_pocket is None:
            has_chest_pocket = detect_chest_pocket_from_text(full_text)

        is_camouflage = raw_features.get("is_camouflage")
        if is_camouflage is None and pattern:
            is_camouflage = pattern.lower() == "camouflage"
        if is_camouflage is None:
            is_camouflage = detect_flag_from_text(full_text, ("camouflage",))

        is_realtree = raw_features.get("is_realtree")
        if is_realtree is None:
            is_realtree = detect_flag_from_text(full_text, ("realtree",))

        is_new_york = raw_features.get("is_new_york")
        if is_new_york is None:
            is_new_york = detect_flag_from_text(full_text, ("new york", " ny"))

        # --- SKU (Carhartt JCR) ---
        sku_from_ui = ui_data.get("sku")
        sku_from_ai = raw_features.get("sku") or ai_data.get("sku")
        sku_status_raw = raw_features.get("sku_status") or ai_data.get("sku_status")

        sku_status = (
            str(sku_status_raw).strip().lower()
            if sku_status_raw is not None
            else None
        )

        sku = None

        if sku_from_ui:
            sku = normalize_jcr_sku(sku_from_ui)
            if sku:
                sku_status = "ok"
                logger.info("build_features_for_jacket_carhart: SKU pris depuis UI (%s)", sku)
            else:
                sku = None
                sku_status = "low_confidence"
                logger.warning(
                    "build_features_for_jacket_carhart: SKU UI non conforme JCR (%r)",
                    sku_from_ui,
                )
        else:
            ocr_candidates = ai_data.get("_ocr_sku_candidates") or []
            if not isinstance(ocr_candidates, list):
                ocr_candidates = []

            ocr_sku = _pick_carhartt_sku_from_candidates([str(x) for x in ocr_candidates])

            if ocr_sku:
                sku = ocr_sku
                sku_status = "ok"
                logger.info("build_features_for_jacket_carhart: SKU OCR structuré validé (%s)", sku)
            else:
                normalized_ai_sku = normalize_jcr_sku(sku_from_ai)
                if normalized_ai_sku:
                    sku = normalized_ai_sku
                    sku_status = "ok"
                    logger.info("build_features_for_jacket_carhart: SKU IA validé (%s)", sku)
                else:
                    if sku_status == "low_confidence":
                        sku = None
                        logger.info(
                            "build_features_for_jacket_carhart: SKU low_confidence côté IA"
                        )
                    else:
                        sku = None
                        sku_status = "missing"
                        logger.debug("build_features_for_jacket_carhart: SKU absent (missing)")

        exterior = strip_composition_prefixes(strip_parentheses_notes(exterior))
        lining = strip_composition_prefixes(strip_parentheses_notes(lining))
        sleeve_lining = strip_composition_prefixes(strip_parentheses_notes(sleeve_lining))

        ocr_structured = ui_data.get("ocr_structured") or {}
        ocr_comp = extract_carhartt_composition_from_ocr_structured(ocr_structured)

        exterior = ocr_comp.get("exterior") or exterior
        lining = ocr_comp.get("body_lining") or lining
        sleeve_lining = ocr_comp.get("sleeve_lining") or sleeve_lining

        sleeve_inter = ocr_comp.get("sleeve_interlining")
        if sleeve_inter and sleeve_lining and sleeve_inter != sleeve_lining:
            sleeve_lining = f"{sleeve_lining} / {sleeve_inter}"
        elif sleeve_inter and not sleeve_lining:
            sleeve_lining = sleeve_inter

        # Order ID
        order_id = ui_data.get("order_id")

        features: Dict[str, Any] = {
            "brand": brand,
            "model": model,
            "size": size,
            "color": color,
            "gender": gender or "homme",
            "has_hood": has_hood,
            "pattern": pattern,
            "lining": lining,
            "closure": closure,
            "patch_material": patch_material,
            "collar": collar,
            "zip_material": zip_material,
            "origin_country": origin_country,
            "exterior": exterior,
            "sleeve_lining": sleeve_lining,
            "has_chest_pocket": has_chest_pocket,
            "is_camouflage": is_camouflage,
            "is_realtree": is_realtree,
            "is_new_york": is_new_york,
            "sku": sku,
            "sku_status": sku_status,
            "order_id": order_id,
        }

        logger.debug("build_features_for_jacket_carhart: features=%s", features)
        return features

    except Exception as exc:
        logger.exception(
            "build_features_for_jacket_carhart: échec -> features vides (%s)", exc
        )
        return {}
