# domain/normalizers/pull.py

"""
Builder de features pour le profil PULL (pulls/sweaters).

Supporte les marques branded (Tommy Hilfiger, Ralph Lauren, etc.)
et les pulls unbranded/vintage.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

from domain.normalizers.base import normalize_pull_brand

logger = logging.getLogger(__name__)


# Liste des marques connues pour les pulls (en minuscules pour comparaison)
KNOWN_PULL_BRANDS = [
    "tommy hilfiger",
    "tommy jeans",
    "hilfiger denim",
    "ralph lauren",
    "polo ralph lauren",
    "polo by ralph lauren",
]


def build_features_for_pull(
    ai_data: Dict[str, Any], ui_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Construit le dict 'features' pour un pull/gilet.

    Supporte:
      - Les marques branded (Tommy Hilfiger, Ralph Lauren, etc.)
      - Les pulls unbranded/vintage (brand = None -> is_vintage = True)

    Priorites :
      - donnees IA detaillees (ai_data["features"]),
      - corrections UI (taille, genre, SKU),
      - pas d'invention si les champs sont absents.
    """
    try:
        ui_data = ui_data or {}
        raw_features = ai_data.get("features") or {}

        measurement_mode = ui_data.get("measurement_mode") or "etiquette"
        brand = raw_features.get("brand") or ai_data.get("brand")
        garment_type = raw_features.get("garment_type") or ai_data.get("style")
        neckline = raw_features.get("neckline") or ai_data.get("neckline")
        pattern = raw_features.get("pattern") or ai_data.get("pattern")
        material = raw_features.get("material")
        cotton_percent = raw_features.get("cotton_percent")
        wool_percent = raw_features.get("wool_percent")
        main_colors = raw_features.get("main_colors") or raw_features.get("colors")
        gender = ui_data.get("gender") or raw_features.get("gender")

        size_from_ui = ui_data.get("size")
        size_label = raw_features.get("size") or ai_data.get("size")
        size_estimated = raw_features.get("size_estimated")
        size_source = raw_features.get("size_source")

        size = None
        computed_size_source = None

        try:
            if measurement_mode == "mesures":
                if size_from_ui:
                    size = size_from_ui
                    computed_size_source = "estimated"
                    logger.info(
                        "build_features_for_pull: taille UI retenue en mode mesures (%s)",
                        size,
                    )
                elif size_estimated:
                    size = size_estimated
                    computed_size_source = "estimated"
                    logger.info(
                        "build_features_for_pull: taille estimee depuis mesures IA (%s)",
                        size,
                    )
                elif size_label:
                    size = size_label
                    computed_size_source = size_source or "estimated"
                    logger.info(
                        "build_features_for_pull: taille issue des donnees IA malgre mode mesures (%s)",
                        size,
                    )
                else:
                    size = None
                    computed_size_source = None
                    logger.warning(
                        "build_features_for_pull: aucune taille estimable en mode mesures",
                    )
            else:
                size = size_from_ui or size_label
                computed_size_source = size_source or ("label" if size else None)
                if size:
                    logger.debug(
                        "build_features_for_pull: taille retenue mode etiquette (%s)",
                        size,
                    )
        except Exception as exc:
            logger.exception(
                "build_features_for_pull: erreur determination taille (mode=%s)",
                measurement_mode,
            )
            size = size_from_ui or size_label or size_estimated
            computed_size_source = computed_size_source or size_source

        sku_from_ui = ui_data.get("sku")
        sku_from_ai = raw_features.get("sku") or ai_data.get("sku")
        sku_status_raw = raw_features.get("sku_status") or ai_data.get("sku_status")
        sku_status = (
            str(sku_status_raw).strip().lower() if sku_status_raw is not None else None
        )
        sku_source = "ui" if sku_from_ui is not None else "ai"

        def _is_label_sku(value: str) -> bool:
            """Valide un SKU de type etiquette (lettres + chiffres)."""
            try:
                cleaned_value = re.sub(r"\s+", "", value)
                return bool(re.match(r'^[A-Za-z]{2,}\s*[0-9]+$', cleaned_value))
            except Exception:
                logger.debug(
                    "build_features_for_pull: validation SKU impossible pour '%s'",
                    value
                )
                return False

        if sku_source == "ui":
            sku = sku_from_ui
            if not sku_status or sku_status.lower() != "ok":
                sku_status = "ok"
            logger.debug(
                "build_features_for_pull: SKU fourni via UI conserve (%s)",
                sku,
            )
        else:
            if sku_from_ai and sku_status == "ok" and _is_label_sku(sku_from_ai):
                sku = re.sub(r"\s+", "", sku_from_ai)
                logger.info(
                    "build_features_for_pull: SKU detecte sur etiquette accepte (%s)",
                    sku,
                )
            else:
                if sku_from_ai:
                    sku = None
                    sku_status = "invalid"
                    logger.info(
                        "build_features_for_pull: SKU detecte mais invalide (%s)",
                        sku_from_ai,
                    )
                else:
                    sku = None
                    sku_status = "missing"

        # Normalisation de la marque et detection vintage
        try:
            normalized_brand = normalize_pull_brand(brand)
        except Exception as brand_exc:
            logger.warning(
                "build_features_for_pull: echec normalisation marque (%s)",
                brand_exc,
            )
            normalized_brand = brand

        # Detection branded vs vintage (unbranded)
        is_vintage = normalized_brand is None
        if is_vintage:
            logger.info("build_features_for_pull: pull unbranded detecte -> vintage")

        features: Dict[str, Any] = {
            "brand": normalized_brand,
            "is_vintage": is_vintage,
            "garment_type": garment_type,
            "neckline": neckline,
            "pattern": pattern,
            "material": material,
            "cotton_percent": cotton_percent,
            "wool_percent": wool_percent,
            "main_colors": main_colors,
            "gender": gender,
            "size": size,
            "size_estimated": size_estimated,
            "size_source": computed_size_source,
            "measurement_mode": measurement_mode,
            "sku": sku,
            "sku_status": sku_status,
        }

        # Detection du coton Pima dans la description IA ou l'etiquette
        description_text = (ai_data.get("description") or "").lower()
        material_text = (raw_features.get("material") or "").lower()
        pima_detected = (
            "pima coton" in description_text or "pima cotton" in description_text
            or "pima coton" in material_text or "pima cotton" in material_text
        )
        features["is_pima"] = pima_detected

        if pima_detected:
            logger.info(
                "build_features_for_pull: mention 'Pima cotton' detectee"
            )
        return features

    except Exception as exc:
        logger.exception(
            "build_features_for_pull: echec -> features vides (%s)", exc
        )
        return {}


# Alias pour retrocompatibilite
build_features_for_pull_tommy = build_features_for_pull
