# domain/description_engine.py

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from domain.description_builder import (
    _build_composition,
    _build_hashtags,
    _build_state_sentence,
    _clean_carhartt_material_segment,
    _format_percent,
    _format_rise_label,
    _normalize_carhartt_size,
    _normalize_defects,
    _normalize_fit_display,
    _normalize_pull_size,
    _safe_clean,
    _strip_footer_lines,
    _strip_percentage_tokens,
)
from domain.templates import AnalysisProfileName

logger = logging.getLogger(__name__)


def build_description_jean_levis(
    features: Dict[str, Any], ai_description: Optional[str] = None, ai_defects: Optional[str] = None
) -> str:
    try:
        logger.info("build_description_jean_levis: features reçus = %s", features)

        brand = _safe_clean(features.get("brand")) or "Levi's"
        model = _safe_clean(features.get("model"))
        raw_fit = _safe_clean(features.get("fit"))
        fit = _normalize_fit_display(raw_fit, model_hint=model)
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

        intro_sentence = f"{title_intro} pour {gender}."

        size_sentence_parts = []
        if size_us and size_fr:
            size_sentence_parts.append(f"Taille {size_us} US (équivalent {size_fr} FR)")
        elif size_fr:
            size_sentence_parts.append(f"Taille {size_fr} FR")
        elif size_us:
            size_sentence_parts.append(f"Taille {size_us} US")
        if fit:
            size_sentence_parts.append(f"coupe {fit}")
        if rise_label:
            size_sentence_parts.append(f"à {rise_label}")
        if size_sentence_parts:
            size_sentence_parts.append("pour une silhouette ajustée et confortable")
        size_sentence = ", ".join(size_sentence_parts).strip()
        size_sentence = f"{size_sentence}." if size_sentence else "Taille non précisée."

        color_has_fade = "lavé" in color.lower() if color else False
        if color:
            nuance = " légèrement délavé" if not color_has_fade else ""
            color_sentence = f"Coloris {color}{nuance}, très polyvalent et facile à assortir."
        else:
            color_sentence = "Coloris non précisé, se référer aux photos pour les nuances."
        composition_sentence = _build_composition(features.get("cotton_percent"), features.get("elasthane_percent"))
        closure_sentence = "Fermeture zippée + bouton gravé Levi’s."
        state_sentence = _build_state_sentence(ai_defects or features.get("defects"))

        logistics_sentence = "📏 Mesures visibles en photo."
        shipping_sentence = "📦 Envoi rapide et soigné"

        cta_lot_sentence = (
            "💡 Pensez à un lot pour profiter d’une réduction supplémentaire et économiser des frais d’envoi !"
        )
        durin_tag = f"#durin31fr{(size_fr or 'nc').lower()}"
        cta_durin_sentence = f"✨ Retrouvez tous mes articles Levi’s à votre taille ici 👉 {durin_tag}"

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
        logger.debug("build_description_jean_levis: description générée = %s", description)
        return description

    except Exception as exc:  # pragma: no cover - robustesse
        logger.exception("build_description_jean_levis: fallback description IA (%s)", exc)
        return _safe_clean(ai_description)


