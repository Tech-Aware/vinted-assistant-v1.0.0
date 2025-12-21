# domain/ocr_provider.py

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Sequence

logger = logging.getLogger(__name__)


class OCRProviderError(RuntimeError):
    """Erreur fonctionnelle liée au provider OCR."""


@dataclass
class OCRResult:
    """Résultat agrégé d'une extraction OCR."""

    full_text: str
    per_image_text: Dict[Path, str]


class OCRProvider(ABC):
    """
    Interface commune pour les providers OCR.
    """

    @abstractmethod
    def extract_text(self, image_paths: Sequence[Path]) -> OCRResult:
        """
        Extrait du texte pour chaque image fournie.
        Doit lever OCRProviderError en cas de problème fonctionnel.
        """
        raise NotImplementedError
