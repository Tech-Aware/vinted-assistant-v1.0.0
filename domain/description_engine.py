from __future__ import annotations

import logging
from typing import Iterable, List, Optional

logger = logging.getLogger(__name__)


class DescriptionBlockOrder:
    """
    Structure fixe des descriptions :
    1) Ligne titre (sans SKU)
    2) Paragraphe commercial
    3) Composition (placeholders compatibles UI)
    4) État & logistique
    5) Footer (2 lignes)
    6) Hashtags (1 ligne)
    """

    def __init__(
        self,
        title_line: str,
        commercial_paragraph: str,
        composition_line: str,
        state_logistics_lines: Iterable[str],
        footer_lines: Iterable[str],
        hashtags_line: str,
    ) -> None:
        self.title_line = (title_line or "").strip()
        self.commercial_paragraph = (commercial_paragraph or "").strip()
        self.composition_line = (composition_line or "").strip()
        self.state_logistics_lines = [line.strip() for line in state_logistics_lines if line and str(line).strip()]
        self.footer_lines = [line.strip() for line in footer_lines if line and str(line).strip()]
        self.hashtags_line = (hashtags_line or "").strip()


def render_description(blocks: DescriptionBlockOrder) -> str:
    """
    Assemble une description conforme aux blocs 1→6.
    En cas d'erreur, on remonte un texte minimal tout en journalisant l'exception.
    """
    try:
        parts: List[str] = []

        if blocks.title_line:
            parts.append(blocks.title_line)
        if blocks.commercial_paragraph:
            parts.append(blocks.commercial_paragraph)
        if blocks.composition_line:
            parts.append(blocks.composition_line)
        if blocks.state_logistics_lines:
            parts.append("\n".join(blocks.state_logistics_lines))
        if blocks.footer_lines:
            parts.append("\n".join(blocks.footer_lines))
        if blocks.hashtags_line:
            parts.append(blocks.hashtags_line)

        assembled = "\n\n".join(part for part in parts if part)
        logger.debug("render_description: description assemblée (%d caractères)", len(assembled))
        return assembled
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("render_description: assemblage impossible (%s)", exc)
        fallback = "\n\n".join(
            part
            for part in [
                blocks.title_line,
                blocks.commercial_paragraph,
                blocks.composition_line,
                "\n".join(blocks.state_logistics_lines),
                "\n".join(blocks.footer_lines),
                blocks.hashtags_line,
            ]
            if part
        )
        return fallback.strip()
