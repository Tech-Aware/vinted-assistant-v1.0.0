# domain/templates/jackets.py

from __future__ import annotations

import logging
from copy import deepcopy
from typing import Dict

from .base import AnalysisProfile, AnalysisProfileName, BASE_LISTING_SCHEMA

logger = logging.getLogger(__name__)


JACKET_LISTING_SCHEMA = deepcopy(BASE_LISTING_SCHEMA)

JACKET_LISTING_SCHEMA["properties"].update(
    {
        "features": {
            "type": "object",
            "properties": {
                "brand": {"type": ["string", "null"]},
                "model": {"type": ["string", "null"]},
                "size": {"type": ["string", "null"]},
                "color": {"type": ["string", "null"]},
                "gender": {"type": ["string", "null"]},
                "has_hood": {"type": ["boolean", "null"]},
                "pattern": {"type": ["string", "null"]},
                "lining": {"type": ["string", "null"]},
                "closure": {"type": ["string", "null"]},
                "patch_material": {"type": ["string", "null"]},
                "collar_material": {"type": ["string", "null"]},
                "zipper_material": {"type": ["string", "null"]},
                "origin_country": {"type": ["string", "null"]},
                "has_chest_pocket": {"type": ["boolean", "null"]},
                "is_camouflage": {"type": ["boolean", "null"]},
                "is_realtree": {"type": ["boolean", "null"]},
                "is_new_york": {"type": ["boolean", "null"]},
            },
        }
    }
)


JACKETS_PROFILES: Dict[AnalysisProfileName, AnalysisProfile] = {
    AnalysisProfileName.JACKET_CARHART: AnalysisProfile(
        name=AnalysisProfileName.JACKET_CARHART,
        json_schema=JACKET_LISTING_SCHEMA,
        prompt_suffix=r"""
PROFILE TYPE: JACKET CARHARTT

Le vêtement est une veste Carhartt (workwear, streetwear ou outdoor).

OBJECTIF PRINCIPAL :
- Identifier automatiquement le modèle Carhartt (Detroit, Active, Michigan, New York, etc.).
- Générer un titre au format :
  Veste Carhartt modèle [nom du modèle] taille [taille] couleur [couleur] homme

CONTRAINTES TITRE (FRANÇAIS) :
- Le mot "jacket" doit toujours apparaître.
- S'il y a une capuche : mentionne clairement "veste à capuche Carhartt".
- Si motif camouflage : ajouter la mention "Realtree" dans le titre.
- Pour les modèles New York : ajouter "NY" dans le titre.

DESCRIPTION (FRANÇAIS) :
- Décrire l'intérieur (doublure, sherpa, matelassé, etc.).
- Préciser la capuche (amovible ou non), la fermeture (zip, boutons pression, double zip),
  la présence d'un écusson et sa matière (tissu ou cuir).
- Détailler le col (ex : velours côtelé), la matière du zip (métal / laiton) et la présence
  d'une poche poitrine zippée si visible.
- Mentionner le pays de fabrication quand il est lisible (ex : Made in USA).
- Rester factuel : ne rien inventer si l'information n'est pas visible.

SORTIE JSON OBLIGATOIRE :
- Respecter le schéma principal (title, description, brand, style, pattern, neckline, season, defects).
- Ajouter un objet "features" avec les clés suivantes :
  {
    "brand": string | null,
    "model": string | null,
    "size": string | null,
    "color": string | null,
    "gender": string | null,
    "has_hood": boolean | null,
    "pattern": string | null,
    "lining": string | null,
    "closure": string | null,
    "patch_material": string | null,
    "collar_material": string | null,
    "zipper_material": string | null,
    "origin_country": string | null,
    "has_chest_pocket": boolean | null,
    "is_camouflage": boolean | null,
    "is_realtree": boolean | null,
    "is_new_york": boolean | null
  }
- Ne JAMAIS inventer une valeur : si l'information n'est pas lisible, utiliser null.
- Répondre UNIQUEMENT avec le JSON (aucun texte ou commentaire autour).
""",
    ),
}

logger.debug(
    "Profil JACKET_CARHART chargé avec schéma %s",
    list(JACKET_LISTING_SCHEMA["properties"].keys()),
)
