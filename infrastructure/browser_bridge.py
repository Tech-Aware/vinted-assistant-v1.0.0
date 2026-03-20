# infrastructure/browser_bridge.py
"""
Serveur HTTP pour la communication entre l'app Python et l'extension Chrome.

Architecture :
- Polling HTTP (pas de WebSocket) pour compatibilité maximale (Chromebook, réseaux restreints)
- Comportement humain simulé côté extension (délais, frappe progressive)
- Une seule donnée à la fois (pas de queue/rafale)

Endpoints:
- GET  /status   : Diagnostic - vérifie que le serveur est actif
- GET  /check    : Récupère les données à transférer (titre/description)
- POST /confirm  : Confirme que les données ont été reçues par l'extension
- GET  /profiles : Liste des profils d'analyse disponibles
- POST /generate : Génère une annonce à partir d'images + profil + ui_data
- POST /shutdown : Arrête le serveur proprement
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

from aiohttp import web

logger = logging.getLogger(__name__)

# Port par défaut (doit correspondre à l'extension Chrome)
DEFAULT_PORT = 8765


@dataclass
class TransferData:
    """Données à transférer vers Vinted."""
    title: str = ""
    description: str = ""
    pending: bool = False  # True si des données attendent d'être récupérées


@dataclass
class BrowserBridge:
    """
    Pont HTTP entre l'application Python et l'extension Chrome.

    Utilisation :
        bridge = BrowserBridge()
        bridge.start()  # Démarre le serveur en arrière-plan

        # Quand l'utilisateur clique sur "Transférer"
        bridge.set_transfer_data("Mon titre", "Ma description")

        # L'extension Chrome récupère les données via polling
        # puis confirme avec POST /confirm

        bridge.stop()  # Arrête le serveur proprement
    """

    port: int = DEFAULT_PORT
    on_transfer_complete: Optional[Callable[[], None]] = None
    provider: Optional[Any] = None  # AIListingProvider (optional, for /generate)

    # État interne
    _data: TransferData = field(default_factory=TransferData)
    _server_thread: Optional[threading.Thread] = None
    _loop: Optional[asyncio.AbstractEventLoop] = None
    _runner: Optional[web.AppRunner] = None
    _running: bool = False

    def set_transfer_data(self, title: str, description: str) -> None:
        """
        Définit les données à transférer vers Vinted.
        L'extension Chrome les récupérera via polling sur /check.
        """
        self._data.title = title
        self._data.description = description
        self._data.pending = True
        logger.info(
            "Données de transfert définies (titre: %d chars, description: %d chars)",
            len(title), len(description)
        )

    def clear_transfer_data(self) -> None:
        """Efface les données de transfert."""
        self._data.title = ""
        self._data.description = ""
        self._data.pending = False
        logger.debug("Données de transfert effacées")

    def is_pending(self) -> bool:
        """Retourne True si des données attendent d'être transférées."""
        return self._data.pending

    def is_running(self) -> bool:
        """Retourne True si le serveur HTTP est actif."""
        return self._running

    # ------------------------------------------------------------------
    # Handlers HTTP
    # ------------------------------------------------------------------

    async def _handle_status(self, request: web.Request) -> web.Response:
        """GET /status - Diagnostic du serveur."""
        return web.json_response({
            "status": "ok",
            "service": "Vinted Assistant Bridge",
            "port": self.port,
            "pending_transfer": self._data.pending,
        })

    async def _handle_check(self, request: web.Request) -> web.Response:
        """
        GET /check - Retourne les données de transfert si disponibles.

        Appelé par l'extension Chrome toutes les 2 secondes.
        """
        if not self._data.pending:
            # Pas de données en attente
            return web.json_response({})

        logger.info("Extension Chrome récupère les données de transfert")
        return web.json_response({
            "title": self._data.title,
            "description": self._data.description,
        })

    async def _handle_confirm(self, request: web.Request) -> web.Response:
        """
        POST /confirm - Confirme que l'extension a bien reçu les données.

        Efface les données en attente pour éviter les doublons.
        """
        if self._data.pending:
            logger.info("Transfert confirmé par l'extension Chrome")
            self.clear_transfer_data()

            # Callback optionnel pour notifier l'UI
            if self.on_transfer_complete:
                try:
                    self.on_transfer_complete()
                except Exception as exc:
                    logger.error("Erreur dans callback on_transfer_complete: %s", exc)

        return web.json_response({"status": "confirmed"})

    async def _handle_profiles(self, request: web.Request) -> web.Response:
        """GET /profiles - Liste des profils d'analyse disponibles."""
        from domain.templates import ALL_PROFILES
        from domain.templates.base import AnalysisProfileName

        # Champs par profil (correspond aux champs UI)
        profile_fields = {
            "jean_levis": {
                "label": "Jean Levi's",
                "fields": ["size_fr", "size_us", "length", "fit", "rise_type",
                           "composition", "order_id", "has_defect"],
            },
            "pull": {
                "label": "Pull",
                "fields": ["measurement_mode", "order_id", "has_defect"],
            },
            "jacket_carhart": {
                "label": "Veste Carhartt",
                "fields": ["size_fr", "size_us", "length", "composition",
                           "order_id", "has_defect"],
            },
            "polaire_outdoor": {
                "label": "Polaire Outdoor",
                "fields": ["measurement_mode", "order_id", "has_defect"],
            },
        }

        profiles = []
        for name, profile in ALL_PROFILES.items():
            pf = profile_fields.get(name.value, {"label": name.value, "fields": []})
            profiles.append({
                "name": name.value,
                "label": pf["label"],
                "fields": pf["fields"],
            })

        return web.json_response({"profiles": profiles})

    async def _handle_generate(self, request: web.Request) -> web.Response:
        """
        POST /generate - Génère une annonce Vinted à partir d'images + profil.

        Body JSON attendu :
        {
            "images": [{"data": "<base64>", "filename": "img.jpg"}, ...],
            "profile": "jean_levis",
            "ui_data": {"size_fr": "42", ...}
        }
        """
        if not self.provider:
            return web.json_response(
                {"error": "Aucun provider IA configuré sur le serveur."},
                status=503,
            )

        try:
            body = await request.json()
        except Exception:
            return web.json_response(
                {"error": "Corps de requête JSON invalide."}, status=400
            )

        # Valider les champs requis
        images_raw = body.get("images", [])
        profile_name = body.get("profile", "")
        ui_data = body.get("ui_data", {})

        if not images_raw:
            return web.json_response(
                {"error": "Au moins une image est requise."}, status=400
            )

        if not profile_name:
            return web.json_response(
                {"error": "Le champ 'profile' est requis."}, status=400
            )

        # Résoudre le profil
        from domain.templates import ALL_PROFILES
        from domain.templates.base import AnalysisProfileName

        try:
            profile_enum = AnalysisProfileName(profile_name)
            profile = ALL_PROFILES[profile_enum]
        except (ValueError, KeyError):
            return web.json_response(
                {"error": f"Profil inconnu: {profile_name}"}, status=400
            )

        # Décoder les images base64 en fichiers temporaires
        tmp_files: List[Path] = []
        try:
            for i, img in enumerate(images_raw):
                img_data = img.get("data", "")
                filename = img.get("filename", f"image_{i}.jpg")

                # Déterminer le suffixe
                suffix = Path(filename).suffix or ".jpg"

                # Décoder base64
                try:
                    raw_bytes = base64.b64decode(img_data)
                except Exception:
                    return web.json_response(
                        {"error": f"Image {i} : base64 invalide."}, status=400
                    )

                tmp = tempfile.NamedTemporaryFile(
                    delete=False, suffix=suffix, prefix="vinted_ext_"
                )
                tmp.write(raw_bytes)
                tmp.close()
                tmp_files.append(Path(tmp.name))

            logger.info(
                "POST /generate: %d images décodées, profil=%s",
                len(tmp_files), profile_name,
            )

            # Appeler le provider dans un executor (non-bloquant)
            loop = asyncio.get_event_loop()
            t_start = time.time()
            listing = await loop.run_in_executor(
                None,
                lambda: self.provider.generate_listing(
                    tmp_files, profile, ui_data=ui_data
                ),
            )
            listing.generation_time_s = round(time.time() - t_start, 2)

            # Construire la réponse enrichie
            result = listing.to_dict()

            # Ajouter les valeurs par défaut pour l'extension
            result["price"] = ui_data.get("price", 24)
            result["shipping_size"] = ui_data.get("shipping_size", "Petit")

            # Extraire matériaux depuis features si disponible
            features = result.get("features", {})
            materials = features.get("composition_materials") or features.get("material")
            if not materials and result.get("manual_composition_text"):
                materials = result["manual_composition_text"]
            result["materials"] = materials

            logger.info(
                "POST /generate: succès en %.2fs (titre=%d chars)",
                listing.generation_time_s, len(listing.title),
            )
            return web.json_response(result)

        except Exception as exc:
            logger.error("POST /generate: erreur: %s", exc, exc_info=True)
            return web.json_response(
                {"error": str(exc)}, status=500
            )
        finally:
            # Nettoyer les fichiers temporaires
            for tmp_path in tmp_files:
                try:
                    tmp_path.unlink(missing_ok=True)
                except Exception:
                    pass

    async def _handle_shutdown(self, request: web.Request) -> web.Response:
        """POST /shutdown - Arrête le serveur proprement."""
        logger.info("Arrêt du serveur demandé via /shutdown")
        self._running = False
        return web.json_response({"status": "shutting_down"})

    async def _handle_cors_preflight(self, request: web.Request) -> web.Response:
        """Gère les requêtes OPTIONS pour CORS."""
        return web.Response(
            status=204,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Accept",
            }
        )

    # ------------------------------------------------------------------
    # Middleware CORS
    # ------------------------------------------------------------------

    @web.middleware
    async def _cors_middleware(
        self,
        request: web.Request,
        handler: Callable
    ) -> web.Response:
        """Ajoute les headers CORS à toutes les réponses."""
        if request.method == "OPTIONS":
            return await self._handle_cors_preflight(request)

        response = await handler(request)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Accept"
        return response

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _create_app(self) -> web.Application:
        """Crée l'application aiohttp avec les routes."""
        # 100MB max pour les images base64
        app = web.Application(
            middlewares=[self._cors_middleware],
            client_max_size=100 * 1024 * 1024,
        )
        app.router.add_get("/status", self._handle_status)
        app.router.add_get("/check", self._handle_check)
        app.router.add_get("/profiles", self._handle_profiles)
        app.router.add_post("/confirm", self._handle_confirm)
        app.router.add_post("/generate", self._handle_generate)
        app.router.add_post("/shutdown", self._handle_shutdown)
        app.router.add_route("OPTIONS", "/check", self._handle_cors_preflight)
        app.router.add_route("OPTIONS", "/confirm", self._handle_cors_preflight)
        app.router.add_route("OPTIONS", "/generate", self._handle_cors_preflight)
        app.router.add_route("OPTIONS", "/shutdown", self._handle_cors_preflight)
        return app

    async def _run_server(self) -> None:
        """Lance le serveur HTTP (appelé dans le thread dédié)."""
        app = self._create_app()
        self._runner = web.AppRunner(app)
        await self._runner.setup()

        site = web.TCPSite(self._runner, "localhost", self.port)
        await site.start()

        logger.info("Serveur HTTP Bridge démarré sur http://localhost:%d", self.port)
        self._running = True

        # Boucle infinie jusqu'à arrêt
        while self._running:
            await asyncio.sleep(0.5)

        # Cleanup
        await self._runner.cleanup()
        logger.info("Serveur HTTP Bridge arrêté")

    def _thread_target(self) -> None:
        """Point d'entrée du thread serveur."""
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._run_server())
        except Exception as exc:
            logger.error("Erreur dans le thread serveur HTTP: %s", exc, exc_info=True)
        finally:
            if self._loop:
                self._loop.close()

    def start(self) -> None:
        """Démarre le serveur HTTP en arrière-plan."""
        if self._running:
            logger.warning("Serveur HTTP déjà en cours d'exécution")
            return

        self._server_thread = threading.Thread(
            target=self._thread_target,
            daemon=True,
            name="BrowserBridgeServer"
        )
        self._server_thread.start()
        logger.info("Thread serveur HTTP Bridge lancé")

    def stop(self) -> None:
        """Arrête le serveur HTTP proprement."""
        if not self._running:
            return

        self._running = False

        if self._server_thread and self._server_thread.is_alive():
            self._server_thread.join(timeout=3.0)
            logger.info("Thread serveur HTTP Bridge terminé")


