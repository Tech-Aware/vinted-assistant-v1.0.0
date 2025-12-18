# domain/normalizer.py

from __future__ import annotations

import re
from typing import Dict, Any, Optional
import logging

from domain.description_builder import (
    build_jacket_carhart_description,
    build_jean_levis_description,
    build_pull_tommy_description,
    _build_hashtags,
    _strip_footer_lines,
)
from domain.templates import AnalysisProfileName
from domain.title_builder import (
    build_jacket_carhart_title,
    build_jean_levis_title,
    build_pull_tommy_title,
)

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


# ---------------------------------------------------------------------------
# Utilitaires internes
# ---------------------------------------------------------------------------


def _coerce_profile_name(
    profile_name: Optional[object],
) -> Optional[AnalysisProfileName]:
    if isinstance(profile_name, AnalysisProfileName):
        return profile_name

    if isinstance(profile_name, str):
        value = profile_name.strip().lower()
        for enum_val in AnalysisProfileName:
            if enum_val.value == value:
                return enum_val

    return None


def _extract_model_from_text(text: str) -> Optional[str]:
    """
    Tente d'extraire un modèle Levi's (ex: 501, 511, 515) depuis du texte.
    """
    if not text:
        return None

    match = re.search(r"\b5\d{2}\b", text)
    if match:
        return match.group(0)
    return None


def _extract_fit_from_text(text: str) -> Optional[str]:
    """
    Tente d'extraire la coupe (fit) depuis le texte.
    Pour l'instant on se concentre sur Boot Cut.
    """
    if not text:
        return None

    low = text.lower()
    if "boot cut" in low or "bootcut" in low:
        # On uniformise en mentionnant explicitement l'évasé
        return "Boot Cut/Évasé"

    return None


def _normalize_tommy_brand(raw_brand: Optional[Any]) -> Optional[str]:
    """Normalise les variantes Tommy pour éviter "Hilfiger Denim"."""
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
                    "_normalize_tommy_brand: alias '%s' détecté, normalisation en Tommy Hilfiger",
                    alias,
                )
                return "Tommy Hilfiger"

        return brand_str
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("_normalize_tommy_brand: erreur de normalisation (%s)", exc)
        try:
            return str(raw_brand).strip()
        except Exception:
            return None


def _normalize_fit_label(raw_fit: Optional[str]) -> Optional[str]:
    """
    Uniformise les libellés de coupe.
    Exemple : 'Boot Cut' → 'Boot Cut/Évasé'.
    """
    if not raw_fit:
        return None

    low = str(raw_fit).lower().strip()
    boot_markers = {"boot cut", "bootcut", "boot-cut", "flare", "curve", "curvy"}
    if any(marker in low for marker in boot_markers):
        return "Boot Cut/Évasé"

    if "skinny" in low or "slim" in low:
        return "Skinny"

    if "straight" in low or "droit" in low:
        return "Straight/Droit"

    return raw_fit


def _extract_color_from_text(text: str) -> Optional[str]:
    """
    Tente d'extraire une couleur simple (bleu délavé, bleu clair, etc.) depuis le texte.
    C'est volontairement minimaliste.
    """
    if not text:
        return None

    low = text.lower()
    if "bleu délavé" in low:
        return "bleu délavé"
    if "bleu clair" in low:
        return "bleu clair"
    if "bleu foncé" in low:
        return "bleu foncé"
    if "bleu" in low:
        return "bleu"

    return None


def _extract_carhartt_model_from_text(text: str) -> Optional[str]:
    """Détecte quelques modèles Carhartt courants à partir du texte libre."""
    try:
        if not text:
            return None

        low = text.lower()
        known_models = (
            "detroit",
            "active",
            "arctic",
            "michigan",
            "nimbus",
            "og",
            "new york",
            "ny",
            "trapper",
            "chore",
        )
        for model in known_models:
            if model in low:
                logger.info(
                    "_extract_carhartt_model_from_text: modèle détecté dans le texte (%s)", model
                )
                return model.title()
        return None
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "_extract_carhartt_model_from_text: détection impossible (%s)", exc
        )
        return None


def _looks_like_carhartt_sku(token: str) -> bool:
    """Repère un code produit (EJ001, BLK, etc.) pour l'ignorer du modèle."""

    try:
        if not token:
            return False

        cleaned = token.strip()
        if len(cleaned) < 3:
            return False

        has_digit = any(char.isdigit() for char in cleaned)
        has_upper = any(char.isupper() for char in cleaned)
        if has_digit and has_upper and re.fullmatch(r"[A-Za-z0-9]+", cleaned):
            logger.debug("_looks_like_carhartt_sku: token '%s' considéré comme SKU", cleaned)
            return True

        if cleaned.isupper() and has_digit:
            return True

        return False
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("_looks_like_carhartt_sku: détection impossible (%s)", exc)
        return False


