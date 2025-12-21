# infrastructure/gemini_client.py

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Sequence

import google.generativeai as genai

from config.settings import Settings
from domain.ai_provider import AIListingProvider, AIProviderName
from domain.json_utils import safe_json_parse
from domain.models import VintedListing
from domain.prompt import PROMPT_CONTRACT
from domain.templates import AnalysisProfile
from domain.normalizer import normalize_and_postprocess

logger = logging.getLogger(__name__)


class GeminiClientError(RuntimeError):
    """
    Exception fonctionnelle pour les erreurs Gemini.
    """


class GeminiListingClient(AIListingProvider):
    """
    Provider IA pour Google Gemini (vision).

    Analyse une ou plusieurs images d'un même article + un profil d'analyse
    et renvoie un VintedListing.

    IMPORTANT :
    - On NE demande PAS de structured output via response_schema.
    - On se contente d'un prompt très strict qui exige une réponse JSON.
    - On parse ensuite ce JSON avec safe_json_parse.
    """

    def __init__(self, settings: Settings) -> None:
        logger.debug("Initialisation GeminiListingClient...")
        if not settings.gemini_api_key:
            raise GeminiClientError("GEMINI_API_KEY absente.")

        genai.configure(api_key=settings.gemini_api_key)
        self._model_name = self._normalize_model_name(settings.gemini_model)

        logger.info("GeminiListingClient initialisé (model=%s).", self._model_name)

    @property
    def model_name(self) -> str:
        """
        Nom du modèle Gemini actuellement configuré.
        """
        return self._model_name

    def update_model(self, model_name: str) -> None:
        """
        Met à jour dynamiquement le modèle Gemini utilisé pour les générations.

        La normalisation applique automatiquement le préfixe 'models/' si absent.
        """
        try:
            normalized = self._normalize_model_name(model_name)
            if normalized == self._model_name:
                logger.info("Modèle Gemini inchangé (%s).", self._model_name)
                return

            self._model_name = normalized
            logger.info("Modèle Gemini mis à jour dynamiquement: %s", self._model_name)
        except Exception as exc:  # pragma: no cover - robustesse
            logger.error("Echec de mise à jour du modèle Gemini: %s", exc, exc_info=True)
            raise GeminiClientError(f"Modèle Gemini invalide: {exc}") from exc

    # ------------------------------------------------------------------
    # Nom du provider
    # ------------------------------------------------------------------

    @property
    def name(self) -> AIProviderName:
        return AIProviderName.GEMINI

    # ------------------------------------------------------------------
    # Méthode principale
    # ------------------------------------------------------------------

    def generate_listing(
        self,
        image_paths: Sequence[Path],
        profile: AnalysisProfile,
        ui_data: Dict[str, Any] | None = None,
    ) -> VintedListing:
        """
        Analyse UNE OU PLUSIEURS images (toutes du même article) + profil,
        renvoie un VintedListing.
        """
        # Normalisation en liste de Path pour garantir un contrat robuste
        paths: List[Path] = [Path(p) for p in image_paths]

        if not paths:
            raise GeminiClientError("Aucune image fournie à Gemini.generate_listing.")

        logger.info(
            "Gemini.generate_listing(images=%s, profile='%s')",
            [str(p) for p in paths],
            profile.name.value,
        )

        try:
            raw_text = self._call_api(paths, profile, ui_data=ui_data)
            logger.debug("Gemini brut: %s", raw_text[:400])

            # JSON robuste (si jamais il y a des ```json ....```, safe_json_parse gère)
            parsed: Dict[str, Any] = safe_json_parse(raw_text)
            if parsed is None:
                raise GeminiClientError(
                    "Réponse Gemini illisible (JSON invalide ou introuvable)."
                )

            # Post-traitement + normalisation (titre JEAN_LEVIS, mapping clés, etc.)
            normalized = normalize_and_postprocess(
                ai_data=parsed,
                profile_name=profile.name,
                ui_data=ui_data,
            )

            listing = VintedListing.from_dict(normalized)
            logger.info("Annonce Gemini générée: '%s'.", listing.title)

            return listing

        except GeminiClientError:
            raise
        except Exception as exc:
            logger.exception("Erreur inattendue Gemini.generate_listing.")
            raise GeminiClientError(f"Erreur inattendue: {exc}") from exc

    # ------------------------------------------------------------------
    # Construction des contenus pour Gemini (texte + multi-images)
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_model_name(model_name: str) -> str:
        """
        Normalise le nom du modèle Gemini pour éviter les erreurs 400
        "unexpected model name format".

        - Gemini attend le préfixe "models/". Si l'utilisateur saisit
          uniquement le nom court (ex: "gemini-2.5-flash"), on le préfixe
          automatiquement.
        - On valide également que la chaîne n'est pas vide.
        """

        cleaned = (model_name or "").strip()
        if not cleaned:
            raise GeminiClientError("Nom de modèle Gemini manquant ou vide.")

        if not cleaned.startswith("models/"):
            logger.warning(
                "Nom de modèle Gemini sans préfixe 'models/': %s. Préfixage automatique...",
                cleaned,
            )
            cleaned = f"models/{cleaned}"

        return cleaned


    def _build_parts(
        self,
        image_paths: List[Path],
        profile: AnalysisProfile,
        ui_data: Dict[str, Any] | None = None,
    ) -> List[Any]:
        """
        Construit une liste de "parts" pour google-generativeai :

        - d'abord le texte (PROMPT_CONTRACT + prompt_suffix)
        - ensuite toutes les images (SKU, vues, étiquettes, mesures) du même article
        """
        # Texte : contrat global + profil spécialisé
        full_prompt = PROMPT_CONTRACT + "\n\n" + profile.prompt_suffix

        measurement_mode = None
        try:
            measurement_mode = (ui_data or {}).get("measurement_mode")
            if measurement_mode:
                logger.debug(
                    "Gemini._build_parts: measurement_mode fourni: %s",
                    measurement_mode,
                )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "Gemini._build_parts: lecture measurement_mode impossible (%s)",
                exc,
            )
            measurement_mode = None

        parts: List[Any] = [full_prompt]

        if measurement_mode:
            parts.append(
                (
                    f"Mode de relevé UI : {measurement_mode}. "
                    "Si measurement_mode=mesures, estime la taille depuis les mesures à plat "
                    "quand aucune étiquette n'est lisible, sans inventer ni lister les mesures."
                )
            )

        for path in image_paths:
            if not path.exists():
                logger.error("Image introuvable pour Gemini: %s", path)
                raise GeminiClientError(f"Image introuvable: {path}")

            try:
                img_bytes = path.read_bytes()
            except Exception as exc:
                logger.exception("Erreur lecture image Gemini (%s).", path)
                raise GeminiClientError(f"Erreur lecture image '{path}': {exc}") from exc

            parts.append(
                {
                    "mime_type": "image/jpeg",  # adapte si tu envoies du PNG/WebP etc.
                    "data": img_bytes,
                }
            )

        return parts

    # ------------------------------------------------------------------
    # Appel API Gemini
    # ------------------------------------------------------------------

    def _call_api(
        self,
        image_paths: List[Path],
        profile: AnalysisProfile,
        ui_data: Dict[str, Any] | None = None,
    ) -> str:
        """
        Appelle l'API Gemini en mode "simple" :
        - pas de response_schema
        - pas de response_mime_type
        - on s'appuie sur le prompt pour exiger un JSON

        On attend donc que response.text soit une chaîne JSON (éventuellement encadrée
        par des ```json ... ```).
        """
        parts = self._build_parts(image_paths, profile, ui_data=ui_data)

        logger.debug(
            "Appel API Gemini (model=%s, nb_images=%d)...",
            self._model_name,
            len(image_paths),
        )

        try:
            model = genai.GenerativeModel(self._model_name)

            response = model.generate_content(
                contents=parts,
                generation_config={
                    "temperature": 0.2,
                    "top_p": 0.9,
                },
            )

            text = response.text
            if not text:
                raise GeminiClientError("Réponse Gemini vide (text=None ou '').")

            return text

        except GeminiClientError:
            raise
        except Exception as exc:
            logger.exception("Erreur appel API Gemini.")
            raise GeminiClientError(f"Erreur API Gemini: {exc}") from exc