def build_description_pull_tommy(
    features: Dict[str, Any], ai_description: Optional[str] = None, ai_defects: Optional[str] = None
) -> str:
    try:
        logger.info("build_description_pull_tommy: features reçus = %s", features)

        brand = _safe_clean(features.get("brand")) or "Tommy Hilfiger"
        brand.capitalize()
        garment_type = _safe_clean(features.get("garment_type")) or "pull"
        gender = _safe_clean(features.get("gender")) or "femme"
        neckline = _safe_clean(features.get("neckline"))
        pattern = _safe_clean(features.get("pattern"))
        material = _safe_clean(features.get("material"))
        cotton_percent = features.get("cotton_percent")
        wool_percent = features.get("wool_percent")
        angora_percent = features.get("angora_percent")
        colors_raw = features.get("main_colors")
        size = _normalize_pull_size(features.get("size"))
        size_source = (_safe_clean(features.get("size_source")) or "").lower()
        measurement_mode = (_safe_clean(features.get("measurement_mode")) or "").lower()
        defects = ai_defects or features.get("defects")

        colors = ""
        try:
            if isinstance(colors_raw, list):
                colors = ", ".join([_safe_clean(c) for c in colors_raw if _safe_clean(c)])
            else:
                colors = _safe_clean(colors_raw)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("build_description_pull_tommy: couleurs non exploitables (%s)", exc)
            colors = ""

        intro_parts: List[str] = []
        intro_parts.append(f"{garment_type.capitalize()} {brand}")
        if gender:
            intro_parts.append(f"pour {gender}")
        intro_base = " ".join(intro_parts).strip()

        if size:
            if size_source == "estimated" or measurement_mode == "mesures":
                intro_sentence = f"{intro_base} taille {size} (Estimée à la main à partir des mesures à plat)."
            else:
                intro_sentence = f"{intro_base} taille {size}."
        else:
            intro_sentence = f"{intro_base}."

        material_phrase = "maille agréable"
        cotton_val = _format_percent(cotton_percent)
        wool_val = _format_percent(wool_percent)
        angora_val = _format_percent(angora_percent)

        if angora_val is not None:
            material_phrase = f"maille {angora_val}% angora"
        elif wool_val is not None:
            material_phrase = f"maille {wool_val}% laine"
        elif cotton_val is not None:
            material_phrase = f"maille {cotton_val}% coton"
        if material:
            material_phrase = material

        style_phrase = []
        if neckline:
            style_phrase.append(f"col {neckline}")
        if pattern:
            style_phrase.append(pattern)
        style_sentence = ", ".join(style_phrase) + "." if style_phrase else None

        color_sentence = f"Couleur : {colors}." if colors else None

        composition_sentence = None
        if cotton_val is not None or wool_val is not None or angora_val is not None:
            composition_sentence = "Composition : "
            tokens = []
            if cotton_val is not None:
                tokens.append(f"{cotton_val}% coton")
            if wool_val is not None:
                tokens.append(f"{wool_val}% laine")
            if angora_val is not None:
                tokens.append(f"{angora_val}% angora")
            composition_sentence += " / ".join(tokens) + "."

        state_sentence = f"État visuel : {defects}." if defects else "État visuel : bon état, voir photos."

        footer = (
            "📏 Mesures détaillées visibles en photo pour plus de précisions.\n"
            "📦 Envoi rapide et soigné.\n"
            "✨ Retrouvez tous mes pulls Tommy femme ici 👉 #durin31tfM\n"
            "💡 Pensez à faire un lot pour profiter d’une réduction supplémentaire et économiser des frais d’envoi !\n\n"
            "#tommyhilfiger #pulltommy #tommy #pullfemme #modefemme #preloved #durin31tfM #ptf #rouge"
        )

        paragraphs = [
            intro_sentence,
            f"Matière : {material_phrase}." if material_phrase else None,
            style_sentence,
            color_sentence,
            composition_sentence,
            state_sentence,
            footer,
        ]

        description = "\n\n".join([p for p in paragraphs if p])
        logger.debug("build_description_pull_tommy: description générée = %s", description)
        return description
    except Exception as exc:  # pragma: no cover - robustesse
        logger.exception("build_description_pull_tommy: fallback description IA (%s)", exc)
        return _safe_clean(ai_description)


