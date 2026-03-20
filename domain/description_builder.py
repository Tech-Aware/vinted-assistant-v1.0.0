from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from domain.pricing import get_retail_price_range

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

        if normalized in {"low", "ultra_low"} or "basse" in normalized:
            return "taille basse"
        if normalized == "high" or "haute" in normalized:
            return "taille haute"
        if normalized == "mid" or "moy" in normalized:
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
            return "Très bon état."
        concise_state = f"Très bon état : {clean_defects} (voir photos)."
        logger.info("_build_state_sentence: état décrit = %s", concise_state)
        return concise_state
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
    size_tag: str = "",
    vinted_account_tag: str = "",
    sku_order_tag: str = "",
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
            model_low = model.lower().strip()
            model_number = ""
            try:
                import re  # local import pour rester défensif

                match = re.search(r"(\d{3})", model_low)
                if match:
                    model_number = match.group(1)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("_build_hashtags: extraction modèle échouée (%s)", exc)

            if model_number:
                add(f"#levis{model_number}")
                add(f"#{model_number}")

            model_tokens: List[str] = []
            drop_markers = {"demi", "curve", "curvy", "cut"}
            for token in model_low.replace("/", " ").split():
                token_clean = token.replace("'", "").replace("-", "")
                if token_clean == model_number or token_clean.isdigit():
                    continue
                if token_clean in drop_markers:
                    logger.debug(
                        "_build_hashtags: token modèle ignoré (marker): %s", token
                    )
                    continue
                if token_clean:
                    model_tokens.append(token_clean)

            try:
                tokens_lower = {t.lower() for t in model_tokens}
                if "super" in tokens_lower and "skinny" in tokens_lower:
                    add("#superskinny")
                    model_tokens = [t for t in model_tokens if t.lower() not in {"super", "skinny"}]
                if "super" in tokens_lower and "slim" in tokens_lower:
                    add("#superslim")
                    model_tokens = [t for t in model_tokens if t.lower() not in {"super", "slim"}]
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("_build_hashtags: combinaison tokens modèle impossible (%s)", exc)

            for token_clean in model_tokens:
                add(f"#{token_clean}")

        if fit:
            fit_low = fit.lower().strip()
            fit_key = fit_low.replace("é", "e")
            boot_markers = {"bootcut", "boot cut", "boot-cut", "flare", "curve", "curvy"}
            if any(marker in fit_key for marker in boot_markers):
                fit_token = "bootcut"
            elif "skinny" in fit_key or "slim" in fit_key:
                fit_token = "skinny"
            elif "straight" in fit_key or "droit" in fit_key:
                fit_token = "straightdroit"
            else:
                fit_token = fit_key.replace(" ", "").replace("/", "")
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

        # Ajouter le tag de taille avec préfixe compte (#GC_fr36 ou #LG_fr36)
        if size_tag:
            add(size_tag)

        # Ajouter le tag du compte Vinted (#gentlemen_corner ou #ladies_and_gentlemen)
        if vinted_account_tag:
            add(vinted_account_tag)

        if sku_order_tag:
            add(sku_order_tag)

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
        softened = _soften_defect_terms(cleaned)
        return softened
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("_normalize_defects: erreur %s", exc)
        return ""


def _soften_defect_terms(defects: str) -> str:
    """Ajuste certains termes pour des formulations moins anxiogènes."""
    try:
        text = defects
        if not text:
            return ""

        replacements = {"généralisé": "visible", "generalise": "visible"}
        for needle, replacement in replacements.items():
            if needle in text.lower():
                logger.info(
                    "_soften_defect_terms: remplacement '%s' -> '%s'", needle, replacement
                )
                text = re.sub(needle, replacement, text, flags=re.IGNORECASE)

        return text
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("_soften_defect_terms: erreur %s", exc)
        return defects or ""


def _normalize_percentage_spacing(text: str) -> str:
    try:
        normalized = re.sub(r"(\d)\s*%\s*", r"\1 % ", text)
        normalized = re.sub(r"\s{2,}", " ", normalized)
        return normalized.strip()
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("_normalize_percentage_spacing: normalisation impossible (%s)", exc)
        return text


