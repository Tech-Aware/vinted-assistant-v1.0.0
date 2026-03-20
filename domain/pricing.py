# domain/pricing.py

"""
Module de calcul des prix conseillés pour les jeans Levi's.

Barème basé sur :
  - Genre (femme / homme)
  - Gamme (Premium / Standard)
  - Coupe (Skinny / Droit / Évasé)
  - Taille
  - État (avec ou sans défauts)
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Modèles premium
# ---------------------------------------------------------------------------
PREMIUM_MODELS = {"501", "505", "550", "ribcage"}
PREMIUM_MODEL_NUMBERS = {"501", "505", "550"}

# Sub-brands budget
BUDGET_BRANDS = {"denizen", "signature"}


def _is_premium_model(model: Optional[str]) -> bool:
    if not model:
        return False
    low = model.lower().strip()
    for p in PREMIUM_MODELS:
        if p in low:
            return True
    match = re.search(r'\b(\d{3})\b', low)
    if match and match.group(1) in PREMIUM_MODEL_NUMBERS:
        return True
    return False


def _is_budget_brand(brand: Optional[str], model: Optional[str]) -> bool:
    combined = f"{(brand or '')} {(model or '')}".lower()
    return any(b in combined for b in BUDGET_BRANDS)


def _has_defects(defects: Optional[str]) -> bool:
    if not defects:
        return False
    low = defects.lower().strip()
    if not low:
        return False
    if any(t in low for t in ("aucun", "sans défaut", "parfait état", "neuf", "comme neuf")):
        return False
    defect_terms = [
        "tâche", "tache", "usure", "déchirure", "trou", "accroc",
        "décoloration", "jaunissement", "peluche", "bouloché",
        "défaut", "marque", "trace", "usé", "abîmé", "endommagé",
        "stain", "worn", "damaged", "hole", "tear",
    ]
    return any(t in low for t in defect_terms)


def _normalize_fit_for_pricing(fit: Optional[str]) -> str:
    """Renvoie 'skinny', 'droit' ou 'évasé'."""
    if not fit:
        return "droit"
    low = fit.lower().strip()
    if "skinny" in low or "slim" in low:
        return "skinny"
    if any(m in low for m in ("évasé", "evase", "bootcut", "boot cut", "flare", "wide", "baggy", "loose", "relaxed", "barrel", "curve", "curvy")):
        return "évasé"
    return "droit"


def _parse_size_numeric(size_raw: Optional[str]) -> Optional[int]:
    """Extrait la valeur numérique d'une taille (FR ou US)."""
    if not size_raw:
        return None
    try:
        digits = re.sub(r'[^0-9]', '', str(size_raw))
        return int(digits) if digits else None
    except (ValueError, TypeError):
        return None


# =====================================================================
# BARÈME FEMME  (tailles FR)
# =====================================================================

def _price_femme(
    is_premium: bool,
    is_budget: bool,
    fit: str,
    size_num: Optional[int],
    has_defects: bool,
) -> Tuple[float, str]:
    """Retourne (prix, retail_range) pour un jean femme."""

    # --- Premium ---
    if is_premium:
        if fit == "évasé":
            retail = "130–140 €"
            if size_num and size_num >= 42:
                return (34.0 if has_defects else 40.0), retail
            else:
                return (32.0 if has_defects else 38.0), retail
        elif fit == "droit":
            retail = "120–130 €"
            return (32.0 if has_defects else 38.0), retail
        else:  # skinny
            retail = "110–120 €"
            return (28.0 if has_defects else 34.0), retail

    # --- Budget (Denizen / Signature) ---
    if is_budget:
        if size_num and size_num >= 42:
            retail = "40–50 €"
            return (22.0 if has_defects else 28.0), retail
        else:
            retail = "24–40 €"
            return (20.0 if has_defects else 24.0), retail

    # --- Standard ---
    if fit == "évasé":
        retail = "110–130 €"
        if size_num and size_num >= 42:
            return (30.0 if has_defects else 36.0), retail
        else:
            return (28.0 if has_defects else 34.0), retail
    elif fit == "skinny":
        retail = "99–110 €"
        return (20.0 if has_defects else 24.0), retail
    else:  # droit
        retail = "99–120 €"
        return (22.0 if has_defects else 28.0), retail


