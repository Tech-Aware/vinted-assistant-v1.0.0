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
        order_id = _safe_clean(features.get("order_id"))
        rise_label = _format_rise_label(features.get("rise_type"), features.get("rise_cm"))
        defects = ai_defects or features.get("defects")

        cotton_percent = _format_percent(features.get("cotton_percent"))
        elasthane_percent = _format_percent(features.get("elasthane_percent"))
        composition_materials = features.get("composition_materials") or []
        composition_status = features.get("composition_status")

        # --- Fit effectif (doit matcher le titre) ---
        fit_effective = fit
        model_low = (model or "").lower()

        if "demi" in model_low and "curve" in model_low:
            fit_effective = "Bootcut/Évasé"
        elif "curve" in model_low and not fit_effective:
            fit_effective = "Bootcut/Évasé"

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

        # --- Construction du libellé de coupe pour la phrase d'intro ---
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

        # Construire "Ces Jeans évasés Levi's pour femme de taille moyenne..."
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

        # Genre
        if gender.lower() == "femme":
            hashtag_tokens.append("#levisfemme")
        else:
            hashtag_tokens.append("#levishomme")

        # Rise
        if rise_hashtag:
            hashtag_tokens.append(f"#{rise_hashtag}")

        # Coupe
        if fit_hashtag:
            hashtag_tokens.append(f"#{fit_hashtag}")
            hashtag_tokens.append(f"#jean{fit_hashtag}")

        # Couleur
        if color:
            color_clean = color.lower().replace(" ", "")
            hashtag_tokens.append(f"#jean{color_clean}")

        # Tag taille
        hashtag_tokens.append(size_tag)

        # Tag SKU + Order ID
        if sku:
            sku_clean = sku.lower().replace(" ", "")
            if order_id:
                hashtag_tokens.append(f"#{order_id}{sku_clean}")
            else:
                hashtag_tokens.append(f"#{sku_clean}")

        hashtags = " ".join(hashtag_tokens)

        # --- Assemblage final ---
        # Paragraphe 1: intro + composition + couleur + fermeture
        paragraph1 = f"{intro_sentence} {composition_sentence} {color_sentence} {closure_sentence}"

        # Bloc infos
        info_block = "\n".join([size_line, size_note, state_line, measures_line])

        # Footer
        footer_block = "\n".join([shipping_line, "", cta_size_line, cta_lot_line, "", hashtags])

        description = f"{paragraph1}\n\n{info_block}\n\n{footer_block}"
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
