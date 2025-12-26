import logging
import re
from typing import Optional

from domain.templates.base import AnalysisProfileName  # adapte l'import si différent


logger = logging.getLogger(__name__)


class ListingValidationError(Exception):
    pass


def validate_listing(data: dict):
    errors = []

    # title required
    title = data.get("title")
    if not title or not title.strip():
        errors.append("title is required and must be non-empty")

    # description minimum
    desc = data.get("description")
    if not desc or len(desc.split()) < 5:
        errors.append("description must contain at least 5 words")

    # no weird patterns
    if title and "!!!!" in title:
        errors.append("title contains spam punctuation")

    if errors:
        logger.error("Validation errors: %s", errors)
        raise ListingValidationError(" / ".join(errors))

    logger.debug("Listing validated OK.")

# SKU Durin interne : LETTRES + CHIFFRES
# ex: JLF123, PTF42, PTNF007
_INTERNAL_SKU_RE = re.compile(r"^[A-Z]{2,6}\d{1,8}$")

# Codes usine / lavage / lot OCR (INTERDITS comme SKU)
# ex: 18-24-8
_FACTORY_CODE_RE = re.compile(r"^\d{2}-\d{2}-\d{1,2}$")


def _clean_sku(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    return str(raw).strip().upper().replace(" ", "") or None


def is_valid_internal_sku(profile: AnalysisProfileName, sku: Optional[str]) -> bool:
    """
    Validation du SKU interne Durin.
    Source de vérité UNIQUE.
    """
    sku_clean = _clean_sku(sku)
    if not sku_clean:
        return False

    # Refus explicite des codes OCR type 18-24-8
    if _FACTORY_CODE_RE.match(sku_clean):
        logger.debug(
            "SKU rejeté (profil=%s): code usine détecté (%s)",
            profile.value,
            sku_clean,
        )
        return False

    # Format attendu : LETTRES + CHIFFRES
    if not _INTERNAL_SKU_RE.match(sku_clean):
        logger.debug(
            "SKU rejeté (profil=%s): format interne invalide (%s)",
            profile.value,
            sku_clean,
        )
        return False

    return True