# =====================================================================
# BARÈME HOMME  (tailles US W)
# =====================================================================

def _price_homme(
    is_premium: bool,
    is_budget: bool,
    fit: str,
    size_num: Optional[int],
    has_defects: bool,
) -> Tuple[float, str]:
    """Retourne (prix, retail_range) pour un jean homme."""

    # --- Premium ---
    if is_premium:
        if fit == "évasé":
            retail = "120–150 €"
            if size_num and size_num >= 38:
                return (44.0 if has_defects else 50.0), retail
            else:
                return (42.0 if has_defects else 48.0), retail
        elif fit == "droit":
            retail = "110–130 €"
            return (38.0 if has_defects else 44.0), retail
        else:  # skinny
            retail = "110–120 €"
            return (34.0 if has_defects else 40.0), retail

    # --- Budget (Denizen / Signature) ---
    if is_budget:
        if size_num and size_num >= 38:
            retail = "24–27 €"
            return (24.0 if has_defects else 28.0), retail
        else:
            retail = "24–27 €"
            return (22.0 if has_defects else 26.0), retail

    # --- Standard ---
    if fit == "évasé":
        retail = "110–120 €"
        if size_num and size_num >= 38:
            return (40.0 if has_defects else 46.0), retail
        else:
            return (36.0 if has_defects else 42.0), retail
    elif fit == "skinny":
        retail = "99–110 €"
        return (22.0 if has_defects else 26.0), retail
    else:  # droit
        retail = "99–110 €"
        return (26.0 if has_defects else 32.0), retail


# =====================================================================
# API publique
# =====================================================================

def calculate_recommended_price_jean_levis(
    features: Dict[str, Any],
    defects: Optional[str] = None,
) -> Tuple[Optional[float], str]:
    """
    Calcule le prix conseillé pour un jean Levi's selon le barème.

    Returns:
        Tuple (prix_conseillé, explication)
    """
    try:
        gender = (features.get("gender") or "").lower().strip()
        model = features.get("model") or ""
        brand = features.get("brand") or ""
        feature_defects = features.get("defects") or defects or ""
        fit_raw = features.get("fit") or ""

        is_premium = _is_premium_model(model)
        is_budget = _is_budget_brand(brand, model)
        has_def = _has_defects(feature_defects)
        fit = _normalize_fit_for_pricing(fit_raw)

        if gender == "homme":
            size_num = _parse_size_numeric(features.get("size_us"))
            price, retail = _price_homme(is_premium, is_budget, fit, size_num, has_def)
            gender_label = "homme"
        else:
            size_num = _parse_size_numeric(features.get("size_fr"))
            price, retail = _price_femme(is_premium, is_budget, fit, size_num, has_def)
            gender_label = "femme"

        gamme = "premium" if is_premium else ("budget" if is_budget else "standard")
        explanation = (
            f"Genre: {gender_label} | Gamme: {gamme} | "
            f"Coupe: {fit} | Taille: {size_num or 'NC'} | "
            f"Défauts: {'oui' if has_def else 'non'} | "
            f"Modèle: {model or 'NC'} | Prix neuf: {retail}"
        )

        logger.info("calculate_recommended_price_jean_levis: prix=%.1f€ (%s)", price, explanation)
        return price, explanation

    except Exception as exc:
        logger.exception("calculate_recommended_price_jean_levis: erreur %s", exc)
        return None, "Erreur de calcul"


def get_retail_price_range(features: Dict[str, Any]) -> Optional[str]:
    """
    Retourne la fourchette de prix neuf en magasin (ex: '130–140 €').
    """
    try:
        gender = (features.get("gender") or "").lower().strip()
        model = features.get("model") or ""
        brand = features.get("brand") or ""
        fit_raw = features.get("fit") or ""

        is_premium = _is_premium_model(model)
        is_budget = _is_budget_brand(brand, model)
        fit = _normalize_fit_for_pricing(fit_raw)

        if gender == "homme":
            size_num = _parse_size_numeric(features.get("size_us"))
            _, retail = _price_homme(is_premium, is_budget, fit, size_num, False)
        else:
            size_num = _parse_size_numeric(features.get("size_fr"))
            _, retail = _price_femme(is_premium, is_budget, fit, size_num, False)

        return retail
    except Exception as exc:
        logger.exception("get_retail_price_range: erreur %s", exc)
        return None
