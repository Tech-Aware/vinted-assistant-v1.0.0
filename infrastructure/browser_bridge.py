# infrastructure/browser_bridge.py
"""
Serveur HTTP pour la communication entre l'app Python et l'extension Chrome.

Architecture inspirée de Clem's :
- Polling HTTP (pas de WebSocket) pour compatibilité maximale (Chromebook, réseaux restreints)
- Comportement humain simulé côté extension (délais, frappe progressive)
- Une seule donnée à la fois (pas de queue/rafale)

Endpoints:
- GET  /status : Diagnostic - vérifie que le serveur est actif
- GET  /check  : Récupère les données à transférer (titre/description)
- POST /confirm: Confirme que les données ont été reçues par l'extension
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from dataclasses import dataclass, field
from typing import Optional, Callable

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
        app = web.Application(middlewares=[self._cors_middleware])
        app.router.add_get("/status", self._handle_status)
        app.router.add_get("/check", self._handle_check)
        app.router.add_post("/confirm", self._handle_confirm)
        app.router.add_route("OPTIONS", "/check", self._handle_cors_preflight)
        app.router.add_route("OPTIONS", "/confirm", self._handle_cors_preflight)
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
    on_transfer_complete: Optional[Callable[[], None]] = None
) -> BrowserBridge:
    """
    Démarre le serveur Bridge et retourne l'instance.

    Args:
        port: Port HTTP (défaut: 8765)
        on_transfer_complete: Callback appelé quand l'extension confirme le transfert
    """
    global _bridge_instance

    if _bridge_instance is not None and _bridge_instance.is_running():
        logger.warning("Bridge déjà actif, réutilisation de l'instance existante")
        return _bridge_instance

    _bridge_instance = BrowserBridge(
        port=port,
        on_transfer_complete=on_transfer_complete
    )
    _bridge_instance.start()
    return _bridge_instance


def stop_bridge() -> None:
    """Arrête le serveur Bridge global."""
    global _bridge_instance
    if _bridge_instance:
        _bridge_instance.stop()
        _bridge_instance = None
