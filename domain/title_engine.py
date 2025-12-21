# domain/title_engine.py

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional, Tuple

from domain.templates import AnalysisProfileName
from domain.title_builder import (
    SKU_PREFIX,
    _classify_rise_from_cm,
    _format_colors_segment,
    _format_material_segment,
    _format_neckline,
    _normalize_carhartt_size,
    _normalize_fit,
    _normalize_garment_type,
    _normalize_gender,
    _normalize_pull_size,
    _normalize_str,
    _sanitize_model_label,
    _safe_join,
)

logger = logging.getLogger(__name__)


def build_title_jean_levis(features: Dict[str, Any]) -> str:
    """
    Reprise des règles métier jean Levi's sans appel aux builders historiques.
    """
    try:
        brand = _normalize_str(features.get("brand"))
        raw_model = _normalize_str(features.get("model"))
        model = _sanitize_model_label(raw_model)
        size_fr = _normalize_str(features.get("size_fr"))
        size_us_raw = _normalize_str(features.get("size_us"))
        fit_source = _normalize_str(features.get("fit"))
        fit = _normalize_fit(fit_source)
        if not fit:
            fit = _normalize_fit(raw_model)
        else:
            try:
                raw_model_low = (raw_model or "").lower()
                if fit == "Skinny" and raw_model_low and any(
                    marker in raw_model_low for marker in ("boot", "flare", "évas", "evase", "curve", "curvy")
                ):
                    logger.debug(
                        "build_title_jean_levis: fit ajusté en Bootcut/Évasé depuis modèle %s",
                        raw_model,
                    )
                    fit = "Bootcut/Évasé"
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("build_title_jean_levis: ajustement fit impossible (%s)", exc)

        color = _normalize_str(features.get("color"))
        gender = _normalize_gender(_normalize_str(features.get("gender")))
        sku = _normalize_str(features.get("sku"))

        cotton_raw = features.get("cotton_percent")
        elas_raw = features.get("elasthane_percent")

        try:
            cotton_percent = int(cotton_raw) if cotton_raw is not None else None
        except (ValueError, TypeError):
            cotton_percent = None

        try:
            elas_percent = float(elas_raw) if elas_raw is not None else None
        except (ValueError, TypeError):
            elas_percent = None

        rise_type: Optional[str] = features.get("rise_type")
        if not rise_type:
            rise_cm = features.get("rise_cm")
            rise_type = _classify_rise_from_cm(rise_cm)
        else:
            try:
                normalized_rise = rise_type.strip().lower()
                if "basse" in normalized_rise or "low" in normalized_rise:
                    rise_type = "low"
                elif "haute" in normalized_rise or "high" in normalized_rise:
                    rise_type = "high"
                elif "moy" in normalized_rise or "mid" in normalized_rise:
                    rise_type = "mid"
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("build_title_jean_levis: rise_type illisible (%s)", exc)

        def _is_low_rise_label(raw: Optional[str]) -> bool:
            try:
                if not raw:
                    return False
                normalized = str(raw).strip().lower()
                return "low" in normalized or "basse" in normalized or "ultra" in normalized
            except Exception as exc_inner:  # pragma: no cover - defensive
                logger.warning("_is_low_rise_label: impossible de déterminer la taille basse (%s)", exc_inner)
                return False

        low_rise = _is_low_rise_label(rise_type)
        if not low_rise:
            try:
                low_rise = _is_low_rise_label(_classify_rise_from_cm(features.get("rise_cm")))
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("build_title_jean_levis: détection taille basse impossible (%s)", exc)

        size_us_display: Optional[str] = None
        if size_us_raw:
            s = size_us_raw.strip().upper()
            size_us_display = s if s.startswith("W") else f"W{s}"

        parts: List[str] = ["Jean"]

        if brand:
            brand_formatted = " ".join(word.capitalize() for word in brand.lower().split())
            parts.append(brand_formatted)

        if model:
            parts.append(model)

        if size_fr:
            parts.append(f"FR{size_fr}")
        if size_us_display:
            parts.append(size_us_display)

        if fit and low_rise:
            parts.append(f"coupe {fit} taille basse")
        elif fit:
            parts.append(f"coupe {fit}")
        elif low_rise:
            parts.append("taille basse")

        if cotton_percent is not None and cotton_percent >= 60:
            parts.append(f"{cotton_percent}% coton")

        if elas_percent is not None and elas_percent >= 2:
            parts.append("stretch")

        if gender:
            parts.append(gender)

        if color:
            parts.append(color)

        if sku:
            parts.append(f"{SKU_PREFIX}{sku}")

        title = _safe_join(parts)
        logger.debug("build_title_jean_levis: titre construit à partir de %s -> '%s'", features, title)
        return title
    except Exception as exc:  # pragma: no cover - robustesse
        logger.error("build_title_jean_levis: erreur lors de la génération du titre (%s)", exc, exc_info=True)
        return "Jean Levi's"


