from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------


def _safe_clean(value: Optional[Any]) -> str:
    try:
        if value is None:
            return ""
        text = str(value).strip()
        return text
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("_safe_clean: erreur sur %r -> %s", value, exc)
        return ""


def _format_percent(value: Optional[Any]) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("_format_percent: conversion impossible pour %r (%s)", value, exc)
        return None


def _format_rise_label(rise_type: Optional[str], rise_cm: Optional[Any]) -> str:
    try:
        if rise_type:
            normalized = rise_type.strip().lower()
        else:
            normalized = ""

        if normalized in {"low", "ultra_low"}:
            return "taille basse"
        if normalized == "high":
            return "taille haute"
        if normalized == "mid":
            return "taille moyenne"

        if rise_cm is not None:
            try:
                value = float(rise_cm)
                if value < 23:
                    return "taille basse"
                if value >= 26:
                    return "taille haute"
                return "taille moyenne"
            except (TypeError, ValueError):
                logger.debug("_format_rise_label: rise_cm non exploitable: %r", rise_cm)

        return "taille moyenne"
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("_format_rise_label: erreur inattendue %s", exc)
        return "taille moyenne"


def _build_composition(cotton_percent: Optional[Any], elasthane_percent: Optional[Any]) -> str:
    try:
        cotton_val = _format_percent(cotton_percent)
        elas_val = _format_percent(elasthane_percent)

        fibers: List[str] = []
        if cotton_val is not None:
            fibers.append(f"{cotton_val}% coton")
        if elas_val is not None:
            fibers.append(f"{elas_val}% élasthanne")

        if fibers:
            return "Composition : " + " et ".join(fibers) + "."
        return "Composition non lisible (voir étiquettes en photo)."
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("_build_composition: erreur %s", exc)
        return "Composition non lisible (voir étiquettes en photo)."


def _build_state_sentence(defects: Optional[str]) -> str:
    try:
        clean_defects = _normalize_defects(defects)
        if not clean_defects:
            return "Très bon état général."
        return f"Bon état général, légères traces d'usage : {clean_defects} (voir photos)."
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("_build_state_sentence: erreur %s", exc)
        return "État non précisé (voir photos)."


def _build_hashtags(
    brand: str,
    model: str,
    fit: str,
    color: str,
    size_fr: str,
    size_us: str,
    length: str,
    gender: str,
    rise_label: str,
    durin_tag: str,
) -> str:
    try:
        tokens: List[str] = []

        def add(token: str) -> None:
            if token and token not in tokens:
                tokens.append(token)

        brand_token = brand.lower().replace("'", "") if brand else "levis"
        add(f"#{brand_token}")
        add("#jeanlevis")
        add("#jeandenim")

        if gender:
            gender_token = gender.lower().replace(" ", "")
            add(f"#levis{gender_token}")

        if model:
            add(f"#levis{model}")

        if fit:
            fit_low = fit.lower().strip()
            fit_key = fit_low.replace("é", "e")
            if "boot" in fit_key and "cut" in fit_key:
                fit_token = "bootcut"
            else:
                fit_token = (
                    fit_low.replace(" ", "").replace("/", "").replace("é", "e")
                )
            add(f"#{fit_token}jean")

        if color:
            color_clean = color.lower().replace(" ", "")
            add(f"#jean{color_clean}")

        rise_clean = rise_label.lower().replace(" ", "") if rise_label else ""
        if rise_clean:
            add(f"#{rise_clean}")

        if size_fr:
            add(f"#fr{size_fr.lower()}")
        if size_us:
            add(f"#w{size_us.lower().replace('w', '')}")
        if length:
            add(f"#l{length.lower().replace('l', '')}")

        if durin_tag:
            add(durin_tag)

        return " ".join(tokens)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("_build_hashtags: erreur %s", exc)
        return ""


def _normalize_defects(defects: Optional[str]) -> str:
    try:
        base = _safe_clean(defects)
        if not base:
            return ""

        lowered = base.lower()
        if "voir photos" in lowered:
            cut = lowered.split("voir photos", 1)[0].strip()
        else:
            cut = base.strip()

        cleaned = cut.rstrip(". ,;")
        return cleaned
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("_normalize_defects: erreur %s", exc)
        return ""