def _clean_carhartt_material_segment(value: Optional[Any]) -> str:
    """Nettoie un segment décrivant une matière pour l'affichage Carhartt."""

    try:
        base = _safe_clean(value)
        if not base:
            return ""

        cleaned = re.sub(
            r"la composition indiquée[^:]*:", "", base, flags=re.IGNORECASE
        )
        cleaned = re.sub(
            r"^(composition|matiere|material)[:\-]?\s*", "", cleaned, flags=re.IGNORECASE
        )
        cleaned = cleaned.strip(" .;:-")

        # enlève les tirets parasites du type "30 % - POLYESTER"
        cleaned = re.sub(r"\s*-\s*", " ", cleaned)

        cleaned = _normalize_percentage_spacing(cleaned)

        if cleaned:
            logger.info(
                "_clean_carhartt_material_segment: segment nettoyé='%s' (source=%s)",
                cleaned,
                value,
            )
        return cleaned
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("_clean_carhartt_material_segment: nettoyage impossible (%s)", exc)
        return _safe_clean(value)


def _normalize_pull_size(size: Optional[str]) -> str:
    try:
        raw = _safe_clean(size).upper()
        if not raw:
            return ""

        main_token = raw.split("/", 1)[0].strip()
        if main_token:
            return main_token

        return raw
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("_normalize_pull_size: normalisation taille échouée (%s)", exc)
        return _safe_clean(size)


def _normalize_carhartt_size(size: Optional[str]) -> tuple[str, str, str]:
    """Renvoie (taille courte, taille affichée, token hashtag) avec journalisation."""

    try:
        raw = _safe_clean(size)
        if not raw:
            return "NC", "NC", "nc"

        low = raw.lower()
        base = raw.upper()

        size_map = {
            "xs": "XS",
            "extra small": "XS",
            "x-small": "XS",
            "small": "S",
            "s": "S",
            "medium": "M",
            "m": "M",
            "large": "L",
            "l": "L",
            "x-large": "XL",
            "xl": "XL",
            "xxl": "XXL",
            "2xl": "XXL",
            "xxxl": "XXXL",
            "3xl": "XXXL",
        }

        for marker, normalized in size_map.items():
            if marker in low:
                base = normalized
                break

        display = base if base == raw.strip().upper() else f"{base} ({raw})"
        token = base.lower().replace(" ", "") or "nc"
        logger.info(
            "_normalize_carhartt_size: taille brute '%s' -> base=%s, display=%s, token=%s",
            raw,
            base,
            display,
            token,
        )
        return base, display, token
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("_normalize_carhartt_size: échec normalisation (%s)", exc)
        return "NC", "NC", "nc"


def _strip_footer_lines(description: str) -> str:
    try:
        if not description:
            return ""

        try:
            description = description.replace("\u00A0", " ")
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("_strip_footer_lines: normalisation espaces ignorée (%s)", exc)

        filtered_lines: List[str] = []
        for line in description.split("\n"):
            lowered = line.strip().lower()
            try:
                import re

                if re.match(r"^[#*\-\s]*marque\s*:", lowered):
                    logger.debug("_strip_footer_lines: ligne marque supprimée: %s", line)
                    continue
                if re.match(r"^[#*\-\s]*couleur\s*:", lowered):
                    logger.debug("_strip_footer_lines: ligne couleur supprimée: %s", line)
                    continue
                if re.match(r"^[#*\-\s]*taille\s*:", lowered):
                    logger.debug("_strip_footer_lines: ligne taille supprimée: %s", line)
                    continue
                if re.match(r"^[#*\-\s]*sku", lowered):
                    logger.debug("_strip_footer_lines: ligne SKU supprimée: %s", line)
                    continue
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("_strip_footer_lines: regex footer ignoré (%s)", exc)

            filtered_lines.append(line)

        cleaned = "\n".join(filtered_lines)

        try:
            import re

            cleaned = re.sub(
                r"(?im)^\s*(marque|couleur|taille|sku)\s*:[^\n]*$",
                "",
                cleaned,
            )
            cleaned = re.sub(
                r"(?is)\n+\s*(marque|couleur|taille|sku)\s*:[^\n]*", "", cleaned
            )

            final_lines: List[str] = []
            blank_seen = False
            for raw_line in cleaned.split("\n"):
                if not raw_line.strip():
                    if not blank_seen:
                        final_lines.append("")
                        blank_seen = True
                    continue
                final_lines.append(raw_line.rstrip())
                blank_seen = False

            cleaned = "\n".join(final_lines).strip()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("_strip_footer_lines: nettoyage étendu ignoré (%s)", exc)

        return cleaned
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("_strip_footer_lines: erreur %s", exc)
        return description