def _normalize_carhartt_model(raw_model: Optional[str], fallback_text: str) -> Optional[str]:
    """Nettoie le modèle Carhartt pour éviter l'affichage de codes produits."""

    try:
        if not raw_model:
            return _extract_carhartt_model_from_text(fallback_text)

        tokens = re.split(r"[\s\-_/]+", raw_model.strip())
        filtered_tokens = [token for token in tokens if not _looks_like_carhartt_sku(token)]

        if not filtered_tokens:
            logger.info(
                "_normalize_carhartt_model: modèle brut '%s' ignoré (SKU détecté)", raw_model
            )
            return _extract_carhartt_model_from_text(fallback_text)

        candidate = " ".join(filtered_tokens).strip()
        if not candidate:
            return _extract_carhartt_model_from_text(fallback_text)

        logger.debug("_normalize_carhartt_model: modèle retenu '%s'", candidate)
        return candidate.title()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("_normalize_carhartt_model: normalisation impossible (%s)", exc)
        return _extract_carhartt_model_from_text(fallback_text)


def _detect_flag_from_text(text: str, keywords: tuple[str, ...]) -> Optional[bool]:
    try:
        if not text:
            return None
        low = text.lower()
        return any(keyword in low for keyword in keywords)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("_detect_flag_from_text: analyse impossible (%s)", exc)
        return None


def _extract_lining_from_text(text: str) -> Optional[str]:
    try:
        if not text:
            return None
        low = text.lower()
        if "sherpa" in low:
            return "doublure sherpa"
        if "matelass" in low:
            return "doublure matelassée"
        if "polar" in low:
            return "doublure polaire"
        if "doubl" in low:
            return "doublure textile"
        return None
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("_extract_lining_from_text: extraction impossible (%s)", exc)
        return None


def _extract_body_lining_composition(text: str) -> Optional[str]:
    try:
        segment = _extract_segment_with_composition(
            text, ("doublure", "interieur", "intérieur")
        )
        if not segment:
            return None
        cleaned = _strip_leading_keyword(
            segment, ("doublure", "interieur", "intérieur", "intérieur du corps")
        )
        logger.info("_extract_body_lining_composition: segment détecté = %s", cleaned)
        return cleaned
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("_extract_body_lining_composition: échec (%s)", exc)
        return None


def _extract_segment_with_composition(text: str, keywords: tuple[str, ...]) -> Optional[str]:
    """Extrait un segment contenant des compositions (100 %) associé à un mot-clé."""

    try:
        if not text:
            return None

        lowered = text.lower()
        if not any(keyword in lowered for keyword in keywords):
            return None

        candidates = re.split(r"[\n\.?!]", text)
        for segment in candidates:
            if not segment:
                continue
            if any(keyword in segment.lower() for keyword in keywords):
                cleaned = segment.strip(" ,;:\n")
                if cleaned:
                    return cleaned
        return None
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug(
            "_extract_segment_with_composition: extraction échouée (%s)", exc
        )
        return None


def _strip_leading_keyword(segment: str, keywords: tuple[str, ...]) -> str:
    try:
        if not segment:
            return ""
        result = segment
        for keyword in keywords:
            pattern = rf"^\s*{keyword}\s*[:\-–]?\s*"
            result = re.sub(pattern, "", result, flags=re.IGNORECASE)
        return result.strip()
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("_strip_leading_keyword: nettoyage impossible (%s)", exc)
        return segment


def _extract_exterior_from_text(text: str) -> Optional[str]:
    try:
        segment = _extract_segment_with_composition(
            text, ("exterieur", "extérieur", "exterior")
        )
        if not segment:
            return None
        cleaned = _strip_leading_keyword(
            segment, ("exterieur", "extérieur", "exterior")
        )
        logger.info("_extract_exterior_from_text: segment détecté = %s", cleaned)
        return cleaned
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("_extract_exterior_from_text: échec (%s)", exc)
        return None


def _extract_sleeve_lining_from_text(text: str) -> Optional[str]:
    try:
        segment = _extract_segment_with_composition(
            text, ("doublure des manches", "manches doubl", "sleeve lining")
        )
        if not segment:
            return None
        cleaned = _strip_leading_keyword(
            segment, ("doublure des manches", "manches doubl", "sleeve lining")
        )
        logger.info("_extract_sleeve_lining_from_text: segment détecté = %s", cleaned)
        return cleaned
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("_extract_sleeve_lining_from_text: échec (%s)", exc)
        return None


def _split_carhartt_composition_blocks(text: Optional[str]) -> Dict[str, str]:
    """Décompose un bloc de composition en segments ext/intérieur/manches."""

    try:
        if not text:
            return {}

        cleaned = str(text).strip()
        if not cleaned:
            return {}

        parts = re.split(r"[;,\n]", cleaned)
        blocks: Dict[str, str] = {}

        def assign_if_absent(key: str, value: str, keywords: tuple[str, ...]) -> None:
            nonlocal blocks
            if key in blocks:
                return
            lowered = value.lower()
            if any(marker in lowered for marker in keywords):
                stripped = _strip_leading_keyword(value, keywords)
                stripped = stripped.strip(" .-:")
                if stripped:
                    blocks[key] = stripped
                    logger.info(
                        "_split_carhartt_composition_blocks: segment '%s' affecté à %s",
                        stripped,
                        key,
                    )

        for part in parts:
            fragment = part.strip()
            if not fragment:
                continue
            assign_if_absent("exterior", fragment, ("exterieur", "extérieur", "exterior"))
            assign_if_absent(
                "sleeve_lining", fragment, ("doublure des manches", "manches", "sleeve")
            )
            assign_if_absent(
                "lining",
                fragment,
                ("doublure", "interieur", "intérieur", "doublure corps"),
            )

        return blocks
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("_split_carhartt_composition_blocks: découpe impossible (%s)", exc)
        return {}


