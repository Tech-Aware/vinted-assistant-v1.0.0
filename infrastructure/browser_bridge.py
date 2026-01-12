"""
Browser Bridge - Communication HTTP avec l'extension Chrome
Compatible Chromebook Crostini via localhost
"""

import asyncio
import json
from aiohttp import web
from typing import Optional, Dict, Any


class ChromebookBrowserBridge:
    """
    Serveur HTTP pour communication avec l'extension Chrome.
    Architecture adaptée pour Chromebook Crostini.

    L'extension Chrome (dans ChromeOS) fait du polling sur localhost:8765
    pour récupérer les données à remplir dans Vinted.
    """

    def __init__(self):
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        self.pending_data: Optional[Dict[str, str]] = None
        self.confirmed = False
        self.server_running = False

        # Configuration des routes HTTP
        self.app.router.add_get('/check', self.handle_check)
        self.app.router.add_post('/confirm', self.handle_confirm)
        self.app.router.add_options('/check', self.handle_cors)
        self.app.router.add_options('/confirm', self.handle_cors)
        self.app.router.add_get('/status', self.handle_status)

    async def handle_cors(self, request: web.Request) -> web.Response:
        """Gérer les requêtes CORS OPTIONS pour communication cross-origin"""
        return web.Response(
            headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            }
        )

    async def handle_check(self, request: web.Request) -> web.Response:
        """
        Endpoint GET /check
        L'extension Chrome vérifie s'il y a des données à remplir
        """
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Content-Type': 'application/json'
        }

        if self.pending_data and not self.confirmed:
            # Retourner les données en attente
            return web.json_response(self.pending_data, headers=headers)
        else:
            # Aucune donnée en attente
            return web.json_response({}, headers=headers)

    async def handle_confirm(self, request: web.Request) -> web.Response:
        """
        Endpoint POST /confirm
        L'extension confirme que le remplissage est terminé
        """
        self.confirmed = True
        return web.Response(
            text='OK',
            headers={'Access-Control-Allow-Origin': '*'}
        )

    async def handle_status(self, request: web.Request) -> web.Response:
        """
        Endpoint GET /status
        Vérifier que le serveur fonctionne
        """
        return web.json_response({
            'status': 'running',
            'server': 'Vinted Assistant Bridge',
            'version': '1.0.0'
        }, headers={'Access-Control-Allow-Origin': '*'})

    async def start_server(self, host: str = 'localhost', port: int = 8765):
        """
        Démarrer le serveur HTTP

        Args:
            host: Adresse d'écoute (localhost pour Chromebook)
            port: Port d'écoute (8765 par défaut)
        """
        if self.server_running:
            print("⚠️  Le serveur est déjà en cours d'exécution")
            return

        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()

            self.site = web.TCPSite(self.runner, host, port)
            await self.site.start()

            self.server_running = True

            print("=" * 60)
            print("✅ Serveur HTTP démarré avec succès")
            print(f"   URL: http://{host}:{port}")
            print(f"   Status: http://{host}:{port}/status")
            print("-" * 60)
            print("📌 Configuration Chromebook:")
            print("   1. Vérifiez que le port forwarding est activé")
            print("   2. Paramètres ChromeOS → Linux → Port forwarding")
            print(f"   3. Ajouter port {port} (TCP)")
            print("-" * 60)
            print("🔌 Extension Chrome:")
            print("   L'extension doit être installée et activée")
            print("   Elle vérifiera automatiquement http://localhost:8765")
            print("=" * 60)

        except OSError as e:
            if "Address already in use" in str(e):
                print(f"❌ Le port {port} est déjà utilisé")
                print("   Solutions:")
                print(f"   - Arrêtez l'autre processus utilisant le port {port}")
                print("   - Ou utilisez un port différent")
            else:
                print(f"❌ Erreur lors du démarrage du serveur: {e}")
            self.server_running = False

    async def stop_server(self):
        """Arrêter le serveur HTTP"""
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()

        self.server_running = False
        print("🛑 Serveur HTTP arrêté")

    async def send_to_vinted(
        self,
        title: str,
        description: str,
        timeout: int = 30
    ) -> bool:
        """
        Envoyer titre et description vers l'extension Chrome

        Args:
            title: Titre de l'annonce
            description: Description de l'annonce
            timeout: Timeout en secondes (défaut: 30)

        Returns:
            True si succès, False si échec/timeout
        """
        if not self.server_running:
            print("❌ Le serveur n'est pas démarré")
            print("   Lancez d'abord le serveur avec start_server()")
            return False

        # Préparer les données
        self.pending_data = {
            'title': title,
            'description': description,
            'timestamp': asyncio.get_event_loop().time()
        }
        self.confirmed = False

        print("\n" + "=" * 60)
        print("📤 Envoi vers Vinted...")
        print("-" * 60)
        print(f"📝 Titre: {title[:60]}{'...' if len(title) > 60 else ''}")
        print(f"📄 Description: {description[:60]}{'...' if len(description) > 60 else ''}")
        print("-" * 60)
        print("⏳ En attente de confirmation de l'extension...")
        print("   L'extension va remplir les champs automatiquement")
        print("=" * 60)

        # Attendre la confirmation de l'extension (polling)
        start_time = asyncio.get_event_loop().time()
        dots = 0

        while not self.confirmed:
            await asyncio.sleep(0.5)

            # Animation de progression
            dots = (dots + 1) % 4
            print(f"\r⏳ En attente" + "." * dots + " " * (3 - dots), end='', flush=True)

            # Vérifier timeout
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                print("\n\n" + "=" * 60)
                print("❌ TIMEOUT: L'extension n'a pas répondu")
                print("-" * 60)

                # Diagnostic automatique
                print("🔍 DIAGNOSTIC AUTOMATIQUE:")
                try:
                    import urllib.request
                    urllib.request.urlopen('http://localhost:8765/status', timeout=2)
                    print("   ✅ Serveur accessible sur localhost:8765")
                except Exception as e:
                    print(f"   ❌ Serveur NON accessible: {type(e).__name__}")
                    print("      → Relancer l'application")

                print("\n⚠️ CAUSE PROBABLE:")
                print("   Le brouillon Vinted N'EST PAS OUVERT dans Chrome !")
                print("\n🛠️ VÉRIFICATIONS À FAIRE:")
                print("   1. ⚠️ AVEZ-VOUS OUVERT LE BROUILLON VINTED ?")
                print("      → L'URL doit contenir: /items/123456/edit")
                print("      → Pas juste la page d'accueil Vinted !")
                print("   2. Extension installée ? (chrome://extensions/)")
                print("   3. Extension activée ? (toggle ON)")
                print("   4. Port forwarding configuré ? (Port 8765)")
                print("   5. Console Chrome (F12) - Erreurs ?")
                print("\n💡 WORKFLOW CORRECT:")
                print("   1. Créer un brouillon sur Vinted (avec photos)")
                print("   2. Garder l'onglet du brouillon OUVERT")
                print("   3. Retour à l'app Python")
                print("   4. Cliquer '📤 Vinted'")
                print("=" * 60 + "\n")
                self.pending_data = None
                return False

        # Succès
        print("\n\n" + "=" * 60)
        print("✅ SUCCÈS: Brouillon Vinted rempli!")
        print("-" * 60)
        print("📝 Titre et description insérés automatiquement")
        print("👉 Prochaines étapes:")
        print("   1. Vérifiez le brouillon Vinted dans Chrome")
        print("   2. Complétez les champs restants (prix, taille, etc.)")
        print("   3. Cliquez sur 'Enregistrer le brouillon'")
        print("=" * 60 + "\n")

        self.pending_data = None
        return True


# Singleton global pour réutilisation
_bridge_instance: Optional[ChromebookBrowserBridge] = None


def get_bridge() -> ChromebookBrowserBridge:
    """
    Récupère l'instance singleton du bridge

    Returns:
        Instance unique de ChromebookBrowserBridge
    """
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = ChromebookBrowserBridge()
    return _bridge_instance


# Fonction utilitaire pour tests
async def test_server():
    """Fonction de test pour vérifier le serveur"""
    bridge = get_bridge()
    await bridge.start_server()

    print("\n🧪 Serveur de test démarré")
    print("   Testez dans votre navigateur: http://localhost:8765/status")
    print("   Appuyez sur Ctrl+C pour arrêter\n")

    try:
        # Garder le serveur en vie
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 Arrêt du serveur...")
        await bridge.stop_server()


if __name__ == "__main__":
    # Test du serveur
    print("🚀 Test du Browser Bridge\n")
    asyncio.run(test_server())