def build_description_jacket_carhart(
    features: Dict[str, Any], ai_description: Optional[str] = None, ai_defects: Optional[str] = None
) -> str:
    try:
        logger.info("build_description_jacket_carhart: features reçus = %s", features)

        brand = _safe_clean(features.get("brand")) or "Carhartt"
        brand = brand.capitalize()
        model = _safe_clean(features.get("model"))

        raw_size = _safe_clean(features.get("size")) or "NC"
        size_short, size_display, size_token = _normalize_carhartt_size(raw_size)

        color = _safe_clean(features.get("color"))
        gender = _safe_clean(features.get("gender")) or "homme"

        lining = _safe_clean(features.get("lining"))
        patch_material = _safe_clean(features.get("patch_material"))
        collar = _safe_clean(features.get("collar"))
        zip_material = _safe_clean(features.get("zip_material"))
        origin_country = _safe_clean(features.get("origin_country"))

        product_sentence_parts: List[str] = [f"Veste {brand}"]
        if model:
            product_sentence_parts.append(model)
        if gender:
            product_sentence_parts.append(f"pour {gender}")
        product_sentence_parts.append(f"taille {size_display}")
        if color:
            product_sentence_parts.append(f"coloris {color}")
        if origin_country:
            product_sentence_parts.append(f"Made in {origin_country}")

        product_sentence = (
            " ".join(token for token in product_sentence_parts if token).strip().rstrip(".")
            + "."
        )

        patch_label = (patch_material or "simili-cuir").lower()
        color_intro = (
            f"Le coloris {color.lower()} sobre s’associe facilement avec toutes les tenues."
            if color
            else "Coloris à confirmer sur les photos."
        )
        style_sentence = (
            "Modèle iconique du workwear Carhartt, coupe droite intemporelle, "
            f"écusson Carhartt en {patch_label}, facile à porter au quotidien. "
            f"{color_intro}"
        )

        exterior_raw = _safe_clean(features.get("exterior"))
        sleeve_lining_clean = _clean_carhartt_material_segment(_safe_clean(features.get("sleeve_lining")))

        collar_type = ""
        collar_material = ""
        try:
            collar_raw = (collar or "").strip()
            collar_low = collar_raw.lower()

            if "chemise" in collar_low:
                collar_type = "chemise"
            elif "montant" in collar_low:
                collar_type = "montant"
            elif "teddy" in collar_low:
                collar_type = "teddy"
            elif "officier" in collar_low:
                collar_type = "officier"

            if any(k in collar_low for k in ("velours", "côtel", "cotele", "corduroy")):
                collar_material = "velours côtelé"

            logger.debug(
                "build_description_jacket_carhart: col détecté type=%s matière=%s (raw=%s)",
                collar_type,
                collar_material,
                collar_raw,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("build_description_jacket_carhart: parsing col échoué (%s)", exc)
            collar_type = ""
            collar_material = ""

        def _pick_percent_line(text: str) -> str:
            try:
                cleaned = _clean_carhartt_material_segment(text)
                if not cleaned:
                    return ""
                matches = re.findall(r"\d+\\s*%\\s*[A-Za-zÀ-ÿ'’\\- ]+", cleaned)
                if matches:
                    return ", ".join(m.strip() for m in matches)
                return cleaned
            except Exception as exc:  # pragma: no cover
                logger.warning("_pick_percent_line: erreur (%s)", exc)
                return _clean_carhartt_material_segment(text) or ""

        lining_label = ""
        try:
            low = (lining or "").lower()
            if "matelass" in low:
                lining_label = "doublure matelassée"
            elif "sherpa" in low:
                lining_label = "doublure sherpa"
            elif lining:
                lining_label = _strip_percentage_tokens(_clean_carhartt_material_segment(lining))
        except Exception as exc:  # pragma: no cover
            logger.debug("lining_label: fallback (%s)", exc)

        warmth_parts: List[str] = []
        if lining_label:
            warmth_parts.append(
                f"La {lining_label} apporte une bonne chaleur, idéale pour la mi-saison comme pour l’hiver"
            )

        if collar_material:
            if collar_type == "chemise":
                warmth_parts.append(f"avec un col chemise en {collar_material}")
            elif collar_type:
                warmth_parts.append(f"avec un col {collar_type} en {collar_material}")
            else:
                warmth_parts.append(f"avec un col en {collar_material}")
        elif collar_type:
            warmth_parts.append(f"avec un col {collar_type}")

        warmth_sentence = ""
        if warmth_parts:
            warmth_sentence = ", ".join(warmth_parts).strip().rstrip(".") + "."

        zip_sentence = ""
        if zip_material:
            zip_sentence = f"Fermeture zippée intégrale en {zip_material}."

        composition_lines: List[str] = []

        ext_line = _pick_percent_line(exterior_raw or "")
        if ext_line:
            composition_lines.append(f"Extérieur : {ext_line}")

        lining_line = _pick_percent_line(lining or "")
        if lining_line:
            if "matelass" in (lining or "").lower() and ("(" in (lining or "") or "," in (lining or "")):
                composition_lines.append(f"Doublure : matelassée ({lining_line})")
            else:
                composition_lines.append(f"Doublure : {lining_line}")

        sleeve_line = _pick_percent_line(sleeve_lining_clean or "")
        if sleeve_line:
            composition_lines.append(f"Doublure des manches : {sleeve_line}")

        if collar_material:
            composition_lines.append(f"Col : {collar_material}")
        elif collar_type:
            composition_lines.append(f"Col : {collar_type}")

        composition_block = ""
        if composition_lines:
            composition_block = "Composition :\n" + "\n".join(composition_lines)

        defects = _safe_clean(features.get("defects") or ai_defects)
        normalized_defects = _normalize_defects(defects)
        state_sentence = (
            "Très bon état, aucun défaut majeur visible. Veste propre et bien conservée (voir photos)."
            if not normalized_defects
            else f"Très bon état, {normalized_defects}. Veste propre et bien conservée (voir photos)."
        )

        general_tag = "#durin31jc"
        size_tag = f"{general_tag}{size_token}" if size_token else "#durin31jcnc"
        color_tag = f"#{color.lower().replace(' ', '')}" if color else ""

        logistics_sentence = "📏 Mesures détaillées visibles en photo pour plus de précisions."
        shipping_sentence = "📦 Envoi rapide et soigné."
        cta_sentence = f"✨ Retrouvez toutes mes vestes Carhartt ici 👉 {general_tag} et à votre taille 👉 {size_tag}"
        bundle_sentence = "💡 Pensez à faire un lot pour bénéficier d’une réduction et économiser sur les frais d’envoi."

        hashtag_core = "#carhartt #jacket #workwear #durin31"
        hashtags = " ".join(token for token in [hashtag_core, size_tag, color_tag] if token)

        paragraphs = [
            product_sentence,
            style_sentence,
            warmth_sentence,
            zip_sentence,
            composition_block,
            state_sentence,
            logistics_sentence,
            shipping_sentence,
            cta_sentence,
            bundle_sentence,
            hashtags,
        ]

        description = "\n\n".join(part for part in paragraphs if part)
        description = _safe_clean(description)
        logger.debug("build_description_jacket_carhart: description générée = %s", description)
        return description
    except Exception as exc:  # pragma: no cover - robustesse
        logger.exception("build_description_jacket_carhart: fallback description IA (%s)", exc)
        return _safe_clean(ai_description)


def build_description(
    profile_name: AnalysisProfileName,
    features: Dict[str, Any],
    ai_description: Optional[str] = None,
    ai_defects: Optional[str] = None,
) -> str:
    """
    Point d'entrée unique pour construire les descriptions finales depuis les features.
    Expose aussi des fonctions dédiées par profil pour clarifier la logique métier.
    """
    try:
        if profile_name == AnalysisProfileName.JEAN_LEVIS:
            return build_description_jean_levis(features, ai_description=ai_description, ai_defects=ai_defects)
        if profile_name == AnalysisProfileName.PULL_TOMMY:
            return build_description_pull_tommy(features, ai_description=ai_description, ai_defects=ai_defects)
        if profile_name == AnalysisProfileName.JACKET_CARHART:
            return build_description_jacket_carhart(features, ai_description=ai_description, ai_defects=ai_defects)

        fallback = (ai_description or "").strip()
        logger.debug("Profil %s non géré par le moteur de description, fallback brut.", profile_name)
        return fallback
    except Exception as exc:  # pragma: no cover - robustesse
        logger.error(
            "build_description: erreur lors de la génération de la description (%s)",
            exc,
            exc_info=True,
        )
        return (ai_description or "").strip()