def _extract_closure_from_text(text: str) -> Optional[str]:
    try:
        if not text:
            return None
        low = text.lower()
        if "double zip" in low or "double zipper" in low:
            return "double zip"
        if "zip" in low:
            return "zip"
        if "pression" in low:
            return "boutons pression"
        if "bouton" in low:
            return "boutons"
        return None
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("_extract_closure_from_text: extraction impossible (%s)", exc)
        return None


def _extract_patch_material_from_text(text: str) -> Optional[str]:
    try:
        if not text:
            return None
        low = text.lower()
        if "patch cuir" in low or "écusson cuir" in low:
            return "cuir"
        if "patch tissu" in low or "écusson tissu" in low:
            return "tissu"
        if "patch" in low or "écusson" in low:
            return "écusson visible"
        return None
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("_extract_patch_material_from_text: extraction impossible (%s)", exc)
        return None


def _extract_collar_from_text(text: str) -> Optional[str]:
    """Déduit le type de col à partir du texte libre."""

    try:
        if not text:
            return None

        low = text.lower()
        collar_map = {
            "col montant": "col montant",
            "col teddy": "col teddy",
            "col officier": "col officier",
            "col chemise": "col chemise",
            "col rabattu": "col rabattu",
            "col bord": "col bord-côte",
        }

        for marker, label in collar_map.items():
            if marker in low:
                logger.debug("_extract_collar_from_text: col détecté (%s)", label)
                return label

        return None
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("_extract_collar_from_text: extraction impossible (%s)", exc)
        return None


def _extract_zip_material_from_text(text: str) -> Optional[str]:
    """Identifie la matière dominante du zip (métal/plastique)."""

    try:
        if not text:
            return None

        low = text.lower()
        if "zip métal" in low or "zip metal" in low or "fermeture métal" in low:
            logger.debug("_extract_zip_material_from_text: zip métal détecté")
            return "métal"
        if "zip plastique" in low or "fermeture plastique" in low:
            logger.debug("_extract_zip_material_from_text: zip plastique détecté")
            return "plastique"
        return None
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("_extract_zip_material_from_text: extraction impossible (%s)", exc)
        return None


def _extract_origin_country_from_text(text: str) -> Optional[str]:
    """Repère le pays d'origine (Made in ...) dans le texte."""

    try:
        if not text:
            return None

        low = text.lower()
        match = re.search(r"made in\s+([a-z\s]+)", low)
        if match:
            country_raw = match.group(1).strip()
            country_map = {
                "usa": "USA",
                "united states": "USA",
                "états-unis": "USA",
                "mexico": "Mexique",
                "mexique": "Mexique",
                "china": "Chine",
                "chine": "Chine",
                "bangladesh": "Bangladesh",
                "india": "Inde",
                "inde": "Inde",
            }

            for marker, label in country_map.items():
                if marker in country_raw:
                    logger.debug("_extract_origin_country_from_text: origine détectée (%s)", label)
                    return label

            normalized_country = country_raw.title()
            logger.debug(
                "_extract_origin_country_from_text: origine détectée sans mapping (%s)",
                normalized_country,
            )
            return normalized_country
        return None
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("_extract_origin_country_from_text: extraction impossible (%s)", exc)
        return None


def _detect_chest_pocket_from_text(text: str) -> Optional[bool]:
    """Détecte la présence d'une poche poitrine dans le texte libre."""

    try:
        if not text:
            return None

        low = text.lower()
        markers = ("poche poitrine", "poche sur la poitrine", "poche avant")
        detected = any(marker in low for marker in markers)
        if detected:
            logger.debug("_detect_chest_pocket_from_text: poche poitrine détectée")
            return True
        return None
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("_detect_chest_pocket_from_text: détection impossible (%s)", exc)
        return None


MANDATORY_RAW_FOOTER = (
    "📏 Mesures détaillées visibles en photo pour plus de précisions.\n"
    "📦 Envoi rapide et soigné.\n"
    "✨ Retrouvez tous mes pulls Tommy femme ici 👉 #durin31tfM\n"
    "💡 Pensez à faire un lot pour profiter d’une réduction supplémentaire et "
    "économiser des frais d’envoi !\n\n"
    "#tommyhilfiger #pulltommy #tommy #pullfemme #modefemme #preloved "
    "#durin31tfM #ptf #rouge"
)


