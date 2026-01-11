# domain/normalizer.py

"""
Module de normalisation des annonces Vinted.

Ce module a été refactorisé pour améliorer la maintenabilité.
Les fonctions de base et les builders de features ont été déplacés vers
le package `domain.normalizers`.

Ce fichier reste le point d'entrée principal pour la compatibilité ascendante.
"""

from __future__ import annotations

import re
from typing import Dict, Any, Optional
import logging

from domain.description_builder import (
    _build_hashtags,
    _strip_footer_lines,
    _normalize_pull_size,
)
from domain.description_engine import build_description
from domain.templates import AnalysisProfileName
from domain.title_engine import build_title
from domain.validator import is_valid_internal_sku

# Import depuis les nouveaux modules refactorisés
from domain.normalizers.base import (
    ALIASES,
    REQUIRED_KEYS,
    FEATURE_DEFAULTS,
    normalize_listing,
    coerce_profile_name as _coerce_profile_name,
    apply_feature_defaults as _apply_feature_defaults,
    normalize_tommy_brand as _normalize_tommy_brand,
    normalize_sizes,
)
from domain.normalizers.jean_levis import build_features_for_jean_levis
from domain.normalizers.pull import build_features_for_pull, build_features_for_pull_tommy
from domain.normalizers.jacket_carhart import build_features_for_jacket_carhart

logger = logging.getLogger(__name__)

# Re-export pour compatibilite
__all__ = [
    "ALIASES",
    "REQUIRED_KEYS",
    "FEATURE_DEFAULTS",
    "normalize_listing",
    "normalize_sizes",
    "normalize_and_postprocess",
    "build_features_for_jean_levis",
    "build_features_for_pull",
    "build_features_for_pull_tommy",  # Alias pour retrocompatibilite
    "build_features_for_jacket_carhart",
]


# ---------------------------------------------------------------------------
# Constantes pour les footers
# ---------------------------------------------------------------------------

MANDATORY_RAW_FOOTER = (
    "📏 Mesures détaillées visibles en photo pour plus de précisions.\n"
    "📦 Envoi rapide et soigné.\n"
    "✨ Retrouvez tous mes pulls Tommy femme ici 👉 #durin31tfM\n"
    "💡 Pensez à faire un lot pour profiter d'une réduction supplémentaire et "
    "économiser des frais d'envoi !\n\n"
    "#tommyhilfiger #pulltommy #tommy #pullfemme #modefemme #preloved "
    "#durin31tfM #ptf #rouge"
)


