# domain/normalizer.py

from __future__ import annotations

import re
from typing import Dict, Any, Optional
import logging

from domain.description_builder import (
    build_jean_levis_description,
    build_pull_tommy_description,
    _strip_footer_lines,
)
from domain.templates import AnalysisProfileName
from domain.title_builder import build_jean_levis_title, build_pull_tommy_title

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
                return bool(re.match(r"^[a-zA-Z]{2,}[0-9]+$", value.strip()))
            except Exception:
                logger.debug(
                    "build_features_for_pull_tommy: validation SKU impossible pour '%s'",
                    value,
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
                sku = sku_from_ai
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

        logger.debug("build_features_for_pull_tommy: features=%s", features)
        return features
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("build_features_for_pull_tommy: échec -> features vides (%s)", exc)
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
    else:
        # Pour les autres profils (à développer plus tard)
        features = {}
        title = ai_data.get("title") or ""

    logger.debug("normalize_and_postprocess: features construites: %s", features)

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
        else:
            description = ai_data.get("description")
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception(
            "normalize_and_postprocess: erreur description -> fallback brut (%s)",
            exc,
        )
        raw_description = ai_data.get("description") or ""
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

    return result
