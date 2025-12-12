# domain/title_builder.py

from __future__ import annotations

from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


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

        cleaned_tokens: List[str] = []
        for token in raw.replace("/", " ").replace("-", " ").split():
            token_low = token.lower()
            if any(marker in token_low for marker in fit_markers):
                logger.debug("_sanitize_model_label: token coupe ignoré: %s", token)
                continue
            cleaned_tokens.append(token)

        cleaned = " ".join(cleaned_tokens).strip()
        return cleaned or raw
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("_sanitize_model_label: échec de nettoyage (%s)", exc)
        return value


def _normalize_gender(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    v = value.strip().lower()
    if v.startswith("f"):
        return "femme"
    if v.startswith("h"):
        return "homme"
    return value.strip()


def _safe_join(parts: List[str]) -> str:
    """Joint les morceaux en filtrant les chaînes vides."""
    return " ".join(p for p in parts if p and p.strip())


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

    # --- lecture + normalisation des champs attendus ---

    brand = _normalize_str(features.get("brand"))
    raw_model = _normalize_str(features.get("model"))
    model = _sanitize_model_label(raw_model)
    size_fr = _normalize_str(features.get("size_fr"))
    size_us_raw = _normalize_str(features.get("size_us"))
    length = _normalize_str(features.get("length"))  # conservé pour usage éventuel hors titre
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

    # Normalisation d'affichage de la taille US :
    # - si déjà au format "W28", on garde tel quel
    # - sinon, on préfixe avec "W"
    size_us_display: Optional[str] = None
    if size_us_raw:
        s = size_us_raw.strip().upper()
        if s.startswith("W"):
            size_us_display = s
        else:
            size_us_display = f"W{s}"

    # --- construction du titre ---

    parts: List[str] = []

    # Type de vêtement
    parts.append("Jean")

    # Marque
    if brand:
        parts.append(brand)

    # Modèle
    if model:
        parts.append(model)

    # Taille FR / US (sans longueur L dans le titre)
    if size_fr:
        parts.append(f"FR{size_fr}")
    if size_us_display:
        parts.append(size_us_display)

    # Coupe + éventuelle 'taille basse'
    low_rise = rise_type in ("low", "ultra_low")
    if fit and low_rise:
        parts.append(f"coupe {fit} taille basse")
    elif fit:
        parts.append(f"coupe {fit}")
    elif low_rise:
        parts.append("taille basse")

    # % coton si >= 60
    if cotton_percent is not None and cotton_percent >= 60:
        parts.append(f"{cotton_percent}% coton")

    # Stretch si élasthanne >= 2%
    if elas_percent is not None and elas_percent >= 2:
        parts.append("stretch")

    # Genre (homme / femme)
    if gender:
        parts.append(gender)

    # Couleur
    if color:
        parts.append(color)

    # SKU (avec tiret)
    if sku:
        parts.append(f"- {sku}")

    title = _safe_join(parts)

    logger.debug("Titre jean Levi's construit à partir de %s -> '%s'", features, title)
    return title