def _build_pull_composition(
    material: Optional[str],
    cotton_percent: Optional[Any],
    wool_percent: Optional[Any],
    angora_percent: Optional[Any] = None,
    manual_composition_text: Optional[str] = None,
) -> str:
    try:
        fibers: List[str] = []
        seen: set[str] = set()

        def _normalize_fiber_label(raw_label: str) -> str:
            try:
                aliases = {
                    "cotton": "coton",
                    "cotton.": "coton",
                    "cot": "coton",
                    "cotone": "coton",
                    "wool": "laine",
                    "lana": "laine",
                    "angora": "angora",
                    "angora rabbit": "angora",
                    "rabbit angora": "angora",
                    "rabbit": "angora",
                    "lapin": "angora",
                    "lapin angora": "angora",
                    "mohair" : "mohair",
                    "lana de cabra" : "mohair",
                    "lambswool": "laine d'agneau",
                }
                cleaned = raw_label.strip(" .")
                cleaned_lower = cleaned.lower()
                return aliases.get(cleaned_lower, cleaned_lower)
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug(
                    "_build_pull_composition: normalisation matière échouée (%s)",
                    exc,
                )
                return raw_label

        def _add_fiber(label: str, percent: Optional[int]) -> None:
            try:
                label_clean = _safe_clean(label).lower()
                if not label_clean:
                    return
                normalized_label = _normalize_fiber_label(label_clean)
                key = (
                    f"{percent}-{normalized_label}"
                    if percent is not None
                    else normalized_label
                )
                if key in seen:
                    return
                seen.add(key)
                display = normalized_label.capitalize()
                if percent is not None:
                    fibers.append(f"{percent}% {display}")
                else:
                    fibers.append(display)
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug(
                    "_build_pull_composition: impossible d'ajouter %s (%s)",
                    label,
                    exc,
                )

        manual_text = _safe_clean(manual_composition_text)
        if manual_text:
            return f"Composition : {manual_text.rstrip('.')}."

        clean_material = _safe_clean(material)
        material_lower = clean_material.lower()
        if clean_material:
            try:
                import re

                matches = re.findall(
                    r"(\d+)\s*%\s*([A-Za-zÀ-ÿ]+)", clean_material, flags=re.IGNORECASE
                )
                for percent_txt, fiber_name in matches:
                    percent_val = _format_percent(percent_txt)
                    _add_fiber(fiber_name, percent_val)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(
                    "_build_pull_composition: parsing partiel de la composition (%s)",
                    exc,
                )

        cotton_val = _format_percent(cotton_percent)
        wool_val = _format_percent(wool_percent)
        angora_val = _format_percent(angora_percent)

        if cotton_val is not None:
            _add_fiber("coton", cotton_val)

        if angora_val is not None:
            _add_fiber("angora", angora_val)
        elif wool_val is not None:
            try:
                if "angora" in material_lower and "laine" not in material_lower:
                    logger.info(
                        "_build_pull_composition: wool_percent traité comme angora (material=%s)",
                        clean_material,
                    )
                    _add_fiber("angora", wool_val)
                else:
                    _add_fiber("laine", wool_val)
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug(
                    "_build_pull_composition: impossible d'interpréter wool_percent (%s)",
                    exc,
                )
                _add_fiber("laine", wool_val)

        if fibers:
            return "Composition : " + ", ".join(fibers) + "."

        if clean_material:
            return f"Composition (étiquette) : {clean_material}."

        return "Composition non lisible (voir photos)."
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("_build_pull_composition: erreur %s", exc)
        return "Composition non lisible (voir photos)."