# Singleton global pour accès facile depuis l'UI
_bridge_instance: Optional[BrowserBridge] = None


def get_bridge() -> BrowserBridge:
    """Retourne l'instance singleton du BrowserBridge."""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = BrowserBridge()
    return _bridge_instance


def start_bridge(
    port: int = DEFAULT_PORT,
    on_transfer_complete: Optional[Callable[[], None]] = None,
    provider: Optional[Any] = None,
) -> BrowserBridge:
    """
    Démarre le serveur Bridge et retourne l'instance.

    Args:
        port: Port HTTP (défaut: 8765)
        on_transfer_complete: Callback appelé quand l'extension confirme le transfert
        provider: AIListingProvider pour le endpoint POST /generate
    """
    global _bridge_instance

    if _bridge_instance is not None and _bridge_instance.is_running():
        logger.warning("Bridge déjà actif, réutilisation de l'instance existante")
        return _bridge_instance

    _bridge_instance = BrowserBridge(
        port=port,
        on_transfer_complete=on_transfer_complete,
        provider=provider,
    )
    _bridge_instance.start()
    return _bridge_instance


def stop_bridge() -> None:
    """Arrête le serveur Bridge global."""
    global _bridge_instance
    if _bridge_instance:
        _bridge_instance.stop()
        _bridge_instance = None