# ---------------------------------------------------------------------------
# Construction des footers dynamiques
# ---------------------------------------------------------------------------

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
                f"✨ Retrouvez tous mes articles Levi's à votre taille ici 👉 {durin_tag}",
                "💡 Pensez à faire un lot pour profiter d'une réduction supplémentaire et économiser des frais d'envoi !",
                hashtags,
            ]
            footer = "\n".join(line for line in footer_lines if line).strip()
            logger.info(
                "_build_dynamic_footer: footer jean Levi's généré avec taille=%s", size_token
            )
            return footer

        if profile_name == AnalysisProfileName.PULL:
            size_value = context.get("size") or context.get("size_estimated")
            color = ""
            try:
                colors = context.get("main_colors") or context.get("colors") or []
                if isinstance(colors, list) and colors:
                    color = str(colors[0]).lower()
            except Exception as color_exc:
                logger.warning(
                    "_build_dynamic_footer: extraction couleur échouée (%s)", color_exc
                )

            size_token = _normalize_pull_size(size_value) or "NC"
            size_token = size_token.replace(" ", "")
            durin_tag = f"#durin31tf{size_token}"
            size_hashtag = f"#tf{size_token.lower()}"

            color_tag = f"#{color}" if color else ""
            footer_lines = [
                "📏 Mesures détaillées visibles en photo pour plus de précisions.",
                "📦 Envoi rapide et soigné.",
                f"✨ Retrouvez tous mes pulls Tommy femme ici 👉 {durin_tag}",
                "💡 Pensez à faire un lot pour profiter d'une réduction supplémentaire et économiser des frais d'envoi !",
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
                "💡 Pensez à faire un lot pour profiter d'une réduction supplémentaire et économiser des frais d'envoi !",
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
    except Exception as exc:
        logger.exception("_build_dynamic_footer: échec (%s)", exc)
        return MANDATORY_RAW_FOOTER


# ---------------------------------------------------------------------------
# Enrichissement de la description brute
# ---------------------------------------------------------------------------

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
            except Exception as exc_split:
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
                    except Exception as replace_exc:
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
                    except Exception as size_replace_exc:
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
            except Exception as exc_size:
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
            except Exception as exc_inject:
                logger.warning(
                    "_enrich_raw_description: injection composition échouée (%s)",
                    exc_inject,
                )
                return body_text.strip()

        body, _ = _split_body_footer(base_text)

        try:
            body = _normalize_body_sizes(body)
        except Exception as size_norm_exc:
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
    except Exception as exc:
        logger.exception("_enrich_raw_description: échec, retour texte brut (%s)", exc)
        return raw_description


# ---------------------------------------------------------------------------
# Normalisation + post-process complet (point d'entrée)
# ---------------------------------------------------------------------------

def normalize_and_postprocess(
    ai_data: Dict[str, Any],
    profile_name: AnalysisProfileName,
    ui_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Point d'entrée unique pour :
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

    elif profile_name == AnalysisProfileName.PULL:
        features = build_features_for_pull(ai_data, ui_data)

    elif profile_name == AnalysisProfileName.JACKET_CARHART:
        # Support 2 formats possibles venant du pipeline
        ocr_sku_candidates = ai_data.get("_ocr_sku_candidates")

        if not ocr_sku_candidates:
            structured = ai_data.get("_structured_ocr") or {}
            if isinstance(structured, dict):
                ocr_sku_candidates = structured.get("sku_candidates")

        if not isinstance(ocr_sku_candidates, list):
            ocr_sku_candidates = []

        features = build_features_for_jacket_carhart(
            ai_data, ui_data, ocr_sku_candidates=ocr_sku_candidates
        )
    else:
        # Pour les autres profils (à développer plus tard)
        features = {}

    features = _apply_feature_defaults(profile_name, features)

    title_context = dict(features)
    try:
        if ai_data.get("title"):
            title_context["title"] = ai_data.get("title")
    except Exception as exc:
        logger.warning(
            "normalize_and_postprocess: impossibilité d'ajouter le titre brut (%s)", exc
        )
    title = build_title(profile_name, title_context)

    logger.debug("normalize_and_postprocess: features construites: %s", features)

    sku = features.get("sku")

    if sku and not is_valid_internal_sku(profile=profile_name, sku=sku):
        logger.warning(
            "SKU incohérent après normalisation (profil=%s): '%s' -> rejeté",
            getattr(profile_name, "value", profile_name),
            sku,
        )
        features["sku"] = None
        features["sku_status"] = "invalid"

    raw_description = ai_data.get("description") or ""

    try:
        raw_description = _enrich_raw_description(
            raw_description, {**ai_data, **features}, profile_name
        )
    except Exception as exc:
        logger.exception(
            "normalize_and_postprocess: enrichissement description brute échoué (%s)",
            exc,
        )

    # --- 2) Description ----------------------------------------------------
    try:
        description = build_description(
            profile_name=profile_name,
            features={**features, "defects": ai_data.get("defects")},
            ai_description=ai_data.get("description"),
            ai_defects=ai_data.get("defects"),
        )
        if profile_name == AnalysisProfileName.PULL:
            try:
                description = _strip_footer_lines(description)
            except Exception as nested_exc:
                logger.warning(
                    "normalize_and_postprocess: nettoyage complémentaire ignoré (%s)",
                    nested_exc,
                )
            if features.get("is_pima"):
                description = re.sub(
                    r"\bcoton\b", "pima coton", description, flags=re.IGNORECASE
                )
                logger.info(
                    "normalize_and_postprocess: 'coton' remplace par 'pima coton' (PULL)"
                )
    except Exception as exc:
        logger.exception(
            "normalize_and_postprocess: erreur description -> fallback brut (%s)",
            exc,
        )
        if profile_name == AnalysisProfileName.PULL:
            try:
                description = _strip_footer_lines(raw_description)
            except Exception as nested_exc:
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
    except Exception as exc:
        logger.warning(
            "normalize_and_postprocess: impossibilité de nettoyer le footer final (%s)",
            exc,
        )
        result["description"] = description

    result["description_raw"] = raw_description

    return result
