#!/bin/bash
# setup_chromebook.sh - Configuration pour Chromebook Crostini

set -e

echo "============================================================"
echo "  Configuration Vinted Assistant pour Chromebook"
echo "============================================================"
echo ""

# Couleurs pour l'affichage
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 1. Vérifier qu'on est bien dans Crostini
echo -e "${BLUE}📌 Vérification de l'environnement...${NC}"
if [[ ! -f "/etc/apt/sources.list.d/cros.list" ]]; then
    echo -e "${YELLOW}⚠️  Attention: Ce script est optimisé pour Chromebook Crostini${NC}"
    echo "   Vous pouvez continuer mais certaines étapes peuvent différer."
    echo ""
fi

# 2. Installer les dépendances système
echo -e "${BLUE}📦 Installation des dépendances système...${NC}"
sudo apt-get update -qq
sudo apt-get install -y python3-pip python3-venv python3-tk

# 3. Installer les dépendances Python
echo ""
echo -e "${BLUE}🐍 Installation des dépendances Python...${NC}"
pip3 install --user aiohttp flet google-cloud-vision google-generativeai customtkinter pillow python-dotenv

echo -e "${GREEN}✅ Dépendances Python installées${NC}"

# 4. Vérifier que le port 8765 est libre
echo ""
echo -e "${BLUE}🔌 Vérification du port 8765...${NC}"
if lsof -Pi :8765 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${RED}❌ Le port 8765 est déjà utilisé!${NC}"
    echo "   Arrêtez le processus utilisant ce port ou choisissez un autre port."
    exit 1
else
    echo -e "${GREEN}✅ Port 8765 disponible${NC}"
fi

# 5. Test du serveur HTTP
echo ""
echo -e "${BLUE}🧪 Test du serveur HTTP...${NC}"
python3 -c "
import asyncio
from aiohttp import web

async def test_handler(request):
    return web.Response(text='OK - Server is working')

async def test_server():
    app = web.Application()
    app.router.add_get('/', test_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8765)
    await site.start()
    print('✅ Serveur test démarré sur http://localhost:8765')
    print('   Le serveur va s\'arrêter dans 5 secondes...')
    await asyncio.sleep(5)
    await site.stop()
    await runner.cleanup()
    print('✅ Test réussi - Le serveur fonctionne correctement')

asyncio.run(test_server())
" 2>/dev/null || {
    echo -e "${RED}❌ Erreur lors du test du serveur${NC}"
    echo "   Vérifiez que aiohttp est bien installé"
    exit 1
}

# 6. Instructions pour le port forwarding
echo ""
echo "============================================================"
echo -e "${YELLOW}📌 CONFIGURATION DU PORT FORWARDING (IMPORTANT)${NC}"
echo "============================================================"
echo ""
echo "Pour que l'extension Chrome puisse communiquer avec l'app:"
echo ""
echo "1. Ouvrir les Paramètres de ChromeOS"
echo "2. Aller dans: Linux (Beta) → Développer des applications Linux"
echo "3. Cliquer sur 'Port forwarding'"
echo "4. Ajouter un nouveau port:"
echo "   - Numéro de port: 8765"
echo "   - Type de connexion: TCP"
echo "   - Étiquette: Vinted Assistant"
echo "5. Activer le port forwarding"
echo ""
read -p "Appuyez sur Entrée quand c'est fait..."

# 7. Vérifier l'extension Chrome
echo ""
echo "============================================================"
echo -e "${YELLOW}📌 INSTALLATION DE L'EXTENSION CHROME${NC}"
echo "============================================================"
echo ""
echo "Extension située dans: $(pwd)/extension/"
echo ""
echo "Pour installer l'extension:"
echo ""
echo "1. Ouvrir Google Chrome (ChromeOS, pas Crostini)"
echo "2. Aller sur: chrome://extensions/"
echo "3. Activer 'Mode développeur' (toggle en haut à droite)"
echo "4. Cliquer 'Charger l'extension non empaquetée'"
echo "5. Naviguer vers: Fichiers Linux → $(basename $(pwd)) → extension/"
echo "6. Sélectionner le dossier 'extension'"
echo "7. ✅ L'extension devrait apparaître dans la liste"
echo ""
read -p "Appuyez sur Entrée quand c'est fait..."

# 8. Test final
echo ""
echo "============================================================"
echo -e "${BLUE}🧪 TEST FINAL DE LA CONFIGURATION${NC}"
echo "============================================================"
echo ""
echo "Pour tester que tout fonctionne:"
echo ""
echo "1. Dans un terminal Crostini, lancez:"
echo -e "   ${GREEN}python3 main.py${NC}"
echo ""
echo "2. L'app devrait afficher:"
echo "   ✅ Serveur HTTP démarré sur http://localhost:8765"
echo ""
echo "3. Dans Chrome, ouvrez un nouvel onglet et allez sur:"
echo -e "   ${GREEN}http://localhost:8765/status${NC}"
echo ""
echo "4. Vous devriez voir un JSON avec 'status': 'running'"
echo ""
echo "Si ça fonctionne, votre configuration est correcte! 🎉"
echo ""

# 9. Résumé
echo "============================================================"
echo -e "${GREEN}✅ CONFIGURATION TERMINÉE${NC}"
echo "============================================================"
echo ""
echo "Prochaines étapes:"
echo ""
echo "1. Configurer vos clés API dans .env:"
echo -e "   ${GREEN}cp .env.example .env${NC}"
echo "   ${GREEN}nano .env${NC}  # Éditer avec vos clés"
echo ""
echo "2. Lancer l'application:"
echo -e "   ${GREEN}python3 main.py${NC}"
echo ""
echo "3. Utiliser l'application:"
echo "   - Générer titre + description"
echo "   - Ouvrir un brouillon Vinted dans Chrome"
echo "   - Cliquer sur '📤 Vinted' dans l'app"
echo "   - Les champs se remplissent automatiquement!"
echo ""
echo "Pour plus d'aide, consultez: README_CHROMEBOOK.md"
echo ""
echo "============================================================"
