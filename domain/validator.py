import logging

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
