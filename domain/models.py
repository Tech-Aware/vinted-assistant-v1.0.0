# domain/models.py

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any


logger = logging.getLogger(__name__)


class Condition(Enum):
    """
    État du vêtement, adapté au vocabulaire Vinted.
    """
    NEUF = "neuf"
    TRES_BON_ETAT = "très bon état"
    BON_ETAT = "bon état"
    SATISFAISANT = "satisfaisant"
    A_RECYCLER = "à recycler"


@dataclass
class VintedListing:
    """
    Modèle métier pour une annonce Vinted générée par l'IA.

    Ce modèle ne gère pas l'UI, ni l'API.
    Il ne sert qu'à représenter une annonce propre en interne.
    """

    title: str
    description: str
    brand: Optional[str] = None
    size: Optional[str] = None
    condition: Optional[Condition] = None
    color: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    sku: Optional[str] = None
    sku_status: Optional[str] = None
    features: Dict[str, Any] = field(default_factory=dict)
    manual_composition_text: Optional[str] = None

    # ------------------------------------------------------------------ #
    # Validation métier
    # ------------------------------------------------------------------ #

    def validate(self) -> None:
        """
        Valide le contenu de l'objet.
        Lève ValueError si des champs obligatoires sont manquants ou invalides.
        """
        logger.debug("Validation du VintedListing: %r", self)

        errors: List[str] = []

        if not isinstance(self.title, str) or not self.title.strip():
            errors.append("Le titre est obligatoire et ne doit pas être vide.")

        if not isinstance(self.description, str) or not self.description.strip():
            errors.append("La description est obligatoire et ne doit pas être vide.")

        # Vérification des tags
        if not isinstance(self.tags, list):
            errors.append("Tags doit être une liste.")
        else:
            for t in self.tags:
                if not isinstance(t, str):
                    errors.append(f"Tag invalide (non-str): {t!r}")
                    break

        if self.condition is not None and not isinstance(self.condition, Condition):
            errors.append("Condition doit être une instance de Condition ou None.")

        if errors:
            logger.error(
                "Validation VintedListing échouée: %s | objet=%r",
                errors,
                self,
            )
            raise ValueError(" / ".join(errors))

        logger.debug("Validation VintedListing OK pour %r", self)

    # ------------------------------------------------------------------ #
    # Fabriques
    # ------------------------------------------------------------------ #

    @classmethod
    def _parse_condition(cls, raw: Any) -> Optional[Condition]:
        """
        Parse une condition brute (str ou enum).
        Ne lève pas d’exception, retourne None si inconnu.
        """
        if raw is None:
            return None

        if isinstance(raw, Condition):
            return raw

        if isinstance(raw, str):
            txt = raw.strip().lower()
            mapping = {
                "neuf": Condition.NEUF,
                "neuf avec etiquette": Condition.NEUF,
                "très bon état": Condition.TRES_BON_ETAT,
                "tres bon etat": Condition.TRES_BON_ETAT,
                "bon état": Condition.BON_ETAT,
                "bon etat": Condition.BON_ETAT,
                "satisfaisant": Condition.SATISFAISANT,
                "mauvais": Condition.A_RECYCLER,
                "pour pièces": Condition.A_RECYCLER,
                "pour pieces": Condition.A_RECYCLER,
                "pour piece": Condition.A_RECYCLER,
            }
            cond = mapping.get(txt)
            if cond is None:
                logger.warning("Condition inconnue: %r (None retourné)", raw)
            return cond

        logger.warning("Condition avec type invalide: %r (None retourné)", raw)
        return None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VintedListing":
        """
        Construit un VintedListing à partir d’un dict (ex: JSON Gemini).
        - Applique un parsing minimal
        - Valide l’objet final
        - Lève ValueError en cas d’erreur métier
        """
        logger.debug("Construction de VintedListing depuis dict: %r", data)

        try:
            title = data.get("title", "")
            description = data.get("description", "")

            brand = data.get("brand")
            size = data.get("size")
            color = data.get("color")
            sku = data.get("sku")
            sku_status = data.get("sku_status")

            raw_condition = data.get("condition")
            condition = cls._parse_condition(raw_condition)

            raw_tags = data.get("tags", [])
            tags: List[str] = []

            if isinstance(raw_tags, list):
                for t in raw_tags:
                    if isinstance(t, str):
                        tags.append(t)
                    else:
                        logger.warning("Tag ignoré (non str): %r", t)
            else:
                logger.warning("Champ 'tags' non liste: %r", raw_tags)

            features = data.get("features") or {}
            manual_composition_text = data.get("manual_composition_text")

            listing = cls(
                title=title,
                description=description,
                brand=brand,
                size=size,
                color=color,
                condition=condition,
                tags=tags,
                sku=sku,
                sku_status=sku_status,
                features=features,
                manual_composition_text=manual_composition_text,
            )

            listing.validate()
            return listing

        except ValueError:
            raise
        except Exception as exc:
            logger.exception("Erreur inattendue dans VintedListing.from_dict.")
            raise ValueError(
                f"Erreur inattendue dans VintedListing.from_dict: {exc}"
            ) from exc

    def to_dict(self) -> Dict[str, Any]:
        """
        Sérialise l’objet en dict simple.
        """
        try:
            condition_value = self.condition.value if self.condition else None
            result = {
                "title": self.title,
                "description": self.description,
                "brand": self.brand,
                "size": self.size,
                "condition": condition_value,
                "color": self.color,
                "tags": list(self.tags),
                "sku": self.sku,
                "sku_status": self.sku_status,
                "features": dict(self.features),
                "manual_composition_text": self.manual_composition_text,
            }
            logger.debug("Sérialisation VintedListing: %r", result)
            return result
        except Exception as exc:
            logger.exception("Erreur de sérialisation VintedListing.to_dict.")
            return {
                "error": repr(exc),
                "repr": repr(self),
            }
