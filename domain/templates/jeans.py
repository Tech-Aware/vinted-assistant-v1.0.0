# domain/templates/jeans.py

from __future__ import annotations

import logging
from typing import Dict
from copy import deepcopy

from .base import (
    AnalysisProfile,
    AnalysisProfileName,
    BASE_LISTING_SCHEMA,
    AI_ENVELOPE_SCHEMA
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
        # L'enveloppe IA est au niveau racine, pas dans features
        "ai": AI_ENVELOPE_SCHEMA,

        # Les champs spécifiques jeans vont dans features
        "features": {
            "type": "object",
            "properties": {
                "brand": {"type": ["string", "null"]},
                "model": {"type": ["string", "null"]},
                "fit": {"type": ["string", "null"]},
                "color": {"type": ["string", "null"]},
                "size_fr": {"type": ["string", "null"]},
                "size_us": {"type": ["string", "null"]},
                "length": {"type": ["string", "null"]},
                "cotton_percent": {"type": ["number", "null"]},
                "elasthane_percent": {"type": ["number", "null"]},
                "rise_type": {"type": ["string", "null"]},
                "rise_cm": {"type": ["number", "null"]},
                "gender": {"type": ["string", "null"]},
                "sku": {"type": ["string", "null"]},
                "sku_status": {
                    "type": ["string", "null"],
                    "enum": ["ok", "missing", "low_confidence", None],
                    "description": "Statut d'extraction SKU.",
                },
            },
            "required": [
                "brand",
                "model",
                "fit",
                "color",
                "size_fr",
                "size_us",
                "length",
                "cotton_percent",
                "elasthane_percent",
                "rise_type",
                "rise_cm",
                "gender",
                "sku",
                "sku_status",
            ],
            "additionalProperties": False,
        },
    }
)
required = set(JEAN_LISTING_SCHEMA.get("required", []))
required.update({"ai", "features"})
JEAN_LISTING_SCHEMA["required"] = list(required)

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