def _normalize_fit_display(raw_fit: Optional[str], model_hint: Optional[str] = None) -> str:
    """Normalise la coupe en 3 catégories : Skinny / Droit / Évasé."""
    try:
        if not raw_fit and not model_hint:
            return "coupe non précisée"

        value = (raw_fit or model_hint or "").strip()
        low = value.lower()
        secondary_low = (model_hint or "").strip().lower()

        combined = f"{low} {secondary_low}"

        if "skinny" in combined or "slim" in combined:
            return "Skinny"

        if any(m in combined for m in ("straight", "droit", "mom", "boyfriend", "girlfriend", "regular", "tapered")):
            return "Droit"

        if any(m in combined for m in (
            "boot", "flare", "évas", "evase", "curve", "curvy",
            "wide", "baggy", "loose", "relaxed", "barrel",
        )):
            return "Évasé"

        return value or "coupe non précisée"
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("_normalize_fit_display: erreur %s", exc)
        return "coupe non précisée"


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
        raw_fit = _safe_clean(features.get("fit"))
        fit = _normalize_fit_display(raw_fit, model_hint=model)
        color = _safe_clean(features.get("color"))
        size_fr = _safe_clean(features.get("size_fr"))
        size_us = _safe_clean(features.get("size_us"))
        length = _safe_clean(features.get("length"))
        gender = _safe_clean(features.get("gender")) or "femme"
        sku = _safe_clean(features.get("sku"))
        order_id = _safe_clean(features.get("order_id"))
        rise_label = _format_rise_label(features.get("rise_type"), features.get("rise_cm"))
        defects = ai_defects or features.get("defects")

        cotton_percent = _format_percent(features.get("cotton_percent"))
        elasthane_percent = _format_percent(features.get("elasthane_percent"))
        composition_materials = features.get("composition_materials") or []
        composition_status = features.get("composition_status")

        # --- Fit effectif ---
        fit_effective = fit
        model_low = (model or "").lower()

        if "demi" in model_low and "curve" in model_low:
            fit_effective = "Évasé"
        elif "curve" in model_low and not fit_effective:
            fit_effective = "Évasé"

        # --- Déterminer le compte Vinted selon le SKU ---
        sku_upper = (sku or "").upper()
        is_homme = "JLH" in sku_upper

        if is_homme:
            vinted_account_tag = "#gentlemen_corner"
            size_tag_prefix = "#GC_fr"
        else:
            vinted_account_tag = "#ladies_and_gentlemen"
            size_tag_prefix = "#LG_fr"

        size_tag = f"{size_tag_prefix}{(size_fr or 'nc').lower()}"

        # --- Construction du libellé de coupe ---
        fit_low = (fit_effective or "").lower()
        if "boot" in fit_low or "évas" in fit_low or "evas" in fit_low or "flare" in fit_low:
            fit_label = "évasés"
            fit_hashtag = "évasé"
        elif "skinny" in fit_low or "slim" in fit_low:
            fit_label = "skinny"
            fit_hashtag = "skinny"
        elif "straight" in fit_low or "droit" in fit_low:
            fit_label = "droits"
            fit_hashtag = "droit"
        else:
            fit_label = ""
            fit_hashtag = ""

        # --- Libellé taille (rise) ---
        rise_low = (rise_label or "").lower()
        if "basse" in rise_low:
            rise_intro = "de taille basse"
            rise_hashtag = "lowrise"
        elif "haute" in rise_low:
            rise_intro = "de taille haute"
            rise_hashtag = "highrise"
        else:
            rise_intro = "de taille moyenne"
            rise_hashtag = "midrise"

        # --- Phrase d'introduction adaptée selon la coupe ---
        if fit_label == "évasés":
            silhouette_phrase = "équilibre la silhouette et allonge la jambe"
        elif fit_label == "skinny":
            silhouette_phrase = "épouse la silhouette et affine la jambe"
        elif fit_label == "droits":
            silhouette_phrase = "offre une coupe classique et intemporelle"
        else:
            silhouette_phrase = "offre un style polyvalent"

        if fit_label:
            intro_sentence = f"Ces Jeans {fit_label} {brand} pour {gender} {rise_intro} {silhouette_phrase}."
        else:
            intro_sentence = f"Ces Jeans {brand} pour {gender} {rise_intro} {silhouette_phrase}."

        # --- Phrase composition ---
        # Utiliser composition_materials (liste des matériaux sans pourcentages)
        if composition_materials and isinstance(composition_materials, list) and len(composition_materials) > 0:
            composition_text = ", ".join(composition_materials)
            composition_sentence = f"Celui-ci est composé de {composition_text} disposant ainsi d'une toile de denim souple, bien tenue et confortable."
        else:
            # Fallback sur les pourcentages si pas de liste
            composition_parts: List[str] = []
            if cotton_percent:
                composition_parts.append("Coton")
            if elasthane_percent and elasthane_percent > 0:
                composition_parts.append("Élasthanne")

            if composition_parts:
                composition_text = ", ".join(composition_parts)
                composition_sentence = f"Celui-ci est composé de {composition_text} disposant ainsi d'une toile de denim souple, bien tenue et confortable."
            else:
                composition_sentence = "Toile de denim souple, bien tenue et confortable."

        # --- Phrase couleur ---
        if color:
            color_sentence = f"Sa couleur {color.lower()}, intemporelle, s'intègre facilement à une garde-robe."
        else:
            color_sentence = "Sa couleur intemporelle s'intègre facilement à une garde-robe."

        # --- Phrase fermeture ---
        closure_sentence = f"Il est doté d'une fermeture zippée et bouton gravé {brand}."

        # --- Bloc taille ---
        if size_fr and size_us:
            size_line = f"👖 Taille FR{size_fr} équivalent US {size_us}"
        elif size_fr:
            size_line = f"👖 Taille FR{size_fr}"
        elif size_us:
            size_line = f"👖 Taille US {size_us}"
        else:
            size_line = "👖 Taille : voir photos"

        size_note = "*Les variations et écarts de mesure entre les tailles US et FR sont dus aux différentes proportions d'élasthanne et/ou viscose présentes dans le tissu."

        # --- Bloc état ---
        defects_clean = _normalize_defects(defects)
        if not defects_clean:
            state_line = "👍 Très bon état : article impeccable !"
        else:
            state_line = f"👍 Très bon état : {defects_clean}"

        # --- Bloc mesures ---
        measures_line = "🔎 Consultez les photos pour obtenir les mesures précises et la composition détaillée."

        # --- Bloc envoi ---
        shipping_line = "📦 Envoi rapide et soigné"

        # --- CTA ---
        cta_size_line = f"✨ Retrouvez tous mes articles Levi's à votre taille ici 👉 {size_tag}"
        cta_lot_line = "💡 Jusqu'à 20% de réduction sur les lots, pensez y !"

        # --- Hashtags dynamiques ---
        hashtag_tokens: List[str] = ["#vintage", "#levis", "#jeanlevis", "#jeandenim"]

        if gender.lower() == "femme":
            hashtag_tokens.append("#levisfemme")
        else:
            hashtag_tokens.append("#levishomme")

        if rise_hashtag:
            hashtag_tokens.append(f"#{rise_hashtag}")

        if fit_hashtag:
            hashtag_tokens.append(f"#{fit_hashtag}")
            hashtag_tokens.append(f"#jean{fit_hashtag}")

        if color:
            color_clean = color.lower().replace(" ", "")
            hashtag_tokens.append(f"#jean{color_clean}")

        hashtag_tokens.append(size_tag)

        if sku:
            sku_clean = sku.lower().replace(" ", "")
            if order_id:
                hashtag_tokens.append(f"#{order_id}{sku_clean}")
            else:
                hashtag_tokens.append(f"#{sku_clean}")

        hashtags = " ".join(hashtag_tokens)

        # --- Prix neuf en magasin ---
        retail_range = get_retail_price_range(features)
        retail_line = f"💵 Prix neuf en magasin : {retail_range}" if retail_range else ""

        # --- Assemblage final ---
        paragraph1 = f"{intro_sentence} {composition_sentence} {color_sentence} {closure_sentence}"
        info_block = "\n".join([size_line, size_note, state_line, measures_line])
        footer_block = "\n".join([shipping_line, "", cta_size_line, cta_lot_line, "", hashtags])

        if retail_line:
            description = f"{retail_line}\n\n{paragraph1}\n\n{info_block}\n\n{footer_block}"
        else:
            description = f"{paragraph1}\n\n{info_block}\n\n{footer_block}"
        logger.debug("build_jean_levis_description: description générée = %s", description)
        return description

    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("build_jean_levis_description: fallback description IA (%s)", exc)
        return _safe_clean(ai_description)


