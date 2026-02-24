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
    extract_gender_from_sku_prefix,
)

logger = logging.getLogger(__name__)


def detect_fit_from_measurements(
    thigh_cm: Optional[float],
    ankle_cm: Optional[float],
) -> Optional[str]:
    """
    Détecte la coupe du jean basée sur le ratio cheville/cuisse.

    Règles empiriques basées sur les données :
    | Cuisse | Cheville | Ratio | Coupe     |
    |--------|----------|-------|-----------|
    | 30     | 18       | 0.60  | Skinny    |
    | 30     | 21       | 0.70  | Straight  |
    | 30     | 24       | 0.80  | Évasé     |
    | 32     | 27       | 0.84  | Évasé     |

    Seuils :
    - ratio ≤ 0.65 : Skinny (jambe très fuselée)
    - ratio 0.65-0.75 : Straight/Droit (jambe droite)
    - ratio ≥ 0.75 : Bootcut/Évasé (ouverture en bas)

    Args:
        thigh_cm: Largeur cuisse à plat en cm
        ankle_cm: Largeur cheville/bas à plat en cm

    Returns:
        La coupe détectée ou None si mesures insuffisantes
    """
    if not thigh_cm or not ankle_cm:
        return None

    try:
        thigh = float(thigh_cm)
        ankle = float(ankle_cm)

        if thigh <= 0:
            logger.warning("detect_fit_from_measurements: cuisse invalide (%s)", thigh_cm)
            return None

        ratio = ankle / thigh

        if ratio <= 0.65:
            fit = "Skinny"
        elif ratio <= 0.75:
            fit = "Straight/Droit"
        else:
            fit = "Bootcut/Évasé"

        logger.info(
            "detect_fit_from_measurements: cuisse=%.1f, cheville=%.1f, ratio=%.2f -> %s",
            thigh,
            ankle,
            ratio,
            fit,
        )
        return fit

    except (ValueError, TypeError) as exc:
        logger.warning("detect_fit_from_measurements: erreur conversion (%s)", exc)
        return None


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
    # Priorité : UI (boutons radio) > IA > extraction texte
    ui_fit = ui_data.get("fit")
    if ui_fit:
        # Normaliser les valeurs UI (droite, evasee, skinny) vers les labels standard
        ui_fit_lower = ui_fit.lower()
        if ui_fit_lower == "droite":
            fit = "Straight/Droit"
        elif ui_fit_lower == "evasee":
            fit = "Bootcut/Évasé"
        elif ui_fit_lower == "skinny":
            fit = "Skinny"
        else:
            fit = normalize_fit_label(ui_fit)
        logger.info("build_features_for_jean_levis: coupe fournie par l'UI -> %s", fit)
    else:
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
    length = (
        ui_data.get("length")
        or raw_features.get("length")
        or ai_data.get("length")
    )

    if not size_us or not length:
        inferred_us, inferred_len = extract_sizes_from_text(full_text)
        if not size_us and inferred_us:
            size_us = inferred_us
        if not length and inferred_len:
            length = inferred_len

    # --- Composition -------------------------------------------------------
    cotton_percent = raw_features.get("cotton_percent") or ai_data.get("cotton_percent")
    elasthane_percent = raw_features.get("elasthane_percent") or ai_data.get("elasthane_percent")

    # Liste des matériaux (priorité : UI > IA)
    ui_composition = ui_data.get("composition")
    if ui_composition:
        # Parser la saisie utilisateur (ex: "Coton, Élasthanne" -> ["Coton", "Élasthanne"])
        composition_materials = [m.strip() for m in ui_composition.split(",") if m.strip()]
        composition_status = "ok"
        logger.info("build_features_for_jean_levis: composition fournie par l'UI -> %s", composition_materials)
    else:
        composition_materials = raw_features.get("composition_materials") or ai_data.get("composition_materials")
        composition_status = raw_features.get("composition_status") or ai_data.get("composition_status")

        # Si l'IA n'a pas détecté mais qu'on a des pourcentages, on peut déduire
        if not composition_materials and (cotton_percent or elasthane_percent):
            composition_materials = []
            if cotton_percent:
                composition_materials.append("Coton")
            if elasthane_percent:
                composition_materials.append("Élasthanne")
            composition_status = "ok"

    # --- Rise --------------------------------------------------------------
    rise_cm = raw_features.get("rise_cm") or ai_data.get("rise_cm")

    # Priorité : UI (boutons radio) > IA
    ui_rise = ui_data.get("rise_type")
    if ui_rise:
        # Normaliser les valeurs UI (haute, moyenne, basse) vers les labels standard
        ui_rise_lower = ui_rise.lower()
        if ui_rise_lower == "haute":
            rise_type = "high"
        elif ui_rise_lower == "moyenne":
            rise_type = "mid"
        elif ui_rise_lower == "basse":
            rise_type = "low"
        else:
            rise_type = ui_rise
        logger.info("build_features_for_jean_levis: rise fourni par l'UI -> %s", rise_type)
    else:
        rise_type = raw_features.get("rise_type") or ai_data.get("rise_type")

    # --- Mesures cuisse/cheville (pour détection coupe) --------------------
    thigh_width_cm = raw_features.get("thigh_width_cm") or ai_data.get("thigh_width_cm")
    ankle_width_cm = raw_features.get("ankle_width_cm") or ai_data.get("ankle_width_cm")

    # Si pas de fit détecté par l'IA, utiliser les mesures pour le déduire
    if not fit and thigh_width_cm and ankle_width_cm:
        fit = detect_fit_from_measurements(thigh_width_cm, ankle_width_cm)
        if fit:
            logger.info(
                "build_features_for_jean_levis: fit déduit des mesures cuisse=%.1f, cheville=%.1f -> %s",
                thigh_width_cm,
                ankle_width_cm,
                fit,
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
        "composition_materials": composition_materials,
        "composition_status": composition_status,
        "rise_type": rise_type,
        "rise_cm": rise_cm,
        "thigh_width_cm": thigh_width_cm,
        "ankle_width_cm": ankle_width_cm,
        "gender": gender,
        "sku": sku,
        "sku_status": sku_status,
        "order_id": order_id,
    }

    logger.debug("build_features_for_jean_levis: features=%s", features)
    return features