def _strip_footer_lines(description: str) -> str:
    try:
        if not description:
            return ""

        filtered_lines: List[str] = []
        for line in description.split("\n"):
            lowered = line.strip().lower()
            if lowered.startswith("marque :"):
                logger.debug("_strip_footer_lines: ligne marque supprimée: %s", line)
                continue
            if lowered.startswith("couleur :"):
                logger.debug("_strip_footer_lines: ligne couleur supprimée: %s", line)
                continue
            filtered_lines.append(line)

        cleaned = "\n".join(filtered_lines)
        return cleaned
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("_strip_footer_lines: erreur %s", exc)
        return description


# ---------------------------------------------------------------------------
# Génération de description pour jean Levi's
# ---------------------------------------------------------------------------


def build_jean_levis_description(
    features: Dict[str, Any],
    ai_description: Optional[str] = None,
    ai_defects: Optional[str] = None,
) -> str:
    """
    Génère une description structurée d'un jean Levi's à partir des features
    normalisés. En cas d'erreur, on retombe sur la description IA brute.
    """
    try:
        logger.info("build_jean_levis_description: features reçus = %s", features)

        brand = _safe_clean(features.get("brand")) or "Levi's"
        model = _safe_clean(features.get("model"))
        fit = _safe_clean(features.get("fit")) or "coupe non précisée"
        color = _safe_clean(features.get("color"))
        size_fr = _safe_clean(features.get("size_fr"))
        size_us = _safe_clean(features.get("size_us"))
        length = _safe_clean(features.get("length"))
        gender = _safe_clean(features.get("gender")) or "femme"
        sku = _safe_clean(features.get("sku"))
        rise_label = _format_rise_label(features.get("rise_type"), features.get("rise_cm"))

        title_intro_parts = ["Jean", brand]
        if model:
            title_intro_parts.append(model)
        title_intro = " ".join(title_intro_parts)

        # --- Phrases structurées ------------------------------------------
        intro_sentence = f"{title_intro} pour {gender}."

        size_sentence_parts = []
        if size_us and size_fr:
            size_sentence_parts.append(
                f"Taille {size_us} US (équivalent {size_fr} FR)"
            )
        elif size_fr:
            size_sentence_parts.append(f"Taille {size_fr} FR")
        elif size_us:
            size_sentence_parts.append(f"Taille {size_us} US")
        if fit:
            size_sentence_parts.append(f"coupe {fit}")
        if rise_label:
            size_sentence_parts.append(f"à {rise_label}")
        if size_sentence_parts:
            size_sentence_parts.append(
                "pour une silhouette ajustée et confortable"
            )
        size_sentence = ", ".join(size_sentence_parts).strip()
        size_sentence = f"{size_sentence}." if size_sentence else "Taille non précisée."

        color_has_fade = "lavé" in color.lower() if color else False
        if color:
            nuance = " légèrement délavé" if not color_has_fade else ""
            color_sentence = (
                f"Coloris {color}{nuance}, très polyvalent et facile à assortir."
            )
        else:
            color_sentence = "Coloris non précisé, se référer aux photos pour les nuances."
        composition_sentence = _build_composition(
            features.get("cotton_percent"), features.get("elasthane_percent")
        )
        closure_sentence = "Fermeture zippée + bouton gravé Levi’s."
        state_sentence = _build_state_sentence(ai_defects or features.get("defects"))

        logistics_sentence = "📏 Mesures visibles en photo."
        shipping_sentence = "📦 Envoi rapide et soigné"

        cta_lot_sentence = (
            "💡 Pensez à un lot pour profiter d’une réduction supplémentaire et économiser des frais d’envoi !"
        )
        durin_tag = f"#durin31fr{(size_fr or 'nc').lower()}"
        cta_durin_sentence = (
            f"✨ Retrouvez tous mes articles Levi’s à votre taille ici 👉 {durin_tag}"
        )

        hashtags = _build_hashtags(
            brand=brand,
            model=model,
            fit=fit,
            color=color,
            size_fr=size_fr,
            size_us=size_us,
            length=length,
            gender=gender,
            rise_label=rise_label,
            durin_tag=durin_tag,
        )

        paragraphs = [
            intro_sentence,
            size_sentence,
            color_sentence,
            composition_sentence,
            closure_sentence,
            state_sentence,
            logistics_sentence,
            shipping_sentence,
            cta_durin_sentence,
            cta_lot_sentence,
            hashtags,
        ]

        description = "\n\n".join(part for part in paragraphs if part)
        description = _strip_footer_lines(description)
        logger.debug("build_jean_levis_description: description générée = %s", description)
        return description

    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("build_jean_levis_description: fallback description IA (%s)", exc)
        return _safe_clean(ai_description)