def _build_dynamic_footer(
    profile_name: AnalysisProfileName, context: Dict[str, Any]
) -> str:
    """
    Construit un footer obligatoire dynamique en fonction du profil et des tailles.
    """
    try:
        if profile_name == AnalysisProfileName.JEAN_LEVIS:
            size_fr = (context.get("size_fr") or "").strip()
            size_us = (context.get("size_us") or "").strip()
            length = (context.get("length") or "").strip()
            brand = (context.get("brand") or "Levi's").strip()
            model = (context.get("model") or "").strip()
            fit = (context.get("fit") or "").strip()
            color = (context.get("color") or "").strip()
            gender = (context.get("gender") or "").strip()
            rise_label = (context.get("rise_type") or "").strip()

            size_token = (size_fr or size_us or "nc").lower().replace(" ", "")
            durin_tag = f"#durin31fr{size_token}"

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

            footer_lines = [
                "📏 Mesures détaillées visibles en photo pour plus de précisions.",
                "📦 Envoi rapide et soigné.",
                f"✨ Retrouvez tous mes articles Levi’s à votre taille ici 👉 {durin_tag}",
                "💡 Pensez à faire un lot pour profiter d’une réduction supplémentaire et économiser des frais d’envoi !",
                hashtags,
            ]
            footer = "\n".join(line for line in footer_lines if line).strip()
            logger.info(
                "_build_dynamic_footer: footer jean Levi's généré avec taille=%s", size_token
            )
            return footer

        if profile_name == AnalysisProfileName.PULL_TOMMY:
            size_value = context.get("size") or context.get("size_estimated")
            color = ""
            try:
                colors = context.get("main_colors") or context.get("colors") or []
                if isinstance(colors, list) and colors:
                    color = str(colors[0]).lower()
            except Exception as color_exc:  # pragma: no cover - defensive
                logger.warning(
                    "_build_dynamic_footer: extraction couleur échouée (%s)", color_exc
                )

            from domain.description_builder import _normalize_pull_size  # local import

            size_token = _normalize_pull_size(size_value) or "NC"
            size_token = size_token.replace(" ", "")
            durin_tag = f"#durin31tf{size_token}"
            size_hashtag = f"#tf{size_token.lower()}"

            color_tag = f"#{color}" if color else ""
            footer_lines = [
                "📏 Mesures détaillées visibles en photo pour plus de précisions.",
                "📦 Envoi rapide et soigné.",
                f"✨ Retrouvez tous mes pulls Tommy femme ici 👉 {durin_tag}",
                "💡 Pensez à faire un lot pour profiter d’une réduction supplémentaire et économiser des frais d’envoi !",
            ]

            base_tags = "#tommyhilfiger #pulltommy #tommy #pullfemme #modefemme #preloved"
            tokens = " ".join(
                token
                for token in [base_tags, size_hashtag, durin_tag, color_tag]
                if token
            ).strip()
            footer_core = "\n".join(footer_lines)
            footer = (footer_core + "\n\n" + tokens).strip()
            logger.info(
                "_build_dynamic_footer: footer pull Tommy généré avec taille=%s", size_token
            )
            return footer

        if profile_name == AnalysisProfileName.JACKET_CARHART:
            size_value = context.get("size") or context.get("size_fr") or "NC"
            color_value = context.get("color") or ""
            size_token = str(size_value).strip() or "NC"
            size_tag = size_token.lower().replace(" ", "")
            color_tag = f"#{str(color_value).strip().lower()}" if color_value else ""
            durin_tag = f"#durin31jk{size_tag}"

            footer_lines = [
                "📏 Mesures détaillées visibles en photo pour plus de précisions.",
                "📦 Envoi rapide et soigné.",
                f"✨ Retrouvez toutes mes vestes Carhartt ici 👉 {durin_tag}",
                "💡 Pensez à faire un lot pour profiter d’une réduction supplémentaire et économiser des frais d’envoi !",
            ]

            hashtag_core = "#carhartt #jacket #workwear #durin31"
            hashtags = " ".join(token for token in [hashtag_core, durin_tag, color_tag] if token).strip()
            footer = ("\n".join(footer_lines) + "\n\n" + hashtags).strip()
            logger.info(
                "_build_dynamic_footer: footer veste Carhartt généré (taille=%s, couleur=%s)",
                size_token,
                color_value,
            )
            return footer

        logger.info("_build_dynamic_footer: profil non géré, footer par défaut")
        return MANDATORY_RAW_FOOTER
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("_build_dynamic_footer: échec (%s)", exc)
        return MANDATORY_RAW_FOOTER


