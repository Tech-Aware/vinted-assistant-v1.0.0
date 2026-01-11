# infrastructure/google_vision_ocr.py

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from google.cloud import vision

from domain.ocr_models import OCRStructured
from domain.ocr_provider import OCRProvider, OCRProviderError, OCRResult
from domain.ocr_structurer import StructuredOCRExtractor
from domain.path_validator import validate_image_paths, PathValidationError

logger = logging.getLogger(__name__)

# Nombre maximum de workers pour le traitement parallèle OCR
MAX_OCR_WORKERS = int(os.getenv("VINTED_OCR_MAX_WORKERS", "5"))


class GoogleVisionOCRProvider(OCRProvider):
    """
    Provider OCR basé sur Google Vision.

    Requiert :
    - la dépendance `google-cloud-vision`
    - une variable d'environnement GOOGLE_APPLICATION_CREDENTIALS pointant vers la clé service

    Optimisations :
    - Traitement parallèle des images avec ThreadPoolExecutor
    - Configurable via VINTED_OCR_MAX_WORKERS (défaut: 5)
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

    def _extract_single_image(self, path: Path) -> Tuple[Path, Optional[str], Optional[str]]:
        """
        Extrait le texte d'une seule image.

        Returns:
            Tuple (path, text, error_message)
            - text est None si une erreur s'est produite
            - error_message contient le message d'erreur le cas échéant
        """
        try:
            if not path.exists():
                return path, None, f"Image introuvable: {path}"

            content = path.read_bytes()
            image = vision.Image(content=content)
            response = self._client.document_text_detection(image=image)

            if response.error.message:
                return path, None, f"Erreur Vision API: {response.error.message}"

            description = (response.full_text_annotation.text or "").strip()
            logger.debug("OCR %s: %d caractère(s) extraits.", path, len(description))
            return path, description, None

        except Exception as exc:
            return path, None, f"Exception: {exc}"

    def extract_text(self, image_paths: Sequence[Path]) -> OCRResult:
        """
        Extrait le texte de plusieurs images en parallèle.

        Utilise ThreadPoolExecutor pour traiter les images simultanément,
        ce qui améliore significativement les performances avec plusieurs images.
        """
        if not image_paths:
            raise OCRProviderError("Aucune image fournie pour l'OCR.")

        # Validation sécurisée des chemins (prévention path traversal)
        try:
            validated_paths = validate_image_paths(
                [Path(p) for p in image_paths],
                check_exists=True,
                check_extension=True,
            )
        except PathValidationError as exc:
            logger.error("Validation des chemins OCR échouée: %s", exc)
            raise OCRProviderError(f"Chemins d'images OCR invalides: {exc}") from exc

        per_image: Dict[Path, str] = {}
        errors: List[str] = []

        # Déterminer le nombre optimal de workers
        num_workers = min(MAX_OCR_WORKERS, len(validated_paths))

        if num_workers <= 1:
            # Traitement séquentiel pour une seule image (pas de surcharge ThreadPool)
            for path in validated_paths:
                result_path, text, error = self._extract_single_image(path)
                if text is not None:
                    per_image[result_path] = text
                elif error:
                    errors.append(error)
                    logger.warning("OCR échoué pour %s: %s", result_path, error)
        else:
            # Traitement parallèle pour plusieurs images
            logger.info(
                "Démarrage OCR parallèle: %d image(s) avec %d worker(s).",
                len(validated_paths),
                num_workers,
            )

            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                # Soumettre toutes les tâches
                future_to_path = {
                    executor.submit(self._extract_single_image, path): path
                    for path in validated_paths
                }

                # Collecter les résultats au fur et à mesure
                for future in as_completed(future_to_path):
                    try:
                        result_path, text, error = future.result()
                        if text is not None:
                            per_image[result_path] = text
                        elif error:
                            errors.append(error)
                            logger.warning("OCR échoué pour %s: %s", result_path, error)
                    except Exception as exc:
                        original_path = future_to_path[future]
                        errors.append(f"Exception pour {original_path}: {exc}")
                        logger.exception("Erreur OCR inattendue pour %s", original_path)

        # Log des erreurs agrégées si présentes
        if errors:
            logger.warning(
                "OCR terminé avec %d erreur(s) sur %d image(s).",
                len(errors),
                len(validated_paths),
            )

        aggregated = "\n\n".join(text for text in per_image.values() if text)
        logger.info(
            "OCR terminé (%d/%d image(s) réussies, %d caractère(s) agrégés).",
            len(per_image),
            len(validated_paths),
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
                structured.filtered_text[:1000] if structured.filtered_text else "",
            )
        except Exception as exc:  # pragma: no cover - robustesse
            logger.warning(
                "Extraction OCR structurée échouée (fallback brut utilisé): %s",
                exc,
                exc_info=True,
            )
            structured = None

        return OCRResult(full_text=aggregated, per_image_text=per_image, structured=structured)
