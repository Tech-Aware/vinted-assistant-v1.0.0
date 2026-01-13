# domain/pricing.py

"""
Module de calcul des prix conseillés pour les articles.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Modèles Levi's considérés comme "premium" (classiques, iconiques)
PREMIUM_LEVIS_MODELS = {
    "501", "505", "517", "550", "560", "569",
    "vintage", "big e", "orange tab", "red tab",
    "made in usa", "selvedge", "lvc", "levis vintage clothing",
}

# Prix d'achat moyens
LEVIS_PURCHASE_PRICE_HOMME = 9.0
LEVIS_PURCHASE_PRICE_FEMME = 7.0


def _is_premium_model(model: Optional[str]) -> bool:
    """
    Détermine si un modèle Levi's est considéré comme premium.

    Args:
        model: Le nom/numéro du modèle (ex: "501", "505 Regular")

    Returns:
        True si le modèle est premium, False sinon
    """
    if not model:
        return False

    model_lower = model.lower().strip()

    # Vérifier si le modèle contient un des indicateurs premium
    for premium in PREMIUM_LEVIS_MODELS:
        if premium in model_lower:
            return True

    # Vérifier si c'est un numéro de modèle premium (501, 505, etc.)
    import re
    match = re.search(r'\b(\d{3})\b', model_lower)
    if match:
        model_number = match.group(1)
        if model_number in PREMIUM_LEVIS_MODELS:
            return True

    return False


def _has_defects(defects: Optional[str]) -> bool:
    """
    Détermine si l'article a des défauts significatifs.

    Args:
        defects: Description des défauts

    Returns:
        True si des défauts sont présents, False sinon
    """
    if not defects:
        return False

    defects_lower = defects.lower().strip()

    # Si vide ou mention explicite "aucun défaut"
    if not defects_lower:
        return False

    if any(term in defects_lower for term in ["aucun", "sans défaut", "parfait état", "neuf", "comme neuf"]):
        return False

    # Termes indiquant des défauts
    defect_terms = [
        "tâche", "tache", "usure", "déchirure", "trou", "accroc",
        "décoloration", "jaunissement", "peluche", "bouloché",
        "défaut", "marque", "trace", "usé", "abîmé", "endommagé",
        "stain", "worn", "damaged", "hole", "tear"
    ]

    return any(term in defects_lower for term in defect_terms)


def calculate_recommended_price_jean_levis(
    features: Dict[str, Any],
    defects: Optional[str] = None,
) -> Tuple[Optional[float], str]:
    """
    Calcule le prix conseillé pour un jean Levi's.

    Critères:
    - Jean Levi's homme: prix d'achat moyen 9€
    - Jean Levi's femme: prix d'achat moyen 7€

    Multiplicateurs:
    - Premium sans défaut: x4
    - Premium avec défaut: x3.5
    - Non premium sans défaut: x3.5
    - Non premium avec défaut: x2.5

    Args:
        features: Dictionnaire des caractéristiques du jean
        defects: Description des défauts (optionnel)

    Returns:
        Tuple (prix_conseillé, explication)
    """
    try:
        gender = (features.get("gender") or "").lower().strip()
        model = features.get("model") or ""
        feature_defects = features.get("defects") or defects or ""

        # Déterminer le prix d'achat selon le genre
        if gender == "homme":
            base_price = LEVIS_PURCHASE_PRICE_HOMME
            gender_label = "homme"
        elif gender == "femme":
            base_price = LEVIS_PURCHASE_PRICE_FEMME
            gender_label = "femme"
        else:
            # Par défaut, on prend le prix femme (plus conservateur)
            base_price = LEVIS_PURCHASE_PRICE_FEMME
            gender_label = "non précisé"

        # Déterminer si premium et si défauts
        is_premium = _is_premium_model(model)
        has_defects_flag = _has_defects(feature_defects)

        # Calculer le multiplicateur
        if is_premium and not has_defects_flag:
            multiplier = 4.0
            quality_label = "premium sans défaut"
        elif is_premium and has_defects_flag:
            multiplier = 3
            quality_label = "premium avec défaut"
        elif not is_premium and not has_defects_flag:
            multiplier = 3.5
            quality_label = "non premium sans défaut"
        else:  # non premium avec défaut
            multiplier = 2.5
            quality_label = "non premium avec défaut"

        # Calculer le prix conseillé
        recommended_price = base_price * multiplier

        # Construire l'explication
        explanation = (
            f"Genre: {gender_label} (base {base_price}€) | "
            f"Qualité: {quality_label} (x{multiplier}) | "
            f"Modèle: {model or 'NC'}"
        )

        logger.info(
            "calculate_recommended_price_jean_levis: prix=%.1f€ (%s)",
            recommended_price,
            explanation,
        )

        return recommended_price, explanation

    except Exception as exc:
        logger.exception("calculate_recommended_price_jean_levis: erreur %s", exc)
        return None, "Erreur de calcul"