def _enrich_raw_description(
    raw_description: str, context: Dict[str, Any], profile_name: AnalysisProfileName
) -> str:
    """
    Ajoute uniquement le footer obligatoire au texte brut fourni par l'IA et
    applique, si disponible, la composition saisie manuellement.
    """
    try:
        base_text = (raw_description or "").strip()
        manual_compo = (context.get("manual_composition_text") or "").strip()
        dynamic_footer = _build_dynamic_footer(profile_name, context)

        def _split_body_footer(text: str) -> tuple[str, str]:
            try:
                anchor = "📏 Mesures détaillées visibles en photo pour plus de précisions."
                idx = text.find(anchor)
                if idx != -1:
                    body = text[:idx].rstrip()
                    return body, ""

                if MANDATORY_RAW_FOOTER in text:
                    body = text.replace(MANDATORY_RAW_FOOTER, "").rstrip()
                    return body, ""

                return text.rstrip(), ""
            except Exception as exc_split:  # pragma: no cover - defensive
                logger.warning(
                    "_enrich_raw_description: split body/footer échoué (%s)",
                    exc_split,
                )
                return text.rstrip(), ""

        def _normalize_body_sizes(body_text: str) -> str:
            try:
                size_fr_val = context.get("size_fr")
                size_us_val = context.get("size_us")
                length_val = context.get("length")

                size_fr_clean = (
                    str(size_fr_val).strip() if size_fr_val is not None else None
                )
                size_us_clean = (
                    str(size_us_val).upper().replace(" ", "")
                    if size_us_val is not None
                    else None
                )
                length_clean = (
                    str(length_val).upper().replace(" ", "")
                    if length_val is not None
                    else None
                )

                if not any([size_fr_clean, size_us_clean, length_clean]):
                    return body_text.strip()

                parts = body_text.split("\n\n", 1)
                main_paragraph = parts[0].strip()
                remainder = parts[1] if len(parts) > 1 else ""

                for pattern in [r"W\d+\s*L\d+", r"W\d+", r"L\d+"]:
                    try:
                        main_paragraph = re.sub(
                            pattern, "", main_paragraph, flags=re.IGNORECASE
                        )
                    except Exception as replace_exc:  # pragma: no cover - defensive
                        logger.debug(
                            "_enrich_raw_description: regex taille ignorée (%s)",
                            replace_exc,
                        )

                main_paragraph = re.sub(r"\s{2,}", " ", main_paragraph).strip()

                size_tokens = []
                us_block = None
                if size_us_clean:
                    us_block = size_us_clean
                    if length_clean:
                        us_block = f"{us_block} {length_clean}".strip()

                if size_fr_clean and us_block:
                    size_tokens.append(f"Taille {size_fr_clean} FR (US {us_block})")
                elif size_fr_clean:
                    size_tokens.append(f"Taille {size_fr_clean} FR")
                elif us_block:
                    size_tokens.append(f"Taille US {us_block}")
                elif length_clean:
                    size_tokens.append(f"Longueur {length_clean}")

                if size_tokens:
                    size_sentence = ", ".join(size_tokens) + "."
                    try:
                        replaced = re.sub(
                            r"\b[Tt]aille[^.?!]*[.?!]?",
                            size_sentence,
                            main_paragraph,
                            count=1,
                        ).strip()
                        if replaced != main_paragraph:
                            main_paragraph = replaced
                        else:
                            main_paragraph = f"{main_paragraph} {size_sentence}".strip()
                    except Exception as size_replace_exc:  # pragma: no cover - defensive
                        logger.warning(
                            "_enrich_raw_description: réinjection taille échouée (%s)",
                            size_replace_exc,
                        )
                        main_paragraph = f"{main_paragraph} {size_sentence}".strip()

                recombined = (
                    main_paragraph
                    if not remainder
                    else f"{main_paragraph}\n\n{remainder.strip()}"
                )
                logger.debug(
                    "_enrich_raw_description: taille normalisée dans le corps = %s",
                    recombined,
                )
                return recombined.strip()
            except Exception as exc_size:  # pragma: no cover - defensive
                logger.warning(
                    "_enrich_raw_description: normalisation tailles échouée (%s)",
                    exc_size,
                )
                return body_text.strip()

        def _inject_composition(body_text: str, composition: str) -> str:
            try:
                placeholders = [
                    "Composition non lisible (voir photos).",
                    "Etiquette de composition coupée pour plus de confort.",
                ]
                cleaned_body = body_text
                for placeholder in placeholders:
                    cleaned_body = cleaned_body.replace(placeholder, composition)

                if composition in cleaned_body:
                    return cleaned_body.strip()

                if "\n\n" in cleaned_body:
                    first_paragraph, rest = cleaned_body.split("\n\n", 1)
                    return f"{first_paragraph.strip()}\n\n{composition}\n\n{rest.strip()}".strip()

                return f"{cleaned_body.strip()}\n\n{composition}".strip()
            except Exception as exc_inject:  # pragma: no cover - defensive
                logger.warning(
                    "_enrich_raw_description: injection composition échouée (%s)",
                    exc_inject,
                )
                return body_text.strip()

        body, _ = _split_body_footer(base_text)

        try:
            body = _normalize_body_sizes(body)
        except Exception as size_norm_exc:  # pragma: no cover - defensive
            logger.warning(
                "_enrich_raw_description: normalisation taille ignorée (%s)",
                size_norm_exc,
            )

        if manual_compo:
            replacement = f"Composition : {manual_compo.rstrip('.')}."
            body = _inject_composition(body, replacement)

        final_footer = dynamic_footer or MANDATORY_RAW_FOOTER
        enriched_text = (body + "\n\n" + final_footer).strip()

        logger.debug("_enrich_raw_description: texte enrichi produit")
        return enriched_text
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("_enrich_raw_description: échec, retour texte brut (%s)", exc)
        return raw_description


