# domain/title_builder.py

from __future__ import annotations

from typing import Dict, Any, List, Optional
import re
import logging

from domain.title_engine import (
    JeanSpec,
    JacketSpec,
    PullGiletSpec,
    TitleBlock,
    TitleRules,
    build_material_block,
    render_title,
)

logger = logging.getLogger(__name__)

SKU_PREFIX = "- "


def _normalize_str(value: Optional[str]) -> Optional[str]:
    """Trim + None-safe."""
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _normalize_fit(value: Optional[str]) -> Optional[str]:
    """
    Normalise la coupe pour rester cohérent dans les titres.

    Règles métier :
      - 'slim'  -> 'Skinny'
      - 'straight' ou 'droit' -> 'Straight/Droit'
      - 'bootcut' / 'flare' / 'évasé' -> 'Bootcut/Évasé'

    En dehors de ces cas, on renvoie la valeur d’origine nettoyée.
    """
    if not value:
        return None

    raw = value.strip()
    v = raw.lower()

    # Slim = Skinny
    if "slim" in v or "skinny" in v:
        return "Skinny"

    # Straight / Droit
    if "straight" in v or "droit" in v:
        return "Straight/Droit"

    # Bootcut / Évasé / Flare
    if (
        "bootcut" in v
        or "flare" in v
        or "évasé" in v
        or "evase" in v
        or "curve" in v
        or "curvy" in v
    ):
        return "Bootcut/Évasé"

    # Sinon, on garde la valeur telle quelle (juste trimée)
    return raw


def _sanitize_model_label(value: Optional[str]) -> Optional[str]:
    """Nettoie le modèle pour éviter les doublons de coupe dans le titre."""
    if not value:
        return None

    try:
        raw = value.strip()
        low = raw.lower()
        fit_markers = (
            "skinny",
            "slim",
            "straight",
            "droit",
            "boot",
            "flare",
            "évas",
            "evase",
            "curve",
            "curvy",
        )
        drop_markers = {"demi", "cut"}

        cleaned_tokens: List[str] = []
        for token in raw.replace("/", " ").replace("-", " ").split():
            try:
                token_low = token.lower()
                if any(marker in token_low for marker in fit_markers):
                    logger.debug("_sanitize_model_label: token coupe ignoré: %s", token)
                    continue
                if token_low in drop_markers:
                    logger.debug("_sanitize_model_label: token supprimé (marker): %s", token)
                    continue
                cleaned_tokens.append(token)
            except Exception as exc_inner:  # pragma: no cover - defensive
                logger.warning(
                    "_sanitize_model_label: token %s non traité (%s)", token, exc_inner
                )

        cleaned = " ".join(cleaned_tokens).strip()
        if not cleaned:
            logger.debug(
                "_sanitize_model_label: modèle vidé après nettoyage (entrée: %s)", value
            )
            return None
        return cleaned
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("_sanitize_model_label: échec de nettoyage (%s)", exc)
        return value