def build_pull_description(
    features: Dict[str, Any],
    ai_description: Optional[str] = None,
    ai_defects: Optional[str] = None,
) -> str:
    """
    Construit une description structuree pour un pull.

    Supporte:
      - Pulls branded (Tommy Hilfiger, Ralph Lauren, etc.)
      - Pulls vintage/unbranded (is_vintage=True ou brand=None)
    """
    try:
        logger.info("build_pull_description: features recus = %s", features)

        brand = _safe_clean(features.get("brand"))
        is_vintage = features.get("is_vintage", False)

        # Si pas de marque, c'est un pull vintage
        if not brand:
            is_vintage = True
            brand = "Vintage"

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
        sku = _safe_clean(features.get("sku"))
        order_id = _safe_clean(features.get("order_id"))

        colors = ""
        try:
            if isinstance(colors_raw, list):
                colors = ", ".join([_safe_clean(c) for c in colors_raw if _safe_clean(c)])
            else:
                colors = _safe_clean(colors_raw)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("build_pull_description: couleurs non exploitables (%s)", exc)
            colors = ""

        intro_parts: List[str] = []
        intro_parts.append(f"{garment_type.capitalize()} {brand}")
        if gender:
            intro_parts.append(f"pour {gender}")
        intro_base = " ".join(intro_parts).strip()

        if size:
            if size_source == "estimated" or measurement_mode == "mesures":
                intro_sentence = (
                    f"{intro_base} taille {size} (Estimée à la main à partir des mesures à plat)."
                )
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
        elif material:
            material_phrase = f"maille {material}".strip()

        color_text = colors or "aux couleurs iconiques"
        if neckline:
            neckline_low = neckline.lower()
            neckline_text = neckline if neckline_low.startswith("col") else f"Col {neckline}"
        else:
            neckline_text = "Maille"

        style_clause = f" dans un style {pattern}" if pattern else ""
        try:
            comfort_phrases = {
                "angora": "pour une douceur légère et élégante",
                "laine": "pour une chaleur douce et confortable",
                "coton": "pour un confort respirant au quotidien",
            }
            material_key = ""
            for key in comfort_phrases:
                if key in material_phrase.lower():
                    material_key = key
                    break
            comfort_clause = comfort_phrases.get(material_key, "pour un look iconique et confortable")
            descriptive_sentence = (
                f"{neckline_text}{style_clause} aux coloris {color_text}, et une {material_phrase} {comfort_clause}."
            ).strip()
            if descriptive_sentence and not descriptive_sentence[0].isupper():
                descriptive_sentence = descriptive_sentence[0].upper() + descriptive_sentence[1:]
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("build_pull_description: phrase descriptive par défaut (%s)", exc)
            descriptive_sentence = (
                f"{neckline_text}{style_clause} aux coloris {color_text}, et une {material_phrase} pour un look iconique et confortable."
            ).strip()

        composition_sentence = _build_pull_composition(
            material=material,
            cotton_percent=cotton_percent,
            wool_percent=wool_percent,
            angora_percent=angora_percent,
            manual_composition_text=features.get("manual_composition_text"),
        )

        state_sentence = _build_state_sentence(defects)

        logistics_lines = [
            "📏 Mesures détaillées visibles en photo pour plus de précisions.",
            "📦 Envoi rapide et soigné.",
        ]
        logistics_sentence = "\n".join(logistics_lines)

        tokens_hashtag: List[str] = []
        try:
            size_token = _normalize_pull_size(size).replace(" ", "") if size else "NC"
            durin_tag = f"#durin31tf{size_token}"
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("build_pull_description: durin_tag défaut (%s)", exc)
            size_token = "NC"
            durin_tag = "#durin31tfNC"

        try:
            def _add_tag(token: str) -> None:
                if token and token not in tokens_hashtag:
                    tokens_hashtag.append(token)

            base_tags = [
                "#tommyhilfiger",
                "#pulltommy",
                "#tommy",
                "#pullfemme",
                "#modefemme",
                "#preloved",
                durin_tag,
                "#ptf",
            ]
            for token in base_tags:
                _add_tag(token)

            if cotton_val is not None:
                _add_tag("#pullcoton")
            if pattern and pattern.lower().strip() == "torsade":
                _add_tag("#pulltorsade")

            if colors:
                for color_token in colors.split(","):
                    clean_color = color_token.strip().lower().replace(" ", "")
                    if clean_color:
                        _add_tag(f"#{clean_color}")

            # Hashtag SKU + Order ID (format: #durin31ptf123_20)
            if sku:
                sku_clean = sku.lower().replace(" ", "")
                if order_id:
                    _add_tag(f"#durin31{sku_clean}_{order_id}")
                else:
                    _add_tag(f"#durin31{sku_clean}")
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("build_pull_description: hashtags réduits (%s)", exc)

        hashtags_block = " ".join(tokens_hashtag)
        hashtags_with_cta = "\n".join(
            [
                f"✨ Retrouvez tous mes pulls Tommy femme ici 👉 {durin_tag}",
                "💡 Pensez à faire un lot pour profiter d’une réduction supplémentaire et économiser des frais d’envoi !",
                "",
                hashtags_block,
            ]
        )

        paragraphs = [
            intro_sentence,
            descriptive_sentence,
            composition_sentence,
            state_sentence,
            logistics_sentence,
            hashtags_with_cta,
        ]

        description = "\n\n".join([p for p in paragraphs if p])
        cleaned = _strip_footer_lines(description)
        logger.debug("build_pull_description: description generee = %s", cleaned)
        return cleaned
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("build_pull_description: fallback description IA (%s)", exc)
        return _strip_footer_lines(_safe_clean(ai_description))


