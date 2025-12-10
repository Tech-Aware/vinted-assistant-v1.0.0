# infrastructure/openai_client.py

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Dict, Any, List, Union

import requests

from config.settings import Settings
from domain.ai_provider import AIListingProvider, AIProviderName
from domain.models import VintedListing
from domain.templates import AnalysisProfile
from domain.prompt import PROMPT_CONTRACT
from domain.json_utils import safe_json_parse
from domain.normalizer import normalize_and_postprocess

logger = logging.getLogger(__name__)


class OpenAIClientError(RuntimeError):
    """
    Exception fonctionnelle pour les erreurs OpenAI.
    """


class OpenAIListingClient(AIListingProvider):
    """
    Implémentation du provider IA pour OpenAI (modèle vision, ex. gpt-4o-mini).

    Analyse une ou plusieurs images d’un même article + un profil d'analyse
    et renvoie un VintedListing.
    """

    def __init__(self, settings: Settings) -> None:
        logger.debug("Initialisation OpenAIListingClient...")
        if not settings.openai_api_key:
            raise OpenAIClientError("OPENAI_API_KEY absente.")

        self.api_key = settings.openai_api_key
        self.model = settings.openai_model
        self.endpoint = "https://api.openai.com/v1/chat/completions"

        logger.info("OpenAIListingClient initialisé (model=%s).", self.model)

    # ------------------------------------------------------------------
    # Nom du provider
    # ------------------------------------------------------------------

    @property
    def name(self) -> AIProviderName:
        return AIProviderName.OPENAI

    # ------------------------------------------------------------------
    # Méthode principale
    # ------------------------------------------------------------------

    def generate_listing(
        self,
        image_paths: Union[Path, List[Path]],
        profile: AnalysisProfile,
        ui_data: Dict[str, Any] | None = None,
    ) -> VintedListing:
        """
        Analyse une ou plusieurs images locales d’un même article + profil,
        renvoie un VintedListing.

        - image_paths : Path unique ou liste de Path
        - profile     : profil d'analyse (template prompt spécifique à l'article)
        - ui_data     : données saisies dans l’UI (size_fr, size_us, sku, corrections...), optionnel
        """
        # Normaliser en liste
        if isinstance(image_paths, Path):
            image_paths = [image_paths]

        logger.info(
            "OpenAI.generate_listing(images=%s, profile='%s')",
            [str(p) for p in image_paths],
            profile.name.value,
        )

        try:
            # 1) Encodage de toutes les images
            images_b64 = [self._encode_image(p) for p in image_paths]

            # 2) Construction du payload (prompt contractuel + profil + multi-images)
            payload = self._build_payload(images_b64, profile)

            # 3) Appel API OpenAI
            response_json = self._call_api(payload)

            # 4) Récupération du texte (JSON brut) renvoyé par le modèle
            raw_text = self._extract_json(response_json)

            # 5) Parsing “tolérant” du JSON
            parsed = safe_json_parse(raw_text)
            if parsed is None:
                raise OpenAIClientError(
                    "Réponse OpenAI illisible (JSON invalide ou introuvable)."
                )

            # 6) Post-traitement + normalisation (titre JEAN_LEVIS, mapping clés, etc.)
            normalized = normalize_and_postprocess(
                ai_data=parsed,
                profile_name=profile.name,  # ex: AnalysisProfileName.JEAN_LEVIS
                ui_data=ui_data,            # pour l’instant tu peux appeler avec None
            )

            # 7) Construction du modèle de domaine
            listing = VintedListing.from_dict(normalized)
            logger.info("Annonce OpenAI générée: '%s'.", listing.title)
            return listing

        except OpenAIClientError:
            # On laisse remonter les erreurs fonctionnelles déjà formatées
            raise
        except Exception as exc:
            logger.exception("Erreur inattendue OpenAI.generate_listing.")
            raise OpenAIClientError(f"Erreur inattendue: {exc}") from exc

    # ------------------------------------------------------------------
    # Encodage image
    # ------------------------------------------------------------------

    def _encode_image(self, image_path: Path) -> str:
        logger.debug("Encodage image OpenAI...")
        if not image_path.exists():
            logger.error("Image introuvable: %s", image_path)
            raise OpenAIClientError(f"Image introuvable: {image_path}")

        try:
            with open(image_path, "rb") as f:
                binary = f.read()
            encoded = base64.b64encode(binary).decode("utf-8")
            logger.debug("Encodage image OK (%d caractères).", len(encoded))
            return encoded
        except Exception as exc:
            logger.exception("Erreur encodage image OpenAI.")
            raise OpenAIClientError(f"Erreur encodage image: {exc}") from exc

    # ------------------------------------------------------------------
    # Construction du payload
    # ------------------------------------------------------------------

    def _build_payload(
        self,
        images_b64: List[str],
        profile: AnalysisProfile,
    ) -> Dict[str, Any]:
        """
        Construit le payload JSON pour /v1/chat/completions avec :
        - message système : contrat + suffixe de profil
        - message user : consignes + toutes les images
        - response_format json_object (OpenAI formate la sortie en JSON)
        """
        try:
            # Prompt système = contrat général + instructions spécifiques au profil
            full_prompt = PROMPT_CONTRACT + "\n\n" + profile.prompt_suffix

            # Contenu utilisateur : texte + toutes les images
            user_content: List[Dict[str, Any]] = [
                {
                    "type": "text",
                    "text": (
                        "Analyse l'ensemble des images ci-dessous. "
                        "Il s'agit du même vêtement photographié sous différents angles, "
                        "avec des étiquettes et des mesures à plat. "
                        "Génère une annonce Vinted (titre + description) en respectant "
                        "strictement le contrat JSON décrit dans le message système."
                    ),
                }
            ]

            for img_b64 in images_b64:
                user_content.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{img_b64}",
                        },
                    }
                )

            payload: Dict[str, Any] = {
                "model": self.model,
                # On demande à OpenAI de formater la sortie en JSON,
                # mais on ne lui passe plus de json_schema complexe.
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": [
                            {
                                "type": "text",
                                "text": full_prompt,
                            }
                        ],
                    },
                    {
                        "role": "user",
                        "content": user_content,
                    },
                ],
                "temperature": 0.2,
                "top_p": 1.0,
            }

            logger.debug(
                "Payload OpenAI construit (%d images, model=%s).",
                len(images_b64),
                self.model,
            )
            return payload

        except Exception as exc:
            logger.exception("Erreur build payload OpenAI.")
            raise OpenAIClientError(f"Erreur build payload: {exc}") from exc

    # ------------------------------------------------------------------
    # Appel HTTP
    # ------------------------------------------------------------------

    def _call_api(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.debug("Appel API OpenAI...")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                self.endpoint,
                headers=headers,
                json=payload,
                timeout=30,
            )

            if not response.ok:
                logger.error(
                    "Erreur HTTP OpenAI (%d): %s",
                    response.status_code,
                    response.text,
                )
                raise OpenAIClientError(
                    f"Erreur API OpenAI (HTTP {response.status_code}): {response.text}"
                )

            r_json = response.json()
            logger.debug("OpenAI réponse reçue (tronc.): %s", str(r_json)[:400])
            return r_json

        except OpenAIClientError:
            raise
        except requests.exceptions.Timeout:
            logger.error("Timeout OpenAI.")
            raise OpenAIClientError("Timeout API OpenAI.")
        except requests.exceptions.RequestException as exc:
            logger.exception("Erreur réseau OpenAI.")
            raise OpenAIClientError(f"Erreur réseau: {exc}") from exc
        except Exception as exc:
            logger.exception("Erreur inattendue appel API OpenAI.")
            raise OpenAIClientError(f"Erreur API OpenAI: {exc}") from exc

    # ------------------------------------------------------------------
    # Extraction JSON (texte brut renvoyé par OpenAI)
    # ------------------------------------------------------------------

    def _extract_json(self, api_response: Dict[str, Any]) -> str:
        """
        Récupère le texte brut généré par OpenAI (qui doit contenir le JSON).

        chat/completions -> choices[0].message.content
        """
        try:
            choices = api_response.get("choices")
            if not choices:
                raise OpenAIClientError("Réponse vide OpenAI (pas de choices).")

            message = choices[0].get("message")
            if not message:
                raise OpenAIClientError("Réponse OpenAI sans message.")

            content = message.get("content")
            if not content:
                raise OpenAIClientError("Réponse OpenAI sans content.")

            logger.debug("JSON brut OpenAI (texte): %s", content)
            # On renvoie le texte brut pour le laisser à safe_json_parse()
            return content

        except OpenAIClientError:
            raise
        except Exception as exc:
            logger.exception("Erreur extraction JSON OpenAI.")
            raise OpenAIClientError(f"Erreur extraction JSON: {exc}") from exc
