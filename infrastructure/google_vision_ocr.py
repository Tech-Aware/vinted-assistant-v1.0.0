# infrastructure/google_vision_ocr.py

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, Optional, Sequence

from google.cloud import vision

from domain.ocr_models import OCRStructured
from domain.ocr_provider import OCRProvider, OCRProviderError, OCRResult
from domain.ocr_structurer import StructuredOCRExtractor

logger = logging.getLogger(__name__)


class GoogleVisionOCRProvider(OCRProvider):
    """
    Provider OCR basé sur Google Vision.

    Requiert :
    - la dépendance `google-cloud-vision`
    - une variable d'environnement GOOGLE_APPLICATION_CREDENTIALS pointant vers la clé service
    """

    def __init__(self, credentials_path: str | None = None) -> None:
        if credentials_path:
            os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", credentials_path)

        try:
            self._client = vision.ImageAnnotatorClient()
            logger.info("Client Google Vision OCR initialisé.")
        except Exception as exc:  # pragma: no cover - dépendance externe
            logger.error("Impossible d'initialiser Google Vision OCR: %s", exc, exc_info=True)
            raise OCRProviderError(f"Initialisation Google Vision impossible: {exc}") from exc

    def extract_text(self, image_paths: Sequence[Path]) -> OCRResult:
        if not image_paths:
            raise OCRProviderError("Aucune image fournie pour l'OCR.")

        per_image: Dict[Path, str] = {}
        for path in image_paths:
            try:
                if not path.exists():
                    logger.warning("Image OCR introuvable: %s", path)
                    continue

                content = path.read_bytes()
                image = vision.Image(content=content)
                response = self._client.document_text_detection(image=image)

                if response.error.message:
                    logger.warning(
                        "Google Vision a retourné une erreur pour %s: %s",
                        path,
                        response.error.message,
                    )
                    continue

                description = response.full_text_annotation.text or ""
                description = description.strip()
                per_image[path] = description
                logger.debug(
                    "OCR %s: %d caractère(s) extraits.",
                    path,
                    len(description),
                )
            except Exception as exc:  # pragma: no cover - dépendance externe
                logger.warning("Extraction OCR échouée pour %s: %s", path, exc, exc_info=True)

        aggregated = "\n\n".join(text for text in per_image.values() if text)
        logger.info(
            "OCR terminé (%d image(s), %d caractère(s) agrégés).",
            len(per_image),
            len(aggregated),
        )

        structured: Optional[OCRStructured] = None
        try:
            structurer = StructuredOCRExtractor()
            structured = structurer.structure(aggregated)
            logger.info(
                "OCR structuré construit (%d ligne(s) retenues, %d élément(s) de composition).",
                len(structured.debug_lines),
                len(structured.composition_items),
            )
            logger.debug(
                "OCR filtré (tronqué): %s",
                structured.filtered_text[:1000],
            )
        except Exception as exc:  # pragma: no cover - robustesse
            logger.warning(
                "Extraction OCR structurée échouée (fallback brut utilisé): %s",
                exc,
                exc_info=True,
            )
            structured = None

        return OCRResult(full_text=aggregated, per_image_text=per_image, structured=structured)