# Alias pour retrocompatibilite
build_pull_tommy_description = build_pull_description


def _describe_lining(lining: str) -> str:
    try:
        lining_clean = _clean_carhartt_material_segment(lining)
        if not lining_clean:
            return ""
        return f"Intérieur : {lining_clean}"
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("_describe_lining: description de doublure impossible (%s)", exc)
        return ""


def _describe_patch_material(patch_material: str) -> str:
    try:
        material_clean = patch_material.strip()
        if not material_clean:
            return ""
        return f"Écusson {material_clean}."
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("_describe_patch_material: description écusson impossible (%s)", exc)
        return ""


def _strip_percentage_tokens(text: str) -> str:
    """Supprime les pourcentages pour construire un texte descriptif (sans composition).

    Cette fonction est utilisée pour générer un paragraphe rédigé sans chiffres, puis la
    composition détaillée (avec pourcentages) est présentée dans un bloc dédié.
    """

    try:
        if not text:
            return ""

        no_parentheses = re.sub(r"\((?:[^)(]+|\([^)(]*\))*\)", "", text)
        no_percent = re.sub(r"\b\d+\s*%\s*", "", no_parentheses)
        normalized_spaces = re.sub(r"\s{2,}", " ", no_percent)
        return normalized_spaces.strip()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("_strip_percentage_tokens: nettoyage impossible (%s)", exc)
        return text or ""