def _extract_sizes_from_text(text: str) -> tuple[Optional[str], Optional[str]]:
    """
    Extrait (size_us, length) à partir d'un texte contenant des W/L :
    - "W28 L30"
    - "W 28 L 30"
    - "W28L30"
    Retourne ("W28", "L30") ou (None, None).
    """
    if not text:
        return None, None

    compact = text.upper().replace(" ", "")
    w_match = re.search(r"W(\d+)", compact)
    l_match = re.search(r"L(\d+)", compact)

    size_us = f"W{w_match.group(1)}" if w_match else None
    length = f"L{l_match.group(1)}" if l_match else None
    return size_us, length


def normalize_sizes(features: dict) -> dict:
    """
    Corrige les tailles US issues du modèle.
    Gère :
    - "W28 L30"
    - "W28L30"
    - "W 28 L 30"
    - "W28"
    - "L30"
    """

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
        # On ne détruit pas une longueur déjà présente si elle est cohérente,
        # mais si elle est absente on la remplit.
        if not features.get("length"):
            features["length"] = l

    return features


# ---------------------------------------------------------------------------
# Construction des features pour JEAN_LEVIS (Gemini + OpenAI)
# ---------------------------------------------------------------------------


def build_features_for_jean_levis(
    ai_data: Dict[str, Any],
    ui_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Construit le dict 'features' attendu par build_jean_levis_title à partir :
      - ai_data : JSON renvoyé par l'IA (Gemini / OpenAI)
      - ui_data : données saisies dans l'UI (taille FR/US, corrections SKU/genre, etc.)

    Règles :
      - On utilise en priorité le bloc ai_data["features"] (cas Gemini).
      - Si une info manque, on va la chercher dans ai_data (titre + description).
      - On n'invente pas de valeurs précises, on prend uniquement ce qu'on peut
        déduire de manière raisonnable (Boot Cut, modèle 515, couleurs simples,
        tailles W/L).
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
        model = _extract_model_from_text(full_text)

    # --- Fit ---------------------------------------------------------------
    fit = raw_features.get("fit") or ai_data.get("fit")
    fit = _normalize_fit_label(fit)
    if not fit:
        fit = _extract_fit_from_text(full_text)

    # --- Color -------------------------------------------------------------
    color = raw_features.get("color") or ai_data.get("color")
    if not color:
        color = _extract_color_from_text(full_text)

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
        inferred_us, inferred_len = _extract_sizes_from_text(full_text)
        if not size_us and inferred_us:
            size_us = inferred_us
        if not length and inferred_len:
            length = inferred_len

    # --- Composition -------------------------------------------------------
    cotton_percent = raw_features.get("cotton_percent") or ai_data.get(
        "cotton_percent"
    )
    elasthane_percent = raw_features.get("elasthane_percent") or ai_data.get(
        "elasthane_percent"
    )

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
    sku = ui_data.get("sku") or raw_features.get("sku") or ai_data.get("sku")
    sku_status = raw_features.get("sku_status") or ai_data.get("sku_status")
    if not sku_status:
        sku_status = "missing" if sku is None else "ok"

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


# ---------------------------------------------------------------------------
# Construction des features pour PULL_TOMMY
# ---------------------------------------------------------------------------


def build_features_for_pull_tommy(
    ai_data: Dict[str, Any], ui_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Construit le dict 'features' pour un pull/gilet Tommy Hilfiger.

    Priorités :
      - données IA détaillées (ai_data["features"]),
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
                        "build_features_for_pull_tommy: taille UI retenue en mode mesures (%s)",
                        size,
                    )
                elif size_estimated:
                    size = size_estimated
                    computed_size_source = "estimated"
                    logger.info(
                        "build_features_for_pull_tommy: taille estimée depuis mesures IA (%s)",
                        size,
                    )
                elif size_label:
                    size = size_label
                    computed_size_source = size_source or "estimated"
                    logger.info(
                        "build_features_for_pull_tommy: taille issue des données IA malgré mode mesures (%s)",
                        size,
                    )
                else:
                    size = None
                    computed_size_source = None
                    logger.warning(
                        "build_features_for_pull_tommy: aucune taille estimable en mode mesures",
                    )
            else:
                size = size_from_ui or size_label
                computed_size_source = size_source or ("label" if size else None)
                if size:
                    logger.debug(
                        "build_features_for_pull_tommy: taille retenue mode etiquette (%s)",
                        size,
                    )
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception(
                "build_features_for_pull_tommy: erreur détermination taille (mode=%s)",
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
            """
            Valide un SKU de type étiquette tenue en main ou collée sur le produit :
            lettres (au moins 2) suivies de chiffres (ex : PTF127).
            """
            try:
                # 1. Supprimer tous les espaces de la chaîne fournie
                cleaned_value = re.sub(r"\s+", "", value)
                # 2. Vérifier que cleaned_value correspond à 2+ lettres puis à 1+ chiffres (espace toléré initialement)
                return bool(re.match(r'^[A-Za-z]{2,}\s*[0-9]+$', cleaned_value))
            except Exception:
                logger.debug(
                    "build_features_for_pull_tommy: validation SKU impossible pour '%s'",
                    value
                )
                return False

        if sku_source == "ui":
            sku = sku_from_ui
            if not sku_status or sku_status.lower() != "ok":
                sku_status = "ok"
            logger.debug(
                "build_features_for_pull_tommy: SKU fourni via UI conservé (%s)",
                sku,
            )
        else:
            if sku_from_ai and sku_status == "ok" and _is_label_sku(sku_from_ai):
                sku = re.sub(r"\s+", "", sku_from_ai)  # Enlever tous les espaces du SKU
                logger.info("SKU détecté sur étiquette accepté (%s)", sku)
                logger.info(
                    "build_features_for_pull_tommy: SKU détecté sur étiquette au premier plan accepté (%s)",
                    sku,
                )
            else:
                if sku_from_ai:
                    logger.info(
                        "build_features_for_pull_tommy: SKU IA rejeté (statut=%s, valeur=%s)",
                        sku_status,
                        sku_from_ai,
                    )
                sku = None
                sku_status = "missing"

        try:
            normalized_brand = _normalize_tommy_brand(brand)
        except Exception as brand_exc:  # pragma: no cover - defensive
            logger.warning(
                "build_features_for_pull_tommy: échec normalisation marque (%s)",
                brand_exc,
            )
            normalized_brand = brand

        features: Dict[str, Any] = {
            "brand": normalized_brand,
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

        # Détection du coton Pima dans la description IA ou l'étiquette
        description_text = (ai_data.get("description") or "").lower()
        material_text = (raw_features.get("material") or "").lower()
        pima_detected = ("pima coton" in description_text or "pima cotton" in description_text
                         or "pima coton" in material_text or "pima cotton" in material_text)
        features["is_pima"] = pima_detected

        if pima_detected:
            logger.info("build_features_for_pull_tommy: mention 'Pima cotton' détectée dans les données IA")
        return features

    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("build_features_for_pull_tommy: échec -> features vides (%s)", exc)
        return {}


def build_features_for_jacket_carhart(
    ai_data: Dict[str, Any], ui_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Construit les features nécessaires au titre/description Carhartt."""

    try:
        ui_data = ui_data or {}
        raw_features = ai_data.get("features") or {}

        title = ai_data.get("title") or ""
        description = ai_data.get("description") or ""
        full_text = f"{title} {description}".strip()

        brand = raw_features.get("brand") or ai_data.get("brand") or "Carhartt"
        model = raw_features.get("model") or ai_data.get("model")
        model = _normalize_carhartt_model(model, full_text)
        if not model:
            model = _extract_carhartt_model_from_text(full_text)

        size = (
            ui_data.get("size_fr")
            or ui_data.get("size")
            or raw_features.get("size")
            or ai_data.get("size")
        )

        color = raw_features.get("color") or ai_data.get("color")
        if not color:
            color = _extract_color_from_text(full_text)

        gender = ui_data.get("gender") or raw_features.get("gender") or ai_data.get("gender")

        has_hood = raw_features.get("has_hood")
        if has_hood is None:
            has_hood = _detect_flag_from_text(full_text, ("capuche", "hood"))

        pattern = raw_features.get("pattern") or ai_data.get("pattern")
        lining = raw_features.get("lining") or ai_data.get("lining")
        if lining is None:
            lining = _extract_lining_from_text(full_text)
        if lining is None or "%" not in str(lining):
            lining_composition = _extract_body_lining_composition(full_text)
            if lining_composition:
                lining = lining_composition

        closure = raw_features.get("closure") or ai_data.get("closure")
        if closure is None:
            closure = _extract_closure_from_text(full_text)

        patch_material = raw_features.get("patch_material") or ai_data.get("patch_material")
        if patch_material is None:
            patch_material = _extract_patch_material_from_text(full_text)

        collar = raw_features.get("collar") or ai_data.get("collar")
        if collar is None:
            collar = _extract_collar_from_text(full_text)

        zip_material = raw_features.get("zip_material") or ai_data.get("zip_material")
        if zip_material is None:
            zip_material = _extract_zip_material_from_text(full_text)

        origin_country = raw_features.get("origin_country") or ai_data.get("origin_country")
        if origin_country is None:
            origin_country = _extract_origin_country_from_text(full_text)

        exterior = raw_features.get("exterior") or ai_data.get("exterior")
        if exterior is None:
            exterior = _extract_exterior_from_text(full_text)

        sleeve_lining = raw_features.get("sleeve_lining") or ai_data.get("sleeve_lining")
        if sleeve_lining is None:
            sleeve_lining = _extract_sleeve_lining_from_text(full_text)

        split_blocks: Dict[str, str] = {}
        for candidate in (exterior, sleeve_lining, lining, full_text):
            split_blocks.update({k: v for k, v in _split_carhartt_composition_blocks(candidate).items() if v})

        if split_blocks.get("exterior"):
            exterior = split_blocks["exterior"]
        if split_blocks.get("lining"):
            lining = split_blocks["lining"]
        if split_blocks.get("sleeve_lining"):
            sleeve_lining = split_blocks["sleeve_lining"]

        has_chest_pocket = raw_features.get("has_chest_pocket")
        if has_chest_pocket is None:
            has_chest_pocket = _detect_chest_pocket_from_text(full_text)

        is_camouflage = raw_features.get("is_camouflage")
        if is_camouflage is None and pattern:
            is_camouflage = pattern.lower() == "camouflage"
        if is_camouflage is None:
            is_camouflage = _detect_flag_from_text(full_text, ("camouflage",))

        is_realtree = raw_features.get("is_realtree")
        if is_realtree is None:
            is_realtree = _detect_flag_from_text(full_text, ("realtree",))

        is_new_york = raw_features.get("is_new_york")
        if is_new_york is None:
            is_new_york = _detect_flag_from_text(full_text, ("new york", " ny"))

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
        }

        logger.debug("build_features_for_jacket_carhart: features=%s", features)
        return features
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception(
            "build_features_for_jacket_carhart: échec -> features vides (%s)", exc
        )
        return {}


# ---------------------------------------------------------------------------
# Normalisation + post-process complet (point d'entrée)
# ---------------------------------------------------------------------------


def normalize_and_postprocess(
    ai_data: Dict[str, Any],
    profile_name: AnalysisProfileName,
    ui_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Point d’entrée unique pour :
      - extraire / normaliser les features,
      - appliquer la logique métier du profil,
      - construire le titre final,
      - renvoyer un dict complet pour VintedListing.

    Ici, on ne gère PAS l'affichage UI, uniquement les données (diagnostic).
    """
    ui_data = ui_data or {}
    result: Dict[str, Any] = {}

    # --- 1) Construction des features selon le profil ---------------------
    if profile_name == AnalysisProfileName.JEAN_LEVIS:
        features = build_features_for_jean_levis(ai_data, ui_data)
        features = normalize_sizes(features)

        # Titre reconstruit de manière cohérente pour TOUS les providers
        title = build_jean_levis_title(features)
    elif profile_name == AnalysisProfileName.PULL_TOMMY:
        features = build_features_for_pull_tommy(ai_data, ui_data)
        title = build_pull_tommy_title(features)
    elif profile_name == AnalysisProfileName.JACKET_CARHART:
        features = build_features_for_jacket_carhart(ai_data, ui_data)
        title = build_jacket_carhart_title(features)
    else:
        # Pour les autres profils (à développer plus tard)
        features = {}
        title = ai_data.get("title") or ""

    logger.debug("normalize_and_postprocess: features construites: %s", features)

    raw_description = ai_data.get("description") or ""

    try:
        raw_description = _enrich_raw_description(
            raw_description, {**ai_data, **features}, profile_name
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception(
            "normalize_and_postprocess: enrichissement description brute échoué (%s)",
            exc,
        )

    # --- 2) Description ----------------------------------------------------
    try:
        if profile_name == AnalysisProfileName.JEAN_LEVIS:
            description = build_jean_levis_description(
                {**features, "defects": ai_data.get("defects")},
                ai_description=ai_data.get("description"),
                ai_defects=ai_data.get("defects"),
            )
        elif profile_name == AnalysisProfileName.PULL_TOMMY:
            description = build_pull_tommy_description(
                {**features, "defects": ai_data.get("defects")},
                ai_description=ai_data.get("description"),
                ai_defects=ai_data.get("defects"),
            )
            try:
                description = _strip_footer_lines(description)
            except Exception as nested_exc:  # pragma: no cover - defensive
                logger.warning(
                    "normalize_and_postprocess: nettoyage complémentaire ignoré (%s)",
                    nested_exc,
                )
            # AJOUT : si coton Pima détecté, remplacer "coton" par "pima coton" dans la description finale
            if features.get("is_pima"):
                # Remplacement en évitant les hashtags (ex: "#pullcoton")
                description = re.sub(r"\bcoton\b", "pima coton", description, flags=re.IGNORECASE)
                logger.info(
                    "normalize_and_postprocess: 'coton' remplacé par 'pima coton' dans la description finale (PULL_TOMMY)")
        elif profile_name == AnalysisProfileName.JACKET_CARHART:
            description = build_jacket_carhart_description(
                {**features, "defects": ai_data.get("defects")},
                ai_description=ai_data.get("description"),
                ai_defects=ai_data.get("defects"),
            )
        else:
            description = ai_data.get("description")
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception(
            "normalize_and_postprocess: erreur description -> fallback brut (%s)",
            exc,
        )
        if profile_name == AnalysisProfileName.PULL_TOMMY:
            try:
                description = _strip_footer_lines(raw_description)
            except Exception as nested_exc:  # pragma: no cover - defensive
                logger.warning(
                    "normalize_and_postprocess: nettoyage footer ignoré (%s)",
                    nested_exc,
                )
                description = raw_description
        else:
            description = raw_description

    # --- 3) Merge final ----------------------------------------------------
    result.update(features)
    result["features"] = dict(features)
    result["title"] = title
    try:
        result["description"] = _strip_footer_lines(description)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "normalize_and_postprocess: impossibilité de nettoyer le footer final (%s)",
            exc,
        )
        result["description"] = description

    result["description_raw"] = raw_description

    return result
