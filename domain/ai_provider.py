# domain/ai_provider.py

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path

from domain.models import VintedListing
from domain.templates import AnalysisProfile

logger = logging.getLogger(__name__)


class AIProviderName(Enum):
    """
    Fournisseurs IA disponibles pour générer des annonces Vinted.
    """
    GEMINI = "gemini"
    OPENAI = "openai"
    # Plus tard : ANTHROPIC = "anthropic"


class AIListingProvider(ABC):
    """
    Interface commune à tous les fournisseurs d'IA.

    Chaque implémentation (Gemini, OpenAI, etc.) doit :
    - prendre une image locale (Path)
    - prendre un profil d'analyse (AnalysisProfile)
    - renvoyer un VintedListing
    """

    @property
    @abstractmethod
    def name(self) -> AIProviderName:
        """
        Nom logique du provider (GEMINI, OPENAI, ...).
        """
        raise NotImplementedError

    @abstractmethod
    def generate_listing(self, image_path: Path, profile: AnalysisProfile) -> VintedListing:
        """
        Analyse l'image en fonction du profil et renvoie une annonce Vinted.
        Doit lever une exception métier propre (par ex. GeminiClientError / OpenAIClientError)
        en cas de problème côté provider.
        """
        raise NotImplementedError
