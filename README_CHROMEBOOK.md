# 🚀 Vinted Assistant - Guide Chromebook

Guide d'installation et d'utilisation pour **Chromebook Crostini**.

---

## 📋 Table des matières

1. [Prérequis](#prérequis)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Utilisation](#utilisation)
5. [Dépannage](#dépannage)

---

## 🔧 Prérequis

### Système
- **Chromebook** avec Linux (Beta) / Crostini activé
- **Google Chrome** (version bureau)
- **Connexion Internet** pour l'API Gemini

### Activer Linux sur Chromebook

Si Linux n'est pas encore activé :

1. Paramètres ChromeOS → **Linux (Beta)**
2. Cliquer sur **Activer**
3. Suivre les instructions d'installation
4. Attendre que le terminal Linux s'ouvre

---

## 📦 Installation

### Étape 1 : Cloner le projet

```bash
# Dans le terminal Linux (Crostini)
cd ~/
git clone <URL_DU_REPO> vinted-assistant
cd vinted-assistant
```

### Étape 2 : Lancer le script d'installation

```bash
# Rendre le script exécutable
chmod +x setup_chromebook.sh

# Lancer l'installation
./setup_chromebook.sh
```

Le script va :
- ✅ Installer les dépendances Python
- ✅ Vérifier le port 8765
- ✅ Tester le serveur HTTP
- ✅ Guider pour le port forwarding
- ✅ Guider pour l'installation de l'extension Chrome

### Étape 3 : Configurer les clés API

```bash
# Copier le fichier d'exemple
cp .env.example .env

# Éditer avec vos clés
nano .env
```

Remplir avec vos clés API :
```
GEMINI_API_KEY=votre_clé_gemini_ici
```

---

## ⚙️ Configuration

### 1. Port Forwarding (CRITIQUE)

Pour que Chrome (ChromeOS) puisse communiquer avec l'app Python (Crostini) :

1. **Paramètres ChromeOS** → **Linux (Beta)**
2. **Développer des applications Linux** → **Port forwarding**
3. Cliquer **Ajouter**
4. Configuration :
   - **Numéro de port** : `8765`
   - **Type de connexion** : `TCP`
   - **Étiquette** : `Vinted Assistant`
5. **Activer** le port

✅ **Vérification** : Une fois l'app lancée, ouvrir http://localhost:8765/status dans Chrome devrait afficher un JSON.

### 2. Extension Chrome

1. Ouvrir **Google Chrome** (ChromeOS)
2. Aller sur : `chrome://extensions/`
3. Activer **Mode développeur** (toggle en haut à droite)
4. Cliquer **Charger l'extension non empaquetée**
5. Naviguer vers : `Fichiers Linux` → `vinted-assistant` → `extension/`
6. Sélectionner le dossier `extension`
7. ✅ L'extension apparaît dans la liste

**Extension installée** : L'icône 🏷️ devrait apparaître dans la barre Chrome.

---

## 🎯 Utilisation

### Workflow complet

#### 1. Créer un brouillon sur Vinted

```
📱 Sur Vinted (navigateur Chrome) :
1. Cliquer "Vendre"
2. Ajouter photos (1-12 photos)
3. Cliquer "Mettre en brouillon" (sans rien remplir)
4. ✅ Brouillon créé avec photos uniquement
```

#### 2. Sauvegarder les photos localement

```
💾 Sur Vinted :
1. Ouvrir le brouillon
2. Clic droit sur chaque photo → "Enregistrer l'image sous"
3. Sauvegarder dans : ~/Downloads/Article1/
4. ✅ Photos sauvegardées
```

#### 3. Lancer l'application

```bash
# Dans le terminal Crostini
cd ~/vinted-assistant
python3 main.py
```

**Vérifications au démarrage** :
```
✅ Serveur HTTP démarré sur http://localhost:8765
🟢 Bridge activé - Extension peut communiquer
```

#### 4. Générer titre et description

```
🖥️ Dans l'application :
1. Cliquer "+" → Sélectionner vos photos
2. Choisir le profil (Jean Levi's, Jacket, Pull, etc.)
3. Optionnel : Renseigner tailles FR/US
4. Cliquer "Générer"
⏳ Attendre 5-10 secondes...
✅ Titre et description générés !
```

#### 5. Envoyer automatiquement vers Vinted

```
🖥️ Dans l'application :
1. Vérifier le titre/description générés
2. Cliquer sur le bouton "📤 Vinted"
⏳ L'extension remplit automatiquement...
✅ Notification : "Brouillon Vinted rempli!"
```

**Ce qui se passe** :
- L'app envoie les données via `localhost:8765`
- L'extension Chrome les récupère (polling toutes les 2s)
- Les champs titre + description sont remplis automatiquement
- Simulation de frappe humaine (50-120ms par caractère)

#### 6. Compléter le brouillon manuellement

```
🌐 Retour sur Vinted :
1. Vérifier titre ✅ et description ✅
2. Remplir manuellement :
   - Prix : 45€
   - Marque : Levi's
   - Taille : W32 L34
   - État : Bon état
   - Couleur : Bleu
   - Catégorie : Jeans
3. Cliquer "Enregistrer le brouillon"
4. ✅ Brouillon complet !
```

#### 7. Publier (quand prêt)

```
🌐 Sur Vinted :
1. Aller dans "Mes brouillons"
2. Vérifier l'annonce
3. Cliquer "Publier"
4. ✅ Article en ligne !
```

---

## ⏱️ Gain de temps

### Avant (manuel)
```
1. Générer titre/description                     [10s]
2. Sélectionner titre → Ctrl+C                   [5s]
3. Alt+Tab → Vinted                              [2s]
4. Clic champ → Ctrl+V                           [3s]
5. Alt+Tab → App                                 [2s]
6. Sélectionner description → Ctrl+C             [5s]
7. Alt+Tab → Vinted                              [2s]
8. Clic champ → Ctrl+V                           [3s]
──────────────────────────────────────────────────
TOTAL actions titre/description : ~32 secondes
```

### Après (automatique)
```
1. Générer titre/description                     [10s]
2. Clic "📤 Vinted"                              [1s]
   → Titre auto-rempli ✅
   → Description auto-remplie ✅
──────────────────────────────────────────────────
TOTAL actions titre/description : ~11 secondes

🎯 Gain : 21 secondes par article (-65%)
🎯 Plus de copier/coller
🎯 Plus d'aller-retour app/navigateur
```

---

## 🛠️ Dépannage

### Problème : "Bridge non disponible"

**Cause** : Le serveur HTTP n'a pas démarré

**Solutions** :
```bash
# 1. Vérifier que le port est libre
lsof -i :8765

# 2. Tuer le processus si nécessaire
kill -9 <PID>

# 3. Relancer l'app
python3 main.py
```

### Problème : "L'extension n'a pas répondu" (timeout)

**Vérifications** :

1. **Un brouillon Vinted est-il ouvert ?**
   - L'URL doit contenir `/items/*/edit`
   - Exemple : `vinted.fr/items/123456/edit`

2. **L'extension est-elle activée ?**
   - Aller sur `chrome://extensions/`
   - Vérifier que "Vinted Assistant" est activé

3. **Le port forwarding est-il configuré ?**
   - Paramètres ChromeOS → Linux → Port 8765 activé

4. **Console Chrome (F12)** :
   ```
   Aller sur le brouillon Vinted
   F12 → Console
   Chercher : "🟢 Vinted Assistant activé"
   ```

### Problème : Extension ne détecte pas les données

**Test manuel** :

```bash
# Dans un autre terminal
curl http://localhost:8765/status
```

Devrait retourner :
```json
{
  "status": "running",
  "server": "Vinted Assistant Bridge",
  "version": "1.0.0"
}
```

Si erreur → Le serveur n'est pas démarré.

### Problème : Champs Vinted ne se remplissent pas

**Console Chrome (F12)** :

```javascript
// Vérifier que l'extension écoute
// Devrait afficher toutes les 2s :
"🔄 Polling démarré - vérification toutes les 2 secondes"

// Vérifier les sélecteurs
document.querySelector('input[name="title"]')
document.querySelector('textarea[name="description"]')

// Si null → Les sélecteurs ont changé
```

**Solution temporaire** : Copier/coller manuel avec les boutons 📋

---

## 🔒 Sécurité & Détection

### L'extension est-elle détectable par Vinted ?

**Non, car** :

✅ **Pas d'automation browser** : Pas de Selenium/Playwright
✅ **Extension légitime** : Comme LastPass ou 1Password
✅ **Événements natifs** : `isTrusted: true` sur tous les events
✅ **Timing humain** : 50-120ms entre frappes (vitesse réelle)
✅ **Pas de patterns** : Chaque brouillon unique
✅ **Session authentique** : Tes vrais cookies Chrome

### Test de détection

```javascript
// Console Chrome (F12) - après remplissage
document.querySelector('input[name="title"]').addEventListener('input', (e) => {
    console.log('isTrusted:', e.isTrusted);  // Doit être TRUE
});

// Si TRUE → Indétectable par Vinted ✅
```

---

## 📊 Architecture technique

```
┌─────────────────────────────────────────┐
│  ChromeOS (système hôte)                │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │ Chrome + Extension               │  │
│  │  • Polling localhost:8765/check  │  │
│  │  • Remplit formulaire Vinted     │  │
│  └──────────────────────────────────┘  │
│         ↕ HTTP (localhost:8765)        │
│  ┌──────────────────────────────────┐  │
│  │ Port forwarding 8765             │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
         ↕
┌─────────────────────────────────────────┐
│  Crostini (container Linux)             │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │ App Python (CustomTkinter)       │  │
│  │  • Serveur HTTP :8765            │  │
│  │  • OCR + Génération IA           │  │
│  │  • Interface utilisateur         │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

---

## 🎓 Conseils d'utilisation

### Optimiser le workflow

**Pour plusieurs articles** :

1. Créer tous les brouillons Vinted d'un coup (avec photos)
2. Sauvegarder toutes les photos dans des dossiers séparés
3. Générer tous les titres/descriptions d'affilée
4. Envoyer vers chaque brouillon avec "📤 Vinted"
5. Compléter tous les brouillons ensuite

**Gain** : ~10 min pour 10 articles

### Bonnes pratiques

- ✅ Toujours vérifier le titre/description avant envoi
- ✅ Compléter TOUS les champs manuellement (prix, taille, etc.)
- ✅ Ne pas dépasser 10-15 annonces/jour
- ✅ Varier les heures de publication
- ✅ Relire chaque brouillon avant publication

---

## 📞 Support

### Logs de débogage

```bash
# Lancer l'app en mode verbose
python3 main.py --verbose

# Logs de l'extension
Chrome → F12 → Console (sur page Vinted)
```

### Fichiers importants

```
vinted-assistant/
├── extension/
│   ├── manifest.json          # Config extension
│   ├── content.js             # Script principal
│   └── background.js          # Service worker
│
├── infrastructure/
│   └── browser_bridge.py      # Serveur HTTP
│
├── presentation/
│   └── ui_app.py              # Interface + intégration
│
└── setup_chromebook.sh        # Script d'installation
```

---

## ✅ Checklist de fonctionnement

Avant d'utiliser, vérifier que :

- [ ] Linux (Crostini) activé sur Chromebook
- [ ] Dépendances Python installées (`./setup_chromebook.sh`)
- [ ] Port forwarding configuré (port 8765)
- [ ] Extension Chrome installée et activée
- [ ] Clés API configurées dans `.env`
- [ ] Serveur démarré (`python3 main.py`)
- [ ] http://localhost:8765/status fonctionne dans Chrome
- [ ] Brouillon Vinted ouvert dans Chrome

Si tous les points ✅ → Tout fonctionne !

---

## 🎉 Conclusion

Vous êtes maintenant prêt à utiliser **Vinted Assistant** sur Chromebook !

**Workflow résumé** :
1. Photos → Brouillon Vinted
2. Sauvegarder photos localement
3. App Python → Générer
4. Clic "📤 Vinted" → Auto-rempli
5. Compléter manuellement
6. Publier

**Questions ?** Consulter la section [Dépannage](#dépannage)

Bon listing ! 🚀
