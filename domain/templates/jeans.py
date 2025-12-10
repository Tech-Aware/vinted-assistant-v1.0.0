# domain/templates/jeans.py

from __future__ import annotations

import logging
from typing import Dict
from copy import deepcopy

from .base import (
    AnalysisProfile,
    AnalysisProfileName,
    BASE_LISTING_SCHEMA,
)

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------
# Schéma spécialisé pour les jeans
# On part du schéma de base, mais on ajoute:
# - sku (str)
# - sku_status (ok / missing / low_confidence)
# --------------------------------------------------------------------

JEAN_LISTING_SCHEMA = deepcopy(BASE_LISTING_SCHEMA)

# Ajout des champs JEAN spécifiques
JEAN_LISTING_SCHEMA["properties"].update(
    {
        "sku": {
            "type": "string",
            "description": "Numéro interne lu depuis la photo SKU. Exemple: JLF87."
        },
        "sku_status": {
            "type": "string",
            "description": "Statut d'extraction SKU: ok, missing, low_confidence.",
            "enum": ["ok", "missing", "low_confidence"]
        },
        "model": {
            "type": "string",
            "description": "Modèle Levi's si visible (501, 505, 511, etc.)."
        },
        "fit": {
            "type": "string",
            "description": "Coupe: skinny, slim, straight/droit, bootcut/évasé, etc."
        },
        "length": {
            "type": "string",
            "description": "Longueur lisible sur l’étiquette (ex: L34)."
        },
        "cotton_percent": {
            "type": "number",
            "description": "% coton si visible sur l’étiquette de composition."
        },
        "elasthane_percent": {
            "type": "number",
            "description": "% élasthanne si > 2%, sinon ne pas inventer."
        },
        "gender": {
            "type": "string",
            "description": "Genre détecté: homme, femme, ou incertain.",
        },
        "color": {
            "type": "string",
            "description": "Couleur dominante détectée: noir, bleu brut, etc."
        },
    }
)

# NOTA:
# - On NE modifie PAS les 'required' ici.
#   La logique business est gérée plus tard dans normalize_and_postprocess
#   et le title builder.
#
# - On NE force PAS sku à être required.
#   Car il peut manquer (photo absente, illisible, etc.).


# --------------------------------------------------------------------
# Profil d'analyse pour un jean Levi's
# --------------------------------------------------------------------

JEANS_PROFILES: Dict[AnalysisProfileName, AnalysisProfile] = {
    AnalysisProfileName.JEAN_LEVIS: AnalysisProfile(
        name=AnalysisProfileName.JEAN_LEVIS,
        json_schema=JEAN_LISTING_SCHEMA,
        prompt_suffix=r"""
PROFILE TYPE: JEAN LEVI'S

You are analyzing multiple photos of a single Levi's denim jean.

IMPORTANT RULES (MUST FOLLOW):

1) SKU (INTERNAL CODE):
   - Look for a small paper/card/label placed in front of the garment.
   - The SKU looks like: JLF87, JLK21, etc.
   - Extract it as-is, without interpretation or modification.
   - If SKU is clearly readable:
       sku = "JLF87", sku_status = "ok"
   - If SKU appears uncertain (blur, missing digit, "?"):
       sku = extracted value, sku_status = "low_confidence"
   - If no SKU card is visible on any photo:
       sku = null, sku_status = "missing"
   - Never invent a SKU.

2) BRAND & MODEL:
   - Detect brand ONLY from visible labels:
     - back pocket red tab (Levi’s),
     - back waist patch,
     - internal labels.
   - If clearly visible: brand = "Levi’s".
   - Model if visible: 501, 505, 511, etc.
   - Never invent a model. If no model is visible: model = null.

3) FIT (CUT):
   - If visible on label: use that label (slim, straight, bootcut, etc.)
   - If visible from full-body silhouette: use it.
   - Common mapping:
     - slim => skinny
     - straight => straight/droits
     - bootcut => bootcut/évasé
   - If unclear: fit = null.

4) LENGTH:
   - Only if clearly visible from label (L32, L34, etc.).
   - If no label => length = null.

5) MATERIAL:
   - Read cotton and elasthane % ONLY from composition label.
   - If cotton ≥ 60%: report percent.
   - If elasthane ≥ 2%: report percent.
   - Otherwise: null.

6) GENDER:
   - If obvious: homme or femme.
   - If uncertain: null.

7) COLOR:
   - Dominant visible color: bleu brut, noir, etc.

8) NO INVENTION RULE:
   - If information is not clearly visible → field = null.
   - Do not guess sizes or data.

OUTPUT FORMAT:
- Respond ONLY in pure JSON with all keys defined in the schema.
- No text outside JSON.
- No commentary.
""",
    ),
}

logger.debug(
    "Profil JEAN_LEVIS chargé avec schéma %s",
    list(JEAN_LISTING_SCHEMA["properties"].keys()),
)
