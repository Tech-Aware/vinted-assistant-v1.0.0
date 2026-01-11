# domain/templates/pulls.py

from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any, Dict

from .base import AnalysisProfile, AnalysisProfileName, BASE_LISTING_SCHEMA, AI_ENVELOPE_SCHEMA

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------
# Schéma spécialisé pour les pulls
# - On part du schéma de base
# - On garantit la présence de:
#   - ai (enveloppe IA standardisée)
#   - features (objet, même vide pour ce profil)
# --------------------------------------------------------------------

PULL_LISTING_SCHEMA: Dict[str, Any] = deepcopy(BASE_LISTING_SCHEMA)

# 1) Garantir que "ai" est bien une propriété top-level et conforme
PULL_LISTING_SCHEMA.setdefault("properties", {})
PULL_LISTING_SCHEMA["properties"]["ai"] = AI_ENVELOPE_SCHEMA

# 2) Garantir que "features" existe (même vide) pour homogénéiser le pipeline
#    (Le normalizer peut s'appuyer dessus sans cas spécial)
PULL_LISTING_SCHEMA["properties"].setdefault(
    "features",
    {
        "type": "object",
        "properties": {},
        "additionalProperties": True,  # Pulls: on ne force pas encore des clés spécifiques
    },
)

# 3) Garantir required = au moins "ai" + "features"
required = list(PULL_LISTING_SCHEMA.get("required", []))
if "ai" not in required:
    required.append("ai")
if "features" not in required:
    required.append("features")
PULL_LISTING_SCHEMA["required"] = required

logger.debug(
    "PULL_LISTING_SCHEMA initialisé (required=%s, properties=%s)",
    PULL_LISTING_SCHEMA.get("required", []),
    list(PULL_LISTING_SCHEMA.get("properties", {}).keys()),
)

# --------------------------------------------------------------------
# Profils
# --------------------------------------------------------------------

PULLS_PROFILES: Dict[AnalysisProfileName, AnalysisProfile] = {
    AnalysisProfileName.PULL: AnalysisProfile(
        name=AnalysisProfileName.PULL,
        json_schema=PULL_LISTING_SCHEMA,
        prompt_suffix=r"""
PROFILE TYPE: PULL / KNIT SWEATER

The item is a knit sweater (pull). It can be:
- A branded pull (Tommy Hilfiger, Ralph Lauren, etc.)
- A vintage/unbranded pull (no visible brand)

FOCUS ON:

1) BRAND & LOGO:
   - Look carefully for:
     - small flag logo on the chest (Tommy Hilfiger),
     - polo player logo (Ralph Lauren),
     - internal neck label with brand name.
   - Known brands to detect:
     - Tommy Hilfiger, Tommy Jeans, Hilfiger Denim
     - Ralph Lauren, Polo Ralph Lauren, Polo by Ralph Lauren
     - Other preppy/casual brands
   - If the brand is clearly visible:
     - Set "brand" to exactly that name.
   - If you cannot read the brand clearly OR there is no brand:
     - Set "brand" to null (do NOT guess).
     - This indicates a vintage/unbranded pull.

2) NECKLINE:
   - Identify:
     - col rond (crew neck),
     - col V (v-neck),
     - col zippe / col montant zippe,
     - col roule.
   - Set "neckline" accordingly when obvious.
   - Mention it in the French description:
     - "col rond", "col V", "col zippe", "col montant", etc.

3) PATTERN & COLORS:
   - Identify the pattern:
     - uni, raye, colorblock, a motifs, etc.
   - For stripes / colorblock:
     - Describe visible color combinations:
       "rayures bleu marine, rouge et gris", "colorblock bleu/rouge/blanc", etc.
   - Set "pattern" with a short value:
     - e.g. "raye", "uni", "colorblock".

4) STYLE:
   - Preppy / casual / smart casual / vintage.
   - Use "style" to capture:
     - "preppy", "casual chic", "college", "vintage", etc., only if it fits the visual.

5) MATERIAL / COMPOSITION:
   - Read composition from any label if it is clearly legible:
     - coton, laine, merino, cachemire, acrylique, melanges, etc.
   - Mention composition in the French description.
   - Do NOT invent composition if the label is not readable.
   - If the label mentions "Pima cotton", highlight it in the description (coton Pima = coton de qualite superieure).

6) SEASON:
   - Based on thickness and knit:
     - "hiver", "mi-saison", or similar.
   - Do not over-claim warmth; stay descriptive.

7) CONDITION & DEFECTS:
   - Look carefully for:
     - pilling / boulochage,
     - loose threads,
     - pulls or snags,
     - stains or discoloration,
     - deformation at cuffs, hem, or neckline.
   - "defects":
     - Short French summary, e.g.:
       - "Leger boulochage sur les manches"
       - "Petite tache claire pres du logo"
     - If really nothing visible: either null or
       "Aucun defaut majeur visible".

8) TITLE & DESCRIPTION (FRENCH):
   - title:
     - concise, clear, French.
     - For BRANDED pulls: include brand + garment type + key style or color.
       Examples:
       - "Pull Tommy Hilfiger raye bleu marine et rouge"
       - "Pull col V Ralph Lauren bleu marine"
     - For VINTAGE/UNBRANDED pulls: replace brand with "Vintage".
       Examples:
       - "Pull Vintage col rond vert foret"
       - "Pull Vintage raye multicolore"
   - description:
     - French, detailed, without markdown.
     - Mention:
       - type de pull (maille fine/epaisse),
       - type de col,
       - motif et couleurs,
       - marque (si connue) OU "vintage" si pas de marque,
       - eventuelle composition (si lisible),
       - etat general et defauts.

AI ENVELOPE (MANDATORY):
- Include top-level "ai" with:
  - status: "ok" | "needs_user_input" | "insufficient_images" | "refused" | "error"
  - reason: string or null
  - missing: array of strings
  - warnings: array of strings
- If status != "ok": keep uncertain fields to null and fill ai.missing.

JSON SCHEMA:
- Use the SAME JSON keys as defined in the main prompt contract.
- Do NOT add extra keys, and do NOT change key names.
- Output ONLY JSON, no extra text.
""",
    ),
}

logger.debug(
    "Profil PULL charge avec schema %s",
    list(PULL_LISTING_SCHEMA.get("properties", {}).keys()),
)
