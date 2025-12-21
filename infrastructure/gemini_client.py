# infrastructure/gemini_client.py

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import google.generativeai as genai
from jsonschema import ValidationError, validate

from config.settings import Settings
from domain.ai_provider import AIListingProvider, AIProviderName
from domain.json_utils import safe_json_parse
from domain.ocr_provider import OCRProvider, OCRProviderError, OCRResult
from domain.models import VintedListing
from domain.prompt import PROMPT_CONTRACT
from domain.templates import AnalysisProfile
from domain.normalizer import normalize_and_postprocess
from infrastructure.google_vision_ocr import GoogleVisionOCRProvider

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

    def __init__(self, settings: Settings, ocr_provider: OCRProvider | None = None) -> None:
        logger.debug("Initialisation GeminiListingClient...")
        if not settings.gemini_api_key:
            raise GeminiClientError("GEMINI_API_KEY absente.")

        genai.configure(api_key=settings.gemini_api_key)
        self._model_name = self._normalize_model_name(settings.gemini_model)
        try:
            self._ocr: OCRProvider = ocr_provider or GoogleVisionOCRProvider()
        except Exception as exc:
            logger.warning(
                "OCR non disponible lors de l'initialisation (%s). Passage en mode dégradé sans OCR.",
                exc,
                exc_info=True,
            )
            self._ocr = self._build_noop_ocr()

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
        ui_data: Optional[Dict[str, Any]] = None,
    ) -> VintedListing:
        """
        Analyse UNE OU PLUSIEURS images (toutes du même article) + profil,
        renvoie un VintedListing.
        """
        paths: List[Path] = [Path(p) for p in image_paths]

        if not paths:
            raise GeminiClientError("Aucune image fournie à Gemini.generate_listing.")

        logger.info(
            "Gemini.generate_listing(images=%s, profile='%s')",
            [str(p) for p in paths],
            profile.name.value,
        )

        ocr_paths: List[Path] = []
        ocr_text: str = ""
        ocr_paths_raw = (ui_data or {}).get("ocr_image_paths", [])
        try:
            ocr_paths = [Path(p) for p in ocr_paths_raw]
            if ocr_paths:
                logger.info("Extraction OCR demandée pour %d image(s).", len(ocr_paths))
                ocr_result = self._ocr.extract_text(ocr_paths)
                ocr_text = ocr_result.full_text or ""
                logger.info(
                    "Extraction OCR effectuée: %d caractère(s) agrégés.",
                    len(ocr_text),
                )
                if ocr_text:
                    logger.debug("Texte OCR (tronqué): %s", ocr_text[:600])
        except OCRProviderError as exc_ocr:
            logger.warning("OCR indisponible: %s", exc_ocr)
        except Exception as exc_ocr:  # pragma: no cover - robustesse
            logger.warning(
                "Erreur inattendue pendant l'OCR: %s",
                exc_ocr,
                exc_info=True,
            )

        gemini_paths: List[Path]
        if ocr_paths:
            ocr_set = {str(p) for p in ocr_paths}
            gemini_paths = [p for p in paths if str(p) not in ocr_set]
            if not gemini_paths:
                logger.warning(
                    "Toutes les images ont été marquées OCR : fallback envoi complet à Gemini."
                )
                gemini_paths = paths
        else:
            gemini_paths = paths

        try:
            raw_text = self._call_api(
                gemini_paths,
                profile,
                ui_data=ui_data,
                ocr_text=ocr_text,
            )
            logger.debug("Gemini brut: %s", raw_text[:400])

            # JSON robuste (si jamais il y a des ```json ....```, safe_json_parse gère)
            parsed: Dict[str, Any] = safe_json_parse(raw_text)
            if parsed is None:
                logger.warning(
                    "Réponse Gemini illisible (JSON invalide ou introuvable). Utilisation d'un fallback."
                )
                return self._build_fallback_listing(
                    reason="JSON Gemini introuvable ou invalide",
                    raw_text=raw_text,
                )

            self._validate_json(parsed, profile)

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
            return self._build_fallback_listing(
                reason=f"Erreur inattendue: {exc}",
                raw_text=None,
            )

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
        ocr_text: str | None = None,
    ) -> List[Any]:
        """
        Construit une liste de "parts" pour google-generativeai :

        - d'abord le texte (PROMPT_CONTRACT + prompt_suffix)
        - ensuite toutes les images (SKU, vues, étiquettes, mesures) du même article
        """
        # Texte : contrat global + profil spécialisé
        prompt_template = PROMPT_CONTRACT + "\n\n" + profile.prompt_suffix
        full_prompt = prompt_template.replace("{OCR_TEXT}", ocr_text or "")

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
        ocr_text: str | None = None,
    ) -> str:
        """
        Appelle l'API Gemini en mode "simple" :
        - pas de response_schema
        - pas de response_mime_type
        - on s'appuie sur le prompt pour exiger un JSON

        On attend donc que response.text soit une chaîne JSON (éventuellement encadrée
        par des ```json ... ```).
        """
        parts = self._build_parts(
            image_paths,
            profile,
            ui_data=ui_data,
            ocr_text=ocr_text,
        )

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

    # ------------------------------------------------------------------
    # Validation + fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _build_noop_ocr() -> OCRProvider:
        class _NoOpOCR(OCRProvider):
            def extract_text(self, image_paths: Sequence[Path]) -> OCRResult:  # type: ignore[override]
                logger.info("OCR noop utilisé, aucune extraction effectuée (%d image(s)).", len(image_paths))
                return OCRResult(full_text="", per_image_text={})

        return _NoOpOCR()

    def _validate_json(self, payload: Dict[str, Any], profile: AnalysisProfile) -> None:
        """
        Valide le JSON Gemini contre le schéma attendu du profil.
        Ne lève pas d'exception bloquante mais journalise les incohérences.
        """
        try:
            validate(instance=payload, schema=profile.json_schema)
            logger.info("Validation JSON Gemini réussie (profil=%s).", profile.name.value)
        except ValidationError as exc:
            logger.warning(
                "JSON Gemini non conforme au schéma (%s): %s",
                profile.name.value,
                exc.message,
            )
            try:
                required = profile.json_schema.get("required", [])
                for key in required:
                    payload.setdefault(key, None)
            except Exception as nested_exc:  # pragma: no cover - robustesse
                logger.debug(
                    "Impossible de compléter les champs requis après validation: %s",
                    nested_exc,
                )

    def _build_fallback_listing(self, reason: str, raw_text: Optional[str]) -> VintedListing:
        """
        Produit une annonce minimale pour éviter tout crash UI.
        """
        logger.warning("Construction d'une annonce de secours: %s", reason)
        if raw_text:
            logger.debug(
                "Contenu brut Gemini (tronqué à 400 chars) pour diagnostic fallback: %s",
                raw_text[:400],
            )
        fallback_data: Dict[str, Any] = {
            "title": "Annonce à compléter",
            "description": "Erreur d'analyse : photos/étiquette à vérifier.",
            "brand": None,
            "style": None,
            "pattern": None,
            "neckline": None,
            "season": None,
            "defects": None,
            "features": {"error": reason},
            "description_raw": raw_text,
            "fallback_reason": reason,
        }
        try:
            return VintedListing.from_dict(fallback_data)
        except Exception as exc:  # pragma: no cover - robustesse
            logger.error(
                "Echec de construction du fallback VintedListing (%s)",
                exc,
                exc_info=True,
            )
            raise GeminiClientError(reason) from exc