def build_title_pull_tommy(features: Dict[str, Any]) -> str:
    """Construit un titre pour les pulls/gilets Tommy Hilfiger (logique rapatriée)."""
    try:
        brand = _normalize_str(features.get("brand")) or "Tommy Hilfiger"
        garment_type = _normalize_garment_type(features.get("garment_type")) or "Pull"
        raw_gender = _normalize_gender(_normalize_str(features.get("gender")))
        gender = "femme"
        if raw_gender and raw_gender.lower() != "femme":
            logger.debug("build_title_pull_tommy: genre forcé à femme (entrée=%s)", raw_gender)
        elif raw_gender:
            gender = raw_gender
        size = _normalize_pull_size(_normalize_str(features.get("size")))
        neckline = _format_neckline(_normalize_str(features.get("neckline")))
        pattern = _normalize_str(features.get("pattern"))
        material = _format_material_segment(
            _normalize_str(features.get("material")),
            features.get("cotton_percent"),
            features.get("wool_percent"),
        )

        colors_input = features.get("main_colors") or features.get("colors")
        colors_segment = _format_colors_segment(colors_input)

        sku = _normalize_str(features.get("sku"))
        sku_status = _normalize_str(features.get("sku_status"))

        parts: List[str] = [garment_type]

        if brand:
            brand_formatted = " ".join(word.capitalize() for word in brand.lower().split())
            parts.append(brand_formatted)
            if features.get("is_pima") and brand.lower() == "tommy hilfiger":
                parts.append("Premium")
                logger.info("build_title_pull_tommy: ajout de 'Premium' au titre (Pima cotton détecté)")

        if gender:
            parts.append(gender)

        if size:
            parts.append(f"taille {size}")

        if material:
            parts.append(material)

        if colors_segment:
            parts.append(colors_segment)

        if pattern:
            parts.append(pattern)

        if neckline:
            parts.append(neckline)

        if sku and sku_status and sku_status.lower() == "ok":
            parts.append(f"{SKU_PREFIX}{sku}")
        elif sku:
            logger.debug(
                "build_title_pull_tommy: SKU ignoré car statut non 'ok' (%s)",
                sku_status,
            )

        title = _safe_join(parts)
        logger.debug("build_title_pull_tommy: titre construit à partir de %s -> '%s'", features, title)
        return title
    except Exception as exc:  # pragma: no cover - robustesse
        logger.exception("build_title_pull_tommy: échec de construction (%s)", exc)
        return _safe_join(["Pull Tommy Hilfiger"])


def build_title_jacket_carhart(features: Dict[str, Any]) -> str:
    """Construit un titre pour une veste Carhartt conformément aux règles métier."""
    try:
        brand = _normalize_str(features.get("brand")) or "Carhartt"
        model = _normalize_str(features.get("model"))
        raw_size = _normalize_str(features.get("size"))
        size, _size_token = _normalize_carhartt_size(raw_size)
        color = _normalize_str(features.get("color"))
        gender = _normalize_str(features.get("gender")) or "homme"
        has_hood = features.get("has_hood")
        is_camouflage = features.get("is_camouflage")
        is_realtree = features.get("is_realtree")
        is_new_york = features.get("is_new_york")
        pattern = _normalize_str(features.get("pattern"))

        sku = _normalize_str(features.get("sku"))
        sku_status = _normalize_str(features.get("sku_status"))

        prefix = "Veste à capuche Carhartt" if has_hood else "Veste Carhartt"
        parts: List[str] = [prefix]

        if brand and brand.lower() != "carhartt":
            parts.append(brand)

        if model:
            model_clean = model.strip()
            model_lower = model_clean.lower()
            if "jacket" in model_lower:
                model_segment = model_clean
            else:
                model_segment = f"{model_clean} Jacket"

            if is_new_york or "new york" in model_lower or model_lower.endswith(" ny"):
                model_segment = model_segment.rstrip() + " NY"

            parts.append(model_segment)
        elif is_new_york:
            parts.append("modèle NY")

        parts.append(f"taille {size}" if size else "taille NC")

        if color:
            parts.append(f"couleur {color}")

        if is_camouflage:
            parts.append("Realtree" if is_realtree else "camouflage")
        elif pattern and pattern.lower() == "camouflage":
            parts.append("camouflage")

        if gender:
            parts.append(gender)

        if sku and sku_status and sku_status.lower() == "ok":
            parts.append(f"{SKU_PREFIX}{sku}")
        elif sku:
            logger.debug(
                "build_title_jacket_carhart: SKU ignoré car statut non 'ok' (%s)",
                sku_status,
            )

        title = _safe_join(parts)
        logger.debug(
            "build_title_jacket_carhart: titre construit depuis %s -> '%s'",
            features,
            title,
        )
        return title
    except Exception as exc:  # pragma: no cover - robustesse
        logger.exception("build_title_jacket_carhart: échec de construction (%s)", exc)
        return "Veste Carhartt"


def build_title(profile_name: AnalysisProfileName, features: Dict[str, Any]) -> str:
    """
    Point d'entrée unique pour construire les titres depuis les features normalisées.
    Expose aussi des fonctions dédiées par profil pour clarifier la logique métier.
    """
    try:
        if profile_name == AnalysisProfileName.JEAN_LEVIS:
            return build_title_jean_levis(features)
        if profile_name == AnalysisProfileName.PULL_TOMMY:
            return build_title_pull_tommy(features)
        if profile_name == AnalysisProfileName.JACKET_CARHART:
            return build_title_jacket_carhart(features)

        fallback = str(features.get("title") or "").strip()
        logger.debug("Profil %s non géré par le moteur de titre, fallback brut.", profile_name)
        return fallback
    except Exception as exc:  # pragma: no cover - robustesse
        logger.error("build_title: erreur lors de la génération du titre (%s)", exc, exc_info=True)
        return str(features.get("title") or "").strip()
