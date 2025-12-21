# domain/ai_provider.py

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from domain.models import VintedListing
from domain.templates import AnalysisProfile

logger = logging.getLogger(__name__)


class AIProviderName(Enum):
    """
    Fournisseurs IA disponibles pour générer des annonces Vinted.
    """
    GEMINI = "gemini"
    # Une seule implémentation conservée : Gemini


class AIListingProvider(ABC):
    """
    Interface commune pour le fournisseur d'IA.

    Chaque implémentation (Gemini) doit :
    - prendre une image locale (Path)
    - prendre un profil d'analyse (AnalysisProfile)
    - renvoyer un VintedListing
    """

    @property
    @abstractmethod
    def name(self) -> AIProviderName:
        """
        Nom logique du provider (GEMINI).
        """
        raise NotImplementedError

    @abstractmethod
    def generate_listing(
        self,
        image_paths: Sequence[Path],
        profile: AnalysisProfile,
        ui_data: Optional[Dict[str, Any]] = None,
    ) -> VintedListing:
        """
        Analyse une ou plusieurs images en fonction du profil et renvoie une annonce Vinted.
        Doit lever une exception métier propre (par ex. GeminiClientError)
        en cas de problème côté provider.
        """
        raise NotImplementedError