def build_jacket_carhart_description(
    features: Dict[str, Any],
    ai_description: Optional[str] = None,
    ai_defects: Optional[str] = None,
) -> str:
    """Produit une description détaillée pour une veste Carhartt."""
    try:
        logger.info("build_jacket_carhart_description: features reçus = %s", features)

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
        sku = _safe_clean(features.get("sku"))
        order_id = _safe_clean(features.get("order_id"))

        # --- 1) Phrase produit -------------------------------------------------
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

        # --- 2) Phrase style ---------------------------------------------------
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

        # --- 3) Champs utiles à la composition -------------------------------
        exterior_raw = _safe_clean(features.get("exterior"))
        sleeve_lining_clean = _clean_carhartt_material_segment(
            _safe_clean(features.get("sleeve_lining"))
        )

        # --- 4) Col : extraction type + matière -------------------------------
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
                "build_jacket_carhart_description: col détecté type=%s matière=%s (raw=%s)",
                collar_type,
                collar_material,
                collar_raw,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("build_jacket_carhart_description: parsing col échoué (%s)", exc)
            collar_type = ""
            collar_material = ""

        # --- 5) Helpers composition ------------------------------------------
        def _pick_percent_line(text: str) -> str:
            """
            Récupère une composition courte du type '100 % coton' si présente,
            sinon renvoie un nettoyage minimal.
            """
            try:
                cleaned = _clean_carhartt_material_segment(text)
                if not cleaned:
                    return ""
                matches = re.findall(r"\d+\s*%\s*[A-Za-zÀ-ÿ'’\- ]+", cleaned)
                if matches:
                    return ", ".join(m.strip() for m in matches)
                return cleaned
            except Exception as exc:  # pragma: no cover
                logger.warning("_pick_percent_line: erreur (%s)", exc)
                return _clean_carhartt_material_segment(text) or ""

        # --- 6) Paragraphe doublure / col (court) -----------------------------
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

        # Col (priorité à la matière si détectée)
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

        # --- 7) Paragraphe zip (court) ---------------------------------------
        zip_sentence = ""
        if zip_material:
            zip_sentence = f"Fermeture zippée intégrale en {zip_material}."

        # --- 8) Composition (lignes courtes) ---------------------------------
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

        # --- 9) État ----------------------------------------------------------
        defects = _safe_clean(features.get("defects") or ai_defects)
        normalized_defects = _normalize_defects(defects)
        if not normalized_defects:
            state_sentence = "Très bon état, aucun défaut majeur visible. Veste propre et bien conservée (voir photos)."
        else:
            nd = normalized_defects.strip()
            # si ça commence par une majuscule, on la baisse (après virgule)
            if nd[:1].isupper():
                nd = nd[:1].lower() + nd[1:]
            state_sentence = f"Très bon état, {nd}. Veste propre et bien conservée (voir photos)."

        # --- 10) Footer / tags ----------------------------------------------
        general_tag = "#durin31jc"
        size_tag = f"{general_tag}{size_token}" if size_token else "#durin31jcnc"
        color_tag = f"#{color.lower().replace(' ', '')}" if color else ""

        # Hashtag SKU + Order ID (format: #durin31jcr123_20)
        sku_order_tag = ""
        if sku:
            sku_clean = sku.lower().replace(" ", "")
            if order_id:
                sku_order_tag = f"#durin31{sku_clean}_{order_id}"
            else:
                sku_order_tag = f"#durin31{sku_clean}"

        logistics_sentence = "📏 Mesures détaillées visibles en photo pour plus de précisions."
        shipping_sentence = "📦 Envoi rapide et soigné."
        cta_sentence = (
            f"✨ Retrouvez toutes mes vestes Carhartt ici 👉 {general_tag} et à votre taille 👉 {size_tag}"
        )
        bundle_sentence = (
            "💡 Pensez à faire un lot pour bénéficier d'une réduction et économiser sur les frais d'envoi."
        )

        hashtags = " ".join(
            token
            for token in [
                "#carhartt",
                "#jacket",
                "#workwear",
                "#vintage",
                "#detroitjacket",
                "#detroit",
                f"#madein{origin_country.lower()}" if origin_country else "",
                general_tag,
                "#durin31",
                size_tag,
                color_tag,
                sku_order_tag,
            ]
            if token
        ).strip()

        # --- 11) Assemblage final -------------------------------------------
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

        description = "\n\n".join(part for part in paragraphs if part).strip()
        logger.debug("build_jacket_carhart_description: description générée = %s", description)
        return description

    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("build_jacket_carhart_description: fallback description IA (%s)", exc)
        return _strip_footer_lines(_safe_clean(ai_description))