def _normalize_gender(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        v = value.strip().lower()
        female_markers = {"f", "femme", "female", "woman", "women", "girl"}
        male_markers = {"h", "homme", "male", "man", "men", "boy"}

        if v in female_markers or v.startswith("fem") or v.startswith("wom"):
            return "femme"
        if v in male_markers or v.startswith("hom") or v.startswith("masc") or v.startswith("men"):
            return "homme"
        return value.strip()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("_normalize_gender: impossible de normaliser (%s)", exc)
        return value.strip()


def _safe_join(parts: List[str]) -> str:
    """Joint les morceaux en filtrant les chaînes vides."""
    return " ".join(p for p in parts if p and p.strip())


def _normalize_garment_type(value: Optional[str]) -> Optional[str]:
    """Uniformise le type (pull / gilet / cardigan)."""
    if not value:
        return None
    try:
        low = value.strip().lower()
        if "gilet" in low or "cardi" in low:
            return "Gilet"
        return "Pull"
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("_normalize_garment_type: impossible de lire %s (%s)", value, exc)
        return None


def _normalize_colors(value: Optional[Any]) -> List[str]:
    """Nettoie une liste de couleurs en entrée (liste ou chaîne séparée par virgules)."""
    try:
        if value is None:
            return []
        colors: List[str] = []
        if isinstance(value, list):
            iterator = value
        else:
            iterator = str(value).replace("/", ",").split(",")

        for raw in iterator:
            color = str(raw).strip()
            if not color:
                continue
            colors.append(color)

        return colors
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("_normalize_colors: échec normalisation (%s)", exc)
        return []


def _format_colors_segment(value: Optional[Any]) -> Optional[str]:
    """Formate les couleurs en limitant le bruit et les doublons."""
    try:
        colors = _normalize_colors(value)
        simplified: List[str] = []
        seen = set()
        for color in colors:
            color_clean = color.strip()
            color_key = color_clean.lower()
            if not color_key:
                continue

            simplified_color = _simplify_color_name(color_key)
            if not simplified_color:
                continue

            if simplified_color in seen:
                continue
            seen.add(simplified_color)
            simplified.append(simplified_color)

        if not simplified:
            return None

        # Si "multicolore" est présent avec d'autres couleurs, on le supprime.
        if len(simplified) > 1:
            simplified = [c for c in simplified if c != "multicolore"] or simplified

        max_colors = 2
        limited = simplified[:max_colors]
        return ", ".join(limited)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("_format_colors_segment: échec (%s)", exc)
        return None


def _simplify_color_name(color: str) -> Optional[str]:
    """Réduit les couleurs à une palette simple (bleu sans qualificatifs, marine dédié)."""
    try:
        base = color.strip().lower()
        if not base:
            return None

        palettes = [
            ({"bleu marine", "navy", "navy blue", "marine"}, "marine"),
            (
                {
                    "bleu",
                    "blue",
                    "turquoise",
                    "petrole",
                    "pétrole",
                    "sarcelle",
                    "azure",
                    "azur",
                    "cyan",
                    "ciel",
                },
                "bleu",
            ),
            ({"noir", "black"}, "noir"),
            ({"blanc", "white", "ecru", "écru", "off-white", "ivory", "ivoire"}, "blanc"),
            ({"gris", "gray", "grey", "chiné", "chinee", "charcoal"}, "gris"),
            ({"rouge", "red", "bordeaux"}, "rouge"),
            ({"rose", "pink", "fuchsia"}, "rose"),
            ({"vert", "green", "kaki", "khaki", "olive"}, "vert"),
            ({"jaune", "yellow", "moutarde"}, "jaune"),
            ({"orange", "corail", "coral"}, "orange"),
            ({"beige", "sable", "sand", "taupe"}, "beige"),
            ({"marron", "brown", "chocolat", "chocolate"}, "marron"),
            ({"violet", "purple", "lilas", "lavande", "prune"}, "violet"),
        ]

        for keywords, label in palettes:
            if any(keyword in base for keyword in keywords):
                return label

        return base
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("_simplify_color_name: échec (%s)", exc)
        return None


def _format_material_segment(
    material: Optional[str],
    cotton_percent: Optional[Any],
    wool_percent: Optional[Any],
) -> Optional[str]:
    """Construit un segment matière lisible (coton/laine) sans inventer."""
    try:
        cotton_value: Optional[int] = None
        wool_value: Optional[int] = None

        try:
            cotton_value = int(cotton_percent) if cotton_percent is not None else None
        except (TypeError, ValueError):
            logger.debug("_format_material_segment: cotton illisible (%s)", cotton_percent)

        try:
            wool_value = int(wool_percent) if wool_percent is not None else None
        except (TypeError, ValueError):
            logger.debug("_format_material_segment: wool illisible (%s)", wool_percent)

        material_label = (material or "").strip().lower()
        priority_mapping = {
            "cachemire": "cachemire",
            "cashmere": "cachemire",
            "angora": "angora",
            "angora rabbit": "angora",
            "rabbit angora": "angora",
            "rabbit": "angora",
            "laine": "laine",
            "wool": "laine",
            "lin": "lin",
            "linen": "lin",
            "satin": "satin",
        }

        # --- Matières prioritaires (laine / cachemire / lin / satin) -----
        if wool_value is not None and wool_value > 0:
            return "laine"

        for keyword, label in priority_mapping.items():
            if keyword in material_label:
                return label

        # --- Coton (uniquement si >= 60%) --------------------------------
        if cotton_value is not None:
            if cotton_value >= 60:
                return f"{cotton_value}% coton"
            return "coton"

        if material_label:
            if "coton" in material_label or "cotton" in material_label:
                return "coton"

        return None
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("_format_material_segment: échec (%s)", exc)
        return None


def _format_neckline(neckline: Optional[str]) -> Optional[str]:
    """Nettoie le col pour éviter les doublons de 'col'."""
    if not neckline:
        return None
    try:
        neck = neckline.strip()
        neck_lower = neck.lower()
        if neck_lower.startswith("col"):
            neck = neck.split(" ", 1)[-1] if " " in neck else ""
        neck = neck.strip()
        if not neck:
            return None
        return f"col {neck}"
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("_format_neckline: échec (%s)", exc)
        return None


def _normalize_pull_size(value: Optional[str]) -> Optional[str]:
    """Uniformise les tailles sur l'échelle XXXXS -> XXXXXL."""
    if not value:
        return None
    try:
        raw = str(value).strip().upper()
        raw = raw.replace(" ", "")
        if "/" in raw:
            raw = raw.split("/")[0]
        if raw.endswith("P"):
            raw = raw[:-1]

        numeric_match = re.match(r"^(\d+)X$", raw)
        if numeric_match:
            count = int(numeric_match.group(1)) + 1
            return f"{'X' * count}L"

        if raw == "M":
            return "M"

        match = re.match(r"^(X{0,5})(S|L)$", raw)
        if match:
            prefix, base = match.groups()
            normalized = f"{prefix}{base}"
            return normalized if normalized else None

        allowed_sizes = {"XS", "S", "L", "XL", "XXL", "XXXL", "XXXXL", "XXXXXL", "XXXS", "XXXXS"}
        if raw in allowed_sizes:
            return raw

        return raw or None
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("_normalize_pull_size: échec (%s)", exc)
        return None


def _normalize_carhartt_size(value: Optional[str]) -> tuple[str, str]:
    """Normalise la taille Carhartt (base + token hashtag)."""

    try:
        raw = _normalize_str(value)
        if not raw:
            return "NC", "nc"

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

        token = base.lower().replace(" ", "") or "nc"
        logger.info(
            "_normalize_carhartt_size: taille brute '%s' -> base=%s, token=%s",
            raw,
            base,
            token,
        )
        return base, token
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("_normalize_carhartt_size: normalisation impossible (%s)", exc)
        return "NC", "nc"


def _sanitize_carhartt_size_for_title(raw_size: Optional[str]) -> Optional[str]:
    """Retire les fragments de SKU (JCR) qui polluent la taille affichée."""
    try:
        cleaned = _normalize_str(raw_size)
        if not cleaned:
            return None
        sanitized = re.sub(r"\bjcr\s*\d+\b", "", cleaned, flags=re.IGNORECASE)
        sanitized = re.sub(r"\s{2,}", " ", sanitized).strip(" ,-/")
        logger.debug(
            "_sanitize_carhartt_size_for_title: taille brute '%s' -> '%s'",
            raw_size,
            sanitized,
        )
        return sanitized or None
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("_sanitize_carhartt_size_for_title: nettoyage taille impossible (%s)", exc)
        return _normalize_str(raw_size)


def _classify_rise_from_cm(rise_cm: Optional[float]) -> Optional[str]:
    """
    Classe la taille (rise) à partir de la distance entre entrejambe
    et haut de ceinture face avant, en cm.

    On ne garde ces infos QUE pour décider de 'taille basse' dans le titre :
      - ultra_low  : < 20 cm
      - low        : 20–23 cm
      - mid        : 23–26 cm
      - high       : >= 26 cm
    """
    if rise_cm is None:
        return None
    try:
        v = float(rise_cm)
    except (TypeError, ValueError):
        return None

    if v < 20:
        return "ultra_low"
    if 20 <= v < 23:
        return "low"
    if 23 <= v < 26:
        return "mid"
    return "high"


def _is_low_rise_label(raw: Optional[str]) -> bool:
    """
    Détermine si un libellé de taille correspond à de la taille basse.

    On accepte différents formats ("low", "taille basse", "ultra_low"...).
    """
    try:
        if not raw:
            return False
        normalized = str(raw).strip().lower()
        return "low" in normalized or "basse" in normalized or "ultra" in normalized
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("_is_low_rise_label: impossible de déterminer la taille basse (%s)", exc)
        return False


def build_jean_levis_title(features: Dict[str, Any]) -> str:
    """
    Construit un titre de jean Levi's en appliquant les règles métier :

    Jean + marque + modèle (si dispo) + FR + W +
    coupe (+ 'taille basse' uniquement si low/ultra_low) +
    % coton (si >= 60) + 'stretch' (si elast >= 2%) +
    genre + couleur + - SKU

    IMPORTANT : on NE MET PLUS la longueur de jambe (Lxx) dans le titre.
    On n'invente JAMAIS :
    - si une info n'est pas fournie dans 'features', on l'ignore.
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
                    marker in raw_model_low
                    for marker in ("boot", "flare", "évas", "evase", "curve", "curvy")
                ):
                    logger.debug(
                        "build_jean_levis_title: fit ajusté en Bootcut/Évasé depuis modèle %s",
                        raw_model,
                    )
                    fit = "Bootcut/Évasé"
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("build_jean_levis_title: ajustement fit impossible (%s)", exc)
        color = _normalize_str(features.get("color"))
        gender = _normalize_gender(_normalize_str(features.get("gender")))
        sku = _normalize_str(features.get("sku"))

        # % coton / élasthanne
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

        # Rise : soit déjà fourni comme type, soit calculé depuis rise_cm
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
                logger.warning("build_jean_levis_title: rise_type illisible (%s)", exc)

        low_rise = _is_low_rise_label(rise_type)
        if not low_rise:
            try:
                rise_cm_value = features.get("rise_cm")
                low_rise = _is_low_rise_label(_classify_rise_from_cm(rise_cm_value))
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("build_jean_levis_title: détection taille basse impossible (%s)", exc)

        # Normalisation d'affichage de la taille US :
        size_us_display: Optional[str] = None
        if size_us_raw:
            s = size_us_raw.strip().upper()
            size_us_display = s if s.startswith("W") else f"W{s}"

        size_segments: List[str] = []
        if size_fr:
            size_segments.append(f"FR{size_fr}")
        if size_us_display:
            size_segments.append(size_us_display)
        size_value = " ".join(size_segments)

        fit_segment = None
        if fit and low_rise:
            fit_segment = f"coupe {fit} taille basse"
        elif fit:
            fit_segment = f"coupe {fit}"
        elif low_rise:
            fit_segment = "taille basse"

        colors = _normalize_colors(color)
        color_primary = colors[0] if colors else None
        color_secondary = colors[1] if len(colors) > 1 else None

        material_candidates: List[str] = []
        cotton_label = f"{cotton_percent}% coton" if cotton_percent is not None else None
        if cotton_label:
            material_candidates.append(cotton_label)
        try:
            formatted_material = _format_material_segment(
                features.get("material"), cotton_percent, features.get("wool_percent")
            )
            if formatted_material:
                material_candidates.append(formatted_material)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("build_jean_levis_title: matière non exploitable (%s)", exc)

        blocks: List[TitleBlock] = [
            TitleBlock(kind="category", value="Jean", critical=True, capitalize=False),
        ]

        if brand:
            brand_formatted = " ".join(word.capitalize() for word in brand.lower().split())
            blocks.append(
                TitleBlock(kind="brand", value=brand_formatted, critical=True, capitalize=False)
            )

        if model:
            blocks.append(TitleBlock(kind="model", value=model, trim_priority=1, capitalize=False))

        if size_value:
            blocks.append(
                TitleBlock(
                    kind="size",
                    value=size_value,
                    trim_priority=1,
                    capitalize=False,
                    critical=True,
                )
            )

        if fit_segment:
            blocks.append(TitleBlock(kind="fit", value=fit_segment, trim_priority=2))

        if elas_percent is not None and elas_percent >= 2:
            blocks.append(TitleBlock(kind="stretch", value="stretch", trim_priority=2))

        material_block = build_material_block(material_candidates)
        if material_block:
            material_block.trim_priority = 1
            blocks.append(material_block)

        if color_primary:
            blocks.append(TitleBlock(kind="color_primary", value=color_primary, trim_priority=1))
        if color_secondary:
            blocks.append(TitleBlock(kind="color_secondary", value=color_secondary, trim_priority=3))

        if gender:
            blocks.append(TitleBlock(kind="gender", value=gender, trim_priority=1))

        if sku:
            blocks.append(TitleBlock(kind="sku", value=f"{SKU_PREFIX}{sku}", trim_priority=0))

        title = render_title(blocks, JeanSpec(), TitleRules())
        logger.debug("Titre jean Levi's construit à partir de %s -> '%s'", features, title)
        return title
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("build_jean_levis_title: échec de construction (%s)", exc)
        parts: List[str] = []
        try:
            if features.get("brand"):
                parts.append(str(features.get("brand")))
            if features.get("model"):
                parts.append(str(features.get("model")))
        except Exception:
            pass
        return _safe_join(["Jean", *parts]).strip()


def build_pull_tommy_title(features: Dict[str, Any]) -> str:
    """Construit un titre pour les pulls/gilets Tommy Hilfiger."""
    try:
        brand = _normalize_str(features.get("brand"))

        garment_type = _normalize_garment_type(features.get("garment_type")) or "Pull"
        raw_gender = _normalize_gender(_normalize_str(features.get("gender")))
        gender = "femme"
        if raw_gender and raw_gender.lower() != "femme":
            logger.debug(
                "build_pull_tommy_title: genre forcé à femme (entrée=%s)", raw_gender
            )
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
        if not brand:
            brand = "Tommy Hilfiger"

        blocks: List[TitleBlock] = [
            TitleBlock(kind="category", value=garment_type, critical=True, capitalize=False),
            TitleBlock(
                kind="brand",
                value=" ".join(word.capitalize() for word in brand.lower().split()),
                critical=True,
                capitalize=False,
            ),
        ]

        if features.get("is_pima") and brand.lower() == "tommy hilfiger":
            blocks.append(TitleBlock(kind="premium", value="Premium", trim_priority=1))
            logger.info("build_pull_tommy_title: ajout de 'Premium' au titre (Pima cotton détecté)")

        if pattern:
            blocks.append(TitleBlock(kind="pattern", value=pattern, trim_priority=2))

        if size:
            blocks.append(
                TitleBlock(
                    kind="size",
                    value=f"taille {size}",
                    trim_priority=1,
                    critical=True,
                    capitalize=False,
                )
            )

        color_values = _normalize_colors(colors_segment or colors_input)
        if color_values:
            blocks.append(TitleBlock(kind="color_primary", value=color_values[0], trim_priority=1))
        if len(color_values) > 1:
            blocks.append(
                TitleBlock(kind="color_secondary", value=color_values[1], trim_priority=3)
            )

        material_block = build_material_block([material] if material else [])
        if material_block:
            material_block.trim_priority = 1
            blocks.append(material_block)

        if neckline:
            blocks.append(TitleBlock(kind="neckline", value=neckline, trim_priority=2))

        if gender:
            blocks.append(TitleBlock(kind="gender", value=gender, trim_priority=1))

        specificity = _normalize_str(features.get("specificity"))
        if specificity:
            blocks.append(TitleBlock(kind="specificity", value=specificity, trim_priority=2))

        if sku and sku_status and sku_status.lower() == "ok":
            blocks.append(TitleBlock(kind="sku", value=f"{SKU_PREFIX}{sku}", trim_priority=0))
        elif sku:
            logger.debug(
                "build_pull_tommy_title: SKU ignoré car statut non 'ok' (%s)",
                sku_status,
            )
        else:
            logger.debug(
                "build_pull_tommy_title: SKU absent ou illisible (statut=%s)", sku_status
            )

        title = render_title(blocks, PullGiletSpec(), TitleRules())
        logger.debug("Titre pull Tommy construit à partir de %s -> '%s'", features, title)
        return title
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("build_pull_tommy_title: échec de construction (%s)", exc)
        return _safe_join(["Pull Tommy Hilfiger"])


def build_jacket_carhart_title(features: Dict[str, Any]) -> str:
    """Construit un titre pour une veste Carhartt conformément aux règles métier."""
    try:
        brand = _normalize_str(features.get("brand")) or "Carhartt"
        model = _normalize_str(features.get("model"))
        raw_size = _sanitize_carhartt_size_for_title(features.get("size"))
        size, size_token = _normalize_carhartt_size(raw_size)
        color = _normalize_str(features.get("color"))
        gender = _normalize_str(features.get("gender")) or "homme"
        has_hood = features.get("has_hood")
        is_camouflage = features.get("is_camouflage")
        is_realtree = features.get("is_realtree")
        is_new_york = features.get("is_new_york")
        pattern = _normalize_str(features.get("pattern"))

        # --- SKU (Carhartt) -------------------------------------------------
        sku = _normalize_str(features.get("sku"))
        sku_status = _normalize_str(features.get("sku_status"))

        category_value = "Jacket à capuche" if has_hood else "Jacket"
        blocks: List[TitleBlock] = [
            TitleBlock(kind="category", value=category_value, critical=True, capitalize=False)
        ]

        brand_value = brand if brand and brand.lower() != "carhartt" else "Carhartt"
        blocks.append(
            TitleBlock(
                kind="brand",
                value=brand_value,
                critical=True,
                capitalize=False,
            )
        )

        style_value = None
        if model:
            model_clean = model.strip()
            model_lower = model_clean.lower()
            normalized_style = model_lower.replace("jacket", "").replace("veste", "").strip()
            if normalized_style in {"detroit", "détroit"}:
                normalized_style = "Detroit"
            style_value = normalized_style or model_clean
            if is_new_york or "new york" in model_lower or model_lower.endswith(" ny"):
                style_value = f"{style_value} NY".strip()
        elif is_new_york:
            style_value = "NY"

        if style_value:
            blocks.append(TitleBlock(kind="style", value=style_value, trim_priority=1, capitalize=True))

        size_label = f"taille {size}" if size else "taille NC"
        blocks.append(
            TitleBlock(
                kind="size",
                value=size_label,
                trim_priority=1,
                critical=True,
                capitalize=False,
            )
        )

        specificities: List[str] = []
        if pattern and pattern.lower() == "camouflage":
            is_camouflage = True

        if has_hood:
            logger.debug("build_jacket_carhart_title: capuche déjà portée par la catégorie")

        collar = _normalize_str(features.get("collar"))
        if collar:
            specificities.append(collar)

        lining = _normalize_str(features.get("lining"))
        if lining:
            specificities.append(lining)

        closure = _normalize_str(features.get("closure"))
        if closure:
            specificities.append(closure)

        if is_realtree:
            specificities.append("Realtree")
        elif is_camouflage:
            specificities.append("camouflage")

        if specificities:
            ordered_specificities = []
            for label in specificities:
                low = label.lower()
                if "col" in low:
                    ordered_specificities.insert(0, label)
                elif "doublure" in low or "lining" in low:
                    ordered_specificities.append(label)
                elif "zip" in low or "fermeture" in low:
                    ordered_specificities.append(label)
                else:
                    ordered_specificities.append(label)
            blocks.append(
                TitleBlock(
                    kind="specificities",
                    value=" ".join(ordered_specificities),
                    trim_priority=2,
                )
            )

        material_block = build_material_block(
            [features.get("exterior"), features.get("material"), features.get("lining")]
        )
        if material_block:
            material_block.trim_priority = 1
            blocks.append(material_block)

        color_values = _normalize_colors(color)
        if color_values:
            blocks.append(TitleBlock(kind="color_primary", value=color_values[0], trim_priority=1))
        if len(color_values) > 1:
            blocks.append(TitleBlock(kind="color_secondary", value=color_values[1], trim_priority=3))

        if gender:
            blocks.append(TitleBlock(kind="gender", value=gender, trim_priority=1))

        if sku and sku_status and sku_status.lower() == "ok":
            blocks.append(TitleBlock(kind="sku", value=f"{SKU_PREFIX}{sku}", trim_priority=0))
        elif sku:
            logger.debug(
                "build_jacket_carhart_title: SKU ignoré car statut non 'ok' (%s)",
                sku_status,
            )
        else:
            logger.debug(
                "build_jacket_carhart_title: SKU absent ou illisible (statut=%s)",
                sku_status,
            )

        title = render_title(blocks, JacketSpec(), TitleRules())
        logger.debug(
            "build_jacket_carhart_title: titre construit depuis %s -> '%s'",
            features,
            title,
        )
        return title
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("build_jacket_carhart_title: échec de construction (%s)", exc)
        return _safe_join(["Jacket Carhartt"])
