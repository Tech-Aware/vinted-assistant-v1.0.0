# infrastructure/gemini_client.py

from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from typing import TYPE_CHECKING
import warnings

# Suppress ALL warnings during legacy google.generativeai import
# (package is deprecated but kept as fallback when google.genai unavailable)
_original_filters = warnings.filters[:]
warnings.simplefilter("ignore")
import google.generativeai as genai  # legacy (fallback)
warnings.filters[:] = _original_filters

import json

try:  # structured outputs via Google GenAI SDK
    from google import genai as genai_sdk
    from google.genai import types as genai_types
except Exception:  # pragma: no cover
    genai_sdk = None
    genai_types = None

try:  # pragma: no cover - dépendance optionnelle en environnement restreint
    from jsonschema import ValidationError, validate
except Exception:  # pragma: no cover - fallback local si jsonschema absent
    ValidationError = None

    def validate(instance: dict, schema: dict) -> None:  # type: ignore
        """Fallback no-op si jsonschema n'est pas disponible."""
        return

# Retry avec backoff exponentiel pour les appels API
try:
    from tenacity import (
        retry,
        stop_after_attempt,
        wait_exponential,
        retry_if_exception_type,
        before_sleep_log,
    )
    TENACITY_AVAILABLE = True
except ImportError:
    TENACITY_AVAILABLE = False
    # Fallback: décorateur no-op si tenacity n'est pas installé
    def retry(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    stop_after_attempt = lambda x: None
    wait_exponential = lambda **kwargs: None
    retry_if_exception_type = lambda x: None
    before_sleep_log = lambda logger, level: None

from config.settings import Settings
from domain.ai_provider import AIListingProvider, AIProviderName
from domain.json_utils import safe_json_parse
from domain.ocr_provider import OCRProvider, OCRProviderError, OCRResult
from domain.models import VintedListing
from domain.path_validator import validate_image_paths, PathValidationError
from domain.prompt import PROMPT_CONTRACT
from domain.templates import AnalysisProfile
from domain.normalizer import normalize_and_postprocess
from domain.schema_structured import make_structured_output_schema
from domain.ai_status import AIResultStatus

if TYPE_CHECKING:  # pragma: no cover
    from infrastructure.google_vision_ocr import GoogleVisionOCRProvider

logger = logging.getLogger(__name__)


class GeminiClientError(RuntimeError):
    """
    Exception fonctionnelle pour les erreurs Gemini.
    """


class GeminiRetryableError(GeminiClientError):
    """
    Exception pour les erreurs Gemini récupérables (timeout, rate limit, erreur réseau).
    Ces erreurs peuvent être réessayées avec backoff exponentiel.
    """


# Décorateur de retry pour les appels API Gemini
def _create_retry_decorator():
    """Crée un décorateur de retry avec backoff exponentiel."""
    if not TENACITY_AVAILABLE:
        return lambda func: func

    return retry(
        stop=stop_after_attempt(3),  # Max 3 tentatives
        wait=wait_exponential(multiplier=1, min=2, max=30),  # 2s, 4s, 8s... max 30s
        retry=retry_if_exception_type(GeminiRetryableError),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


gemini_retry = _create_retry_decorator()


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

        self._structured_client = None
        if genai_sdk is not None:
            try:
                self._structured_client = genai_sdk.Client(api_key=settings.gemini_api_key)
                logger.info("Google GenAI SDK client initialisé (structured outputs activable).")
            except Exception as exc:
                logger.warning(
                    "Impossible d'initialiser Google GenAI SDK (structured outputs). Fallback legacy. (%s)",
                    exc,
                    exc_info=True,
                )
                self._structured_client = None
        else:
            logger.info("google-genai non installé: structured outputs indisponible (fallback legacy).")

        try:
            if ocr_provider is not None:
                self._ocr = ocr_provider
            else:
                from infrastructure.google_vision_ocr import GoogleVisionOCRProvider  # lazy import

                self._ocr = GoogleVisionOCRProvider()
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

        ui_data = dict(ui_data or {})
        paths: List[Path] = [Path(p) for p in image_paths]

        if not paths:
            raise GeminiClientError("Aucune image fournie à Gemini.generate_listing.")

        # Validation sécurisée des chemins (prévention path traversal)
        try:
            paths = validate_image_paths(paths, check_exists=True, check_extension=True)
        except PathValidationError as exc:
            logger.error("Validation des chemins d'images échouée: %s", exc)
            raise GeminiClientError(f"Chemins d'images invalides: {exc}") from exc

        logger.info(
            "Gemini.generate_listing(images=%s, profile='%s')",
            [str(p) for p in paths],
            profile.name.value,
        )

        # Étape 1: audit + sanitization du schema pour structured outputs (pas encore utilisé dans l'appel Gemini)
        structured_schema = self._prepare_structured_schema(profile)

        ocr_paths: List[Path] = []
        ocr_text: str = ""
        ocr_payload: str = ""
        ocr_paths_raw = ui_data.get("ocr_image_paths", [])

        use_structured = structured_schema is not None and getattr(self, "_structured_client", None) is not None

        try:
            ocr_paths = [Path(p) for p in ocr_paths_raw]
            if ocr_paths:
                logger.info("Extraction OCR demandée pour %d image(s).", len(ocr_paths))
                ocr_result = self._ocr.extract_text(ocr_paths)
                ocr_text = ocr_result.full_text or ""
                structured = getattr(ocr_result, "structured", None)
                if structured:
                    ocr_payload = structured.filtered_text
                    try:
                        ui_data["ocr_structured"] = structured.to_dict()
                    except Exception as exc:  # pragma: no cover - defensive
                        logger.warning(
                            "Impossible de sérialiser l'OCR structuré: %s", exc, exc_info=True
                        )
                    logger.info(
                        "Extraction OCR effectuée avec structuration: %d caractère(s) bruts, %d ligne(s) filtrées.",
                        len(ocr_text),
                        len(structured.debug_lines),
                    )
                    logger.debug("Texte OCR cadré (tronqué): %s", ocr_payload[:800])

                    # --- SKU candidates depuis l'OCR structuré (pour le normalizer)
                    try:
                        ui_data["_ocr_sku_candidates"] = list(structured.sku_candidates or [])
                    except Exception:
                        ui_data["_ocr_sku_candidates"] = []

                else:
                    ocr_payload = self._truncate_text(ocr_text)
                    logger.info(
                        "Extraction OCR effectuée: %d caractère(s) agrégés (sans structuration).",
                        len(ocr_text),
                    )
                    if ocr_text:
                        logger.debug("Texte OCR brut (tronqué): %s", ocr_payload[:800])
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

        logger.info(
            "Mode IA (profil=%s): structured_outputs=%s, ocr=%s, nb_images_gemini=%d",
            profile.name.value,
            use_structured,
            bool(ocr_payload),
            len(gemini_paths),
        )

        try:
            try:
                raw_text = self._call_api(
                    image_paths=gemini_paths,
                    profile=profile,
                    ui_data=ui_data,
                    ocr_text=ocr_payload,
                    structured_schema=structured_schema,
                )
            except GeminiClientError as exc:
                # Retry unique uniquement en structured outputs, sur erreurs plausiblement transitoires
                if use_structured:
                    logger.warning(
                        "Echec structured outputs (profil=%s). Retry 1x. Cause=%s",
                        profile.name.value,
                        exc,
                    )
                    raw_text = self._call_api(
                        image_paths=gemini_paths,
                        profile=profile,
                        ui_data=ui_data,
                        ocr_text=ocr_payload,
                        structured_schema=structured_schema,
                    )
                else:
                    raise

            if not raw_text:
                logger.error("Réponse IA vide (profil=%s).", profile.name.value)
                return self._build_fallback_listing(
                    reason="Réponse IA vide",
                    raw_text=None,
                    ai_status=AIResultStatus.EMPTY_RESPONSE,
                )

            # Parse
            if use_structured:
                parsed = self._parse_structured_json(raw_text, profile.name.value)
            else:
                parsed = safe_json_parse(raw_text)

            ai_meta = parsed.get("ai") if isinstance(parsed, dict) else None
            ai_status = None
            if isinstance(ai_meta, dict):
                ai_status = (ai_meta.get("status") or "").strip().lower()

            if use_structured and (not isinstance(ai_meta, dict) or not ai_status):
                logger.error("Structured JSON invalide: bloc ai manquant (profil=%s).", profile.name.value)
                return self._build_fallback_listing(
                    reason="Structured JSON: bloc ai manquant",
                    raw_text=raw_text,
                    ai_status=AIResultStatus.SCHEMA_ERROR,
                )

            if ai_status and ai_status != "ok":
                reason = ai_meta.get("reason") if isinstance(ai_meta, dict) else None
                missing = ai_meta.get("missing") if isinstance(ai_meta, dict) else None
                logger.warning(
                    "IA non-ok (profil=%s): status=%s missing=%s reason=%s",
                    profile.name.value,
                    ai_status,
                    missing,
                    reason,
                )
                return self._build_fallback_listing(
                    reason=f"IA status={ai_status} missing={missing} reason={reason}",
                    raw_text=raw_text,
                    ai_status=AIResultStatus.FALLBACK_USED,
                )

            if not parsed:
                logger.warning(
                    "Réponse IA illisible (profil=%s, structured=%s).",
                    profile.name.value,
                    use_structured,
                )
                return self._build_fallback_listing(
                    reason="JSON IA introuvable/invalide",
                    raw_text=raw_text,
                    ai_status=AIResultStatus.PARSE_ERROR,
                )

            # Validation schema
            self._validate_json(parsed, profile, strict=use_structured)

            # --- Injecte les candidates OCR dans ai_data pour le normalizer
            try:
                candidates = ui_data.get("_ocr_sku_candidates")
                if isinstance(parsed, dict) and isinstance(candidates, list) and candidates:
                    parsed["_ocr_sku_candidates"] = candidates
            except Exception:
                pass


            # Normalisation + génération finale
            normalized = normalize_and_postprocess(
                ai_data=parsed,
                profile_name=profile.name,
                ui_data=ui_data,
            )

            listing = VintedListing.from_dict(normalized)
            logger.info("Annonce générée (profil=%s): '%s'.", profile.name.value, listing.title)
            return listing

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

    def _prepare_structured_schema(self, profile: AnalysisProfile) -> Optional[Dict[str, Any]]:
        """
        Prépare une version compatible structured outputs du json_schema du profil.
        Étape 1: audit + sanitization + logs uniquement. On ne l'utilise pas encore pour l'appel Gemini.
        """
        try:
            schema = getattr(profile, "json_schema", None)
            profile_name = getattr(getattr(profile, "name", None), "value", "unknown")

            if not isinstance(schema, dict):
                logger.debug("Structured schema: aucun json_schema dict pour profile=%s", profile_name)
                return None

            sanitized, changes, unsupported = make_structured_output_schema(
                schema,
                schema_name=profile_name,
                enforce_no_extra_keys=True,
                strict=False,
            )

            # Contexte utile au niveau client (on évite de spammer si tout est clean)
            if changes:
                logger.info(
                    "Structured schema ready (%s): %d changement(s) appliqué(s).",
                    profile_name,
                    len(changes),
                )

            if unsupported:
                logger.warning(
                    "Structured schema (%s): %d keyword(s) non supporté(s) détecté(s).",
                    profile_name,
                    len(set(k for _, k in unsupported)),
                )

            return sanitized

        except Exception as exc:
            logger.warning(
                "Erreur lors de la préparation du schema structured outputs (%s): %s",
                getattr(getattr(profile, "name", None), "value", "unknown"),
                exc,
                exc_info=True,
            )
            return None

    @staticmethod
    def _guess_mime_type(path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if suffix == ".png":
            return "image/png"
        if suffix == ".webp":
            return "image/webp"
        # fallback raisonnable
        return "image/jpeg"

    def _build_contents_for_structured(
        self,
        image_paths: List[Path],
        profile: AnalysisProfile,
        ui_data: Dict[str, Any] | None = None,
        ocr_text: str | None = None,
    ) -> List[Any]:
        """
        Construit 'contents' pour google-genai (GenAI SDK):
        - 1 part texte (prompt complet avec OCR_TEXT injecté)
        - N parts images via types.Part.from_bytes
        """
        if genai_types is None:
            raise GeminiClientError("google-genai/types indisponible.")

        prompt_template = PROMPT_CONTRACT + "\n\n" + profile.prompt_suffix
        full_prompt = prompt_template.replace("{OCR_TEXT}", ocr_text or "")

        # measurement_mode (même logique que ton _build_parts actuel)
        try:
            measurement_mode = (ui_data or {}).get("measurement_mode")
            if measurement_mode:
                logger.debug("Gemini structured: measurement_mode=%s", measurement_mode)
                full_prompt += f"\n\nMODE_RELEVE: {measurement_mode}"
        except Exception as exc:  # pragma: no cover
            logger.warning("Gemini structured: lecture measurement_mode impossible (%s)", exc)

        contents: List[Any] = [full_prompt]

        for p in image_paths:
            try:
                data = p.read_bytes()
                mime_type = self._guess_mime_type(p)
                contents.append(genai_types.Part.from_bytes(data=data, mime_type=mime_type))
            except Exception as exc:
                logger.warning(
                    "Impossible de lire l'image pour Gemini structured (%s): %s",
                    p,
                    exc,
                    exc_info=True,
                )

        return contents

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

    @staticmethod
    def _is_retryable_error(exc: Exception) -> bool:
        """Détermine si une exception est récupérable (timeout, rate limit, réseau)."""
        error_str = str(exc).lower()
        retryable_patterns = [
            "timeout",
            "rate limit",
            "quota",
            "503",
            "502",
            "504",
            "connection",
            "network",
            "temporarily unavailable",
            "resource exhausted",
            "deadline exceeded",
        ]
        return any(pattern in error_str for pattern in retryable_patterns)

    @gemini_retry
    def _call_api(
            self,
            image_paths: List[Path],
            profile: AnalysisProfile,
            ui_data: Dict[str, Any] | None = None,
            ocr_text: str | None = None,
            structured_schema: Dict[str, Any] | None = None,
    ) -> str:
        """
        Appelle Gemini avec retry automatique sur erreurs récupérables.

        Priorité: structured outputs (google-genai) si dispo + schema.
        Fallback: legacy google-generativeai en prompt-only.

        Le décorateur @gemini_retry réessaie automatiquement en cas de:
        - Timeout
        - Rate limit (429)
        - Erreurs réseau temporaires
        - Erreurs serveur (502, 503, 504)
        """
        profile_name = getattr(getattr(profile, "name", None), "value", "unknown")

        # ---------------------------
        # 1) Structured outputs (SDK google-genai)
        # ---------------------------
        if self._structured_client is not None and structured_schema is not None and genai_types is not None:
            try:
                contents = self._build_contents_for_structured(
                    image_paths=image_paths,
                    profile=profile,
                    ui_data=ui_data,
                    ocr_text=ocr_text,
                )

                logger.info(
                    "Appel Gemini structured outputs (model=%s, profile=%s, nb_images=%d, ocr=%s).",
                    self._model_name,
                    profile_name,
                    len(image_paths),
                    bool(ocr_text),
                )
                logger.debug("Structured schema utilisé (%s): keys=%s", profile_name, list(structured_schema.keys()))

                config = genai_types.GenerateContentConfig(
                    temperature=0.2,
                    top_p=0.9,
                    response_mime_type="application/json",
                    response_json_schema=structured_schema,
                )

                response = self._structured_client.models.generate_content(
                    model=self._model_name,
                    contents=contents,
                    config=config,
                )

                text = getattr(response, "text", None)
                if not text:
                    raise GeminiClientError("Réponse Gemini structured vide (text=None ou '').")

                return text

            except GeminiClientError:
                raise
            except Exception as exc:
                # Si c'est une erreur récupérable, relancer pour retry
                if self._is_retryable_error(exc):
                    logger.warning(
                        "Erreur récupérable Gemini structured (%s): %s. Retry...",
                        profile_name,
                        exc,
                    )
                    raise GeminiRetryableError(f"Erreur Gemini récupérable: {exc}") from exc
                logger.warning(
                    "Echec appel Gemini structured outputs (%s). Fallback legacy. (%s)",
                    profile_name,
                    exc,
                    exc_info=True,
                )

        else:
            if structured_schema is not None and self._structured_client is None:
                logger.info(
                    "Structured schema prêt (%s) mais client google-genai indisponible -> fallback legacy.",
                    profile_name,
                )

        # ---------------------------
        # 2) Fallback legacy (prompt-only)
        # ---------------------------
        try:
            parts = self._build_parts(
                image_paths,
                profile,
                ui_data=ui_data,
                ocr_text=ocr_text,
            )

            logger.info(
                "Appel Gemini legacy (prompt-only) (model=%s, profile=%s, nb_images=%d, ocr=%s).",
                self._model_name,
                profile_name,
                len(image_paths),
                bool(ocr_text),
            )

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
            # Si c'est une erreur récupérable, relancer pour retry
            if self._is_retryable_error(exc):
                logger.warning(
                    "Erreur récupérable Gemini legacy: %s. Retry...",
                    exc,
                )
                raise GeminiRetryableError(f"Erreur Gemini récupérable: {exc}") from exc
            logger.exception("Erreur appel API Gemini (legacy).")
            raise GeminiClientError(f"Erreur API Gemini: {exc}") from exc

    # ------------------------------------------------------------------
    # Validation + fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _truncate_text(text: str, max_len: int = 2000) -> str:
        if not text:
            return ""
        if len(text) <= max_len:
            return text
        return text[:max_len] + "…"

    @staticmethod
    def _build_noop_ocr() -> OCRProvider:
        class _NoOpOCR(OCRProvider):
            def extract_text(self, image_paths: Sequence[Path]) -> OCRResult:  # type: ignore[override]
                logger.info("OCR noop utilisé, aucune extraction effectuée (%d image(s)).", len(image_paths))
                return OCRResult(full_text="", per_image_text={}, structured=None)

        return _NoOpOCR()

    def _validate_json(
            self,
            payload: Dict[str, Any],
            profile: AnalysisProfile,
            *,
            strict: bool,
    ) -> None:
        """
        Valide le JSON contre le schéma du profil.

        - strict=True : lève GeminiClientError si non conforme (mode structured outputs)
        - strict=False : warning uniquement (mode legacy prompt-only)
        """
        try:
            validate(instance=payload, schema=profile.json_schema)
            logger.info("Validation JSON Gemini OK (profil=%s).", profile.name.value)
            return

        except Exception as exc:
            msg = getattr(exc, "message", str(exc))
            if strict:
                logger.error(
                    "JSON Gemini non conforme au schéma (profil=%s) [STRICT]: %s",
                    profile.name.value,
                    msg,
                )
                raise GeminiClientError(f"Schema validation failed ({profile.name.value}): {msg}") from exc

            logger.warning(
                "JSON Gemini non conforme au schéma (profil=%s) [non-strict]: %s",
                profile.name.value,
                msg,
            )

    def _build_fallback_listing(
            self,
            reason: str,
            raw_text: Optional[str],
            ai_status: AIResultStatus = AIResultStatus.FALLBACK_USED,
    ) -> VintedListing:
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
            "features": {"error": reason, "ai_status": ai_status.value},
            "description_raw": raw_text,
            "fallback_reason": reason,
        }
        logger.warning("Construction fallback (ai_status=%s): %s", ai_status.value, reason)
        try:
            return VintedListing.from_dict(fallback_data)
        except Exception as exc:  # pragma: no cover - robustesse
            logger.error(
                "Echec de construction du fallback VintedListing (%s)",
                exc,
                exc_info=True,
            )
            raise GeminiClientError(reason) from exc

    @staticmethod
    def _parse_structured_json(raw_text: str, profile_name: str) -> Dict[str, Any]:
        """
        Parsing strict pour structured outputs.
        """
        try:
            obj = json.loads(raw_text)
            if not isinstance(obj, dict):
                raise GeminiClientError(
                    f"Structured JSON invalide: attendu object/dict, obtenu {type(obj)}"
                )
            return obj
        except GeminiClientError:
            raise
        except Exception as exc:
            logger.warning(
                "Parsing structured JSON échoué (profil=%s): %s",
                profile_name,
                exc,
                exc_info=True,
            )
            raise GeminiClientError(f"Structured JSON parse error ({profile_name}): {exc}") from exc

