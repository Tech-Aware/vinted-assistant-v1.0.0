# domain/templates/pulls.py

from __future__ import annotations

import logging
from typing import Dict

from .base import AnalysisProfile, AnalysisProfileName, BASE_LISTING_SCHEMA

logger = logging.getLogger(__name__)


PULLS_PROFILES: Dict[AnalysisProfileName, AnalysisProfile] = {
    AnalysisProfileName.PULL_TOMMY: AnalysisProfile(
        name=AnalysisProfileName.PULL_TOMMY,
        prompt_suffix=r"""
PROFILE TYPE: PULL TOMMY HILFIGER / PREPPY KNIT

The item is a knit sweater (pull) with a preppy / Tommy Hilfiger style.

FOCUS ON:

1) BRAND & LOGO:
   - Look for:
     - small flag logo on the chest,
     - internal neck label (Tommy Hilfiger, Tommy Jeans, etc.).
   - If the brand is clearly visible:
     - Set "brand" to exactly that name.
   - If you cannot read the brand clearly:
     - Set "brand" to null (do NOT guess).

2) NECKLINE:
   - Identify:
     - col rond (crew neck),
     - col V (v-neck),
     - col zippé / col montant zippé,
     - col roulé.
   - Set "neckline" accordingly when obvious.
   - Mention it in the French description:
     - "col rond", "col V", "col zippé", "col montant", etc.

3) PATTERN & COLORS:
   - Identify the pattern:
     - uni, rayé, colorblock, à motifs, etc.
   - For stripes / colorblock:
     - Describe visible color combinations:
       "rayures bleu marine, rouge et gris", "colorblock bleu/rouge/blanc", etc.
   - Set "pattern" with a short value:
     - e.g. "rayé", "uni", "colorblock".

4) STYLE:
   - Preppy / casual / smart casual.
   - Use "style" to capture:
     - "preppy", "casual chic", "college", etc., only if it fits the visual.

5) MATERIAL / COMPOSITION:
   - Read composition from any label if it is clearly legible:
     - coton, laine, merino, cachemire, acrylique, mélanges, etc.
   - Mention composition in the French description.
   - Do NOT invent composition if the label is not readable.

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
       - "Léger boulochage sur les manches"
       - "Petite tache claire près du logo"
     - If really nothing visible: either null or
       "Aucun défaut majeur visible".

8) TITLE & DESCRIPTION (FRENCH):
   - title:
     - concise, clear, French.
     - Should ideally include brand + garment type + key style or color.
     - examples:
       - "Pull Tommy Hilfiger rayé bleu marine et rouge"
       - "Pull col V Tommy Jeans bleu marine"
   - description:
     - French, detailed, without markdown.
     - Mention:
       - type de pull (maille fine/épaisse),
       - type de col,
       - motif et couleurs,
       - marque (si connue),
       - éventuelle composition (si lisible),
       - état général et défauts.

JSON SCHEMA:
- Use the SAME JSON keys as defined in the main prompt contract:
  "title", "description", "brand", "style", "pattern", "neckline", "season", "defects".
- Do NOT add extra keys, and do NOT change key names.
""",
        json_schema=BASE_LISTING_SCHEMA,
    ),
}

logger.debug(
    "Profil PULL_TOMMY chargé avec schéma %s",
    list(BASE_LISTING_SCHEMA["properties"].keys()),
)
