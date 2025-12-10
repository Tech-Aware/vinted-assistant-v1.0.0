# domain/templates/polaires.py

from __future__ import annotations

import logging
from typing import Dict

from .base import AnalysisProfile, AnalysisProfileName, BASE_LISTING_SCHEMA

logger = logging.getLogger(__name__)


POLAIRES_PROFILES: Dict[AnalysisProfileName, AnalysisProfile] = {
    AnalysisProfileName.POLAIRE_OUTDOOR: AnalysisProfile(
        name=AnalysisProfileName.POLAIRE_OUTDOOR,
        prompt_suffix=r"""
PROFILE TYPE: POLAIRE OUTDOOR

The item is an outdoor fleece (polaire) used for hiking, camping, or cold weather.

FOCUS ON:

1) BRAND:
   - Look for logos and labels from outdoor brands:
     - The North Face, Columbia, Quechua, Patagonia, Millet, etc.
   - If the brand is clearly readable on a label or logo:
     - Set "brand" to that exact text (e.g. "The North Face").
   - If no clear brand is visible:
     - Set "brand" to null (do NOT invent).

2) TYPE OF FLEECE:
   - Identify:
     - full-zip, half-zip, quarter-zip, pullover,
     - hooded (capuche) or non-hooded.
   - Mention this clearly in the French description:
     - "polaire zippée intégrale", "demi-zip", "quart de zip", etc.

3) THICKNESS & SEASON:
   - From the texture and thickness:
     - micropolaire fine (lightweight),
     - polaire moyenne,
     - polaire épaisse.
   - For "season":
     - use "hiver" or "mi-saison" when it makes sense.
   - Do NOT invent technical specs (e.g. g/m²) unless it is clearly printed.

4) FEATURES:
   - Check for:
     - zipped pockets (chest or sides),
     - elastic cuffs or hem,
     - reinforcements on shoulders or elbows,
     - drawcords at hem or hood.
   - Describe these features in the French description if visible.

5) PATTERN & COLORS:
   - For "pattern":
     - use "uni", "bicolore", "colorblock", "rayé", "camouflage", etc., if clear.
   - In the description, mention main visible colors:
     - "bleu marine", "noir", "gris clair", "bordeaux", etc.

6) NECKLINE:
   - Identify:
     - col rond, col montant, col zippé, col cheminée, capuche.
   - Set "neckline" accordingly when obvious, otherwise null.

7) CONDITION & DEFECTS:
   - Inspect carefully:
     - pilling / boulochage (especially on sleeves and sides),
     - stains on front or sleeves,
     - damaged zipper or sliders,
     - holes, snags, pulled threads.
   - "defects":
     - A short French description of any visible issues, e.g.:
       - "Léger boulochage sur les manches"
       - "Petite tache sur le bas devant"
     - If really no visible defect: you may set
       "Aucun défaut majeur visible" or null.

8) TITLE & DESCRIPTION (FRENCH):
   - title:
     - concise, French, and informative.
     - e.g. "Polaire The North Face zippée - bleu marine"
          "Micropolaire Columbia à capuche - noir"
   - description:
     - French, detailed, no markdown.
     - Mention:
       - type de polaire (micropolaire, polaire épaisse),
       - marque (si connue),
       - type de zip et col,
       - éventuelles poches et détails techniques,
       - saison d'utilisation (hiver, mi-saison),
       - état général + défauts.

JSON SCHEMA:
- Use the SAME JSON keys as defined in the main prompt contract:
  "title", "description", "brand", "style", "pattern", "neckline", "season", "defects".
- Do NOT add or rename keys.
""",
        json_schema=BASE_LISTING_SCHEMA,
    ),
}

logger.debug(
    "Profil POLAIRE_OUTDOOR chargé avec schéma %s",
    list(BASE_LISTING_SCHEMA["properties"].keys()),
)
