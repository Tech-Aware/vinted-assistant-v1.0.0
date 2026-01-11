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

        # --- Fit effectif (doit matcher le titre) ---
        fit_effective = fit
        model_low = (model or "").lower()

        # règle métier: Demi Curve => Bootcut/Évasé
        # (on évite de forcer Bootcut dès qu'on voit "curve" seul si tu as d'autres modèles "Curve")
        if "demi" in model_low and "curve" in model_low:
            fit_effective = "Bootcut/Évasé"
        elif "curve" in model_low and not fit_effective:
            # fallback doux si l'IA n'a rien mis dans fit
            fit_effective = "Bootcut/Évasé"

        title_intro_parts = ["Jean", brand]
        if model:
            title_intro_parts.append(model)
        title_intro = " ".join(title_intro_parts)

        intro_sentence = f"{title_intro} pour {gender}."

        # --- Phrase taille / coupe / rise ---
        size_sentence_parts: List[str] = []

        if size_us and size_fr:
            size_sentence_parts.append(f"Taille {size_us} US (équivalent {size_fr} FR)")
        elif size_fr:
            size_sentence_parts.append(f"Taille {size_fr} FR")
        elif size_us:
            size_sentence_parts.append(f"Taille {size_us} US")

        if fit_effective:
            size_sentence_parts.append(f"coupe {fit_effective}")

        if rise_label:
            size_sentence_parts.append(f"à {rise_label}")

        if size_sentence_parts:
            size_sentence_parts.append("pour une silhouette ajustée et confortable")

        size_sentence = ", ".join(size_sentence_parts).strip()
        size_sentence = f"{size_sentence}." if size_sentence else "Taille non précisée."

        # --- Couleur ---
        color_has_fade = "lavé" in color.lower() if color else False
        if color:
            nuance = " légèrement délavé" if not color_has_fade else ""
            color_sentence = f"Coloris {color}{nuance}, très polyvalent et facile à assortir."
        else:
            color_sentence = "Coloris non précisé, se référer aux photos pour les nuances."

        # --- Prose / sensation (prudente, dérivée des features) ---
        comfort_sentence = None
        try:
            # On ne "promet" pas : juste des formulations non risquées
            elas_val = _format_percent(features.get("elasthane_percent"))

            base = "Denim agréable à porter"

            # "stretch" uniquement si > 2%
            if elas_val is not None and elas_val > 2:
                base += ", stretch pour plus de confort"

            # fit
            fit_low = (fit_effective or "").lower()
            if "boot" in fit_low or "évas" in fit_low or "evas" in fit_low or "flare" in fit_low:
                base += ", avec une jambe qui s’évase subtilement en bas"
            elif "skinny" in fit_low:
                base += ", coupe près du corps"

            '''# rise
            if rise_label:
                rl = rise_label.lower()
                if "basse" in rl:
                    base += ", taille basse"
                elif "haute" in rl:
                    base += ", taille haute"
                elif "moyenne" in rl or "mi-haute" in rl or "mi haute" in rl:
                    base += ", taille mi-haute"'''

            comfort_sentence = base.strip().rstrip(".") + "."
        except Exception:
            comfort_sentence = None

        composition_sentence = _build_composition(
            features.get("cotton_percent"),
            features.get("elasthane_percent"),
        )

        closure_sentence = "Fermeture zippée + bouton gravé Levi’s."
        state_sentence = _build_state_sentence(ai_defects or features.get("defects"))

        logistics_sentence = "📏 Mesures visibles en photo."
        shipping_sentence = "📦 Envoi rapide et soigné."

        cta_lot_sentence = "💡 Pensez à un lot pour profiter d’une réduction supplémentaire et économiser des frais d’envoi !"
        durin_tag = f"#durin31fr{(size_fr or 'nc').lower()}"
        cta_durin_sentence = f"✨ Retrouvez tous mes articles Levi’s à votre taille ici 👉 {durin_tag}"

        # IMPORTANT: passer fit_effective au builder hashtags pour éviter incohérences (#skinnyjean vs bootcut)
        hashtags = _build_hashtags(
            brand=brand,
            model=model,
            fit=fit_effective,  # <-- ici
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
            comfort_sentence,
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



def build_description_pull(
    features: Dict[str, Any], ai_description: Optional[str] = None, ai_defects: Optional[str] = None
) -> str:
    """
    Construit une description pour les pulls.

    Supporte:
      - Pulls branded (Tommy Hilfiger, Ralph Lauren, etc.)
      - Pulls vintage/unbranded (is_vintage=True ou brand=None)
    """
    try:
        logger.info("build_description_pull: features recus = %s", features)

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

        # --- Couleurs normalisées (texte simple) ---
        colors = ""
        if isinstance(colors_raw, list):
            colors = ", ".join([_safe_clean(c) for c in colors_raw if _safe_clean(c)])
        else:
            colors = _safe_clean(colors_raw)

        # --- Normaliser neckline pour éviter "col col V" ---
        neckline_text = ""
        if neckline:
            nl = neckline.strip()
            if nl.lower().startswith("col"):
                neckline_text = nl  # ex: "col V"
            else:
                neckline_text = f"col {nl}"

        # --- Headline (plus naturel) ---
        # Ex: "Pull Tommy Hilfiger femme - taille XL. Maille torsadée, col V, bleu. 100% coton."
        headline_main: List[str] = [f"{garment_type.capitalize()} {brand}"]
        if gender:
            headline_main.append(gender.lower())

        cotton_val = _format_percent(cotton_percent)
        wool_val = _format_percent(wool_percent)
        angora_val = _format_percent(angora_percent)

        # --- Sensation / toucher (dérivé de la matière, sans invention) ---
        sensation_sentence = None
        if angora_val is not None:
            sensation_sentence = "Maille douce et légère au toucher, offrant un confort chaleureux et agréable."
        elif wool_val is not None:
            sensation_sentence = "Maille chaude et confortable, agréable à porter par temps frais."
        elif cotton_val is not None:
            sensation_sentence = "Maille douce et respirante, confortable pour un usage quotidien."


        # taille
        size_part = ""
        if size:
            if size_source == "estimated" or measurement_mode == "mesures":
                size_part = f"taille {size} (estimée via mesures)"
            else:
                size_part = f"taille {size}"

        headline_line1 = " ".join([p for p in headline_main if p]).strip()
        if size_part:
            headline_line1 = f"{headline_line1} - {size_part}"
        headline_line1 = headline_line1.rstrip(".") + "."

        # style (sans composition chiffrée)
        style_bits: List[str] = []
        if pattern:
            # pattern attendu: "torsadé", "uni", etc.
            style_bits.append(f"maille {pattern}".strip())
        if neckline_text:
            style_bits.append(neckline_text)
        if colors:
            style_bits.append(colors)

        headline_line2 = ", ".join([b for b in style_bits if b]).strip()
        if headline_line2:
            headline_line2 = headline_line2.rstrip(".") + "."

        headline = "\n".join([line for line in [headline_line1, headline_line2] if line])

        # --- Composition (priorité au % si dispo, sinon à l'étiquette texte) ---
        composition_sentence = None
        cotton_val = _format_percent(cotton_percent)
        wool_val = _format_percent(wool_percent)
        angora_val = _format_percent(angora_percent)

        comp_tokens = []
        if cotton_val is not None:
            comp_tokens.append(f"{cotton_val}% coton")
        if wool_val is not None:
            comp_tokens.append(f"{wool_val}% laine")
        if angora_val is not None:
            comp_tokens.append(f"{angora_val}% angora")

        if comp_tokens:
            composition_sentence = "Composition : " + " / ".join(comp_tokens) + "."
        else:
            mat = _safe_clean(material)
            if mat:
                composition_sentence = f"Composition (étiquette) : {mat.rstrip('.')}."
            else:
                composition_sentence = "Composition non lisible (voir photos)."

        # --- Phrase détail (propre) ---
        details_parts = []
        if neckline_text:
            details_parts.append(neckline_text)
        if pattern:
            details_parts.append(pattern)
        # details_sentence = f"Détails : {', '.join(details_parts)}." if details_parts else None
        details_sentence = None

        # --- État (cohérent) ---
        if defects:
            d = _safe_clean(defects).strip().rstrip(".")
            # "Aucun défaut..." -> "aucun défaut..."
            if d[:1].isupper():
                d = d[:1].lower() + d[1:]
            state_sentence = f"Bon état : {d} (voir photos)."
            logger.info("build_description_pull_tommy: état renseigné = %s", state_sentence)
        else:
            state_sentence = "État : très bon état (voir photos)."

        # --- Footer dynamique (taille) ---
        size_token = (size or "NC").replace(" ", "").upper()
        durin_tag = f"#durin31tf{size_token}"

        # --- Hashtags cohérents (pas de #rouge hardcodé) ---
        hashtag_tokens: List[str] = []
        def _add_tag(t: str) -> None:
            if t and t not in hashtag_tokens:
                hashtag_tokens.append(t)

        _add_tag("#tommyhilfiger")
        _add_tag("#pulltommy")
        _add_tag("#tommy")
        _add_tag("#pullfemme" if gender.lower() == "femme" else "#pullhomme")
        _add_tag("#mode")
        _add_tag("#preloved")
        _add_tag(durin_tag)
        _add_tag("#ptf")

        if colors:
            for c in colors.split(","):
                cc = c.strip().lower().replace(" ", "")
                if cc:
                    _add_tag(f"#{cc}")

        hashtags = " ".join(hashtag_tokens)

        footer = "\n".join(
            [
                "📏 Mesures detaillees visibles en photo pour plus de precisions.",
                "📦 Envoi rapide et soigne.",
                f"✨ Retrouvez tous mes pulls ici 👉 {durin_tag}",
                "💡 Pensez a faire un lot pour profiter d'une reduction supplementaire et economiser des frais d'envoi !",
                "",
                hashtags,
            ]
        )

        paragraphs = [
            headline,
            sensation_sentence,
            composition_sentence,
            state_sentence,
            footer,
        ]

        description = "\n\n".join([p for p in paragraphs if p])
        description = _safe_clean(description)
        logger.debug("build_description_pull: description generee = %s", description)
        return description

    except Exception as exc:  # pragma: no cover - robustesse
        logger.exception("build_description_pull: fallback description IA (%s)", exc)
        return _safe_clean(ai_description)


# Alias pour retrocompatibilite
build_description_pull_tommy = build_description_pull



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
                matches = re.findall(r"\d+\s*%\s*[A-Za-zÀ-ÿ'’\- ]+", cleaned)
                if matches:
                    return " / ".join(m.strip() for m in matches)
                return cleaned
            except Exception as exc:  # pragma: no cover
                logger.warning("_pick_percent_line: erreur (%s)", exc)
                return _clean_carhartt_material_segment(text) or ""

        # --- Warmth sentence: ne jamais injecter la composition dans la prose ---
        lining_label = ""
        try:
            low = (lining or "").lower()

            # uniquement des libellés "qualitatifs", jamais des %/matières
            if "matelass" in low or "quilt" in low:
                lining_label = "doublure matelassée"
            elif "sherpa" in low:
                lining_label = "doublure sherpa"
            elif "blanket" in low or "laine" in low:
                lining_label = "doublure type blanket"
            else:
                lining_label = ""  # important : sinon risque "70% acrylique..."
        except Exception as exc:  # pragma: no cover
            logger.debug("lining_label: fallback (%s)", exc)
            lining_label = ""

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
            joined = ", ".join(warmth_parts).strip().lstrip(", ").rstrip(".")
            # évite une phrase qui démarre par "avec ..."
            if joined.lower().startswith("avec "):
                joined = f"Veste agréable à porter, {joined}"
            warmth_sentence = joined + "."

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
        if profile_name == AnalysisProfileName.PULL:
            return build_description_pull(features, ai_description=ai_description, ai_defects=ai_defects)
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
