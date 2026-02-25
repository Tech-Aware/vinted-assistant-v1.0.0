# Vinted Assistant Online - Google Apps Script

Version Google Apps Script de Vinted Assistant. Fonctionne directement depuis Google Sheets, sans installation locale.

## Architecture

```
appscript/
  appsscript.json          # Manifeste Apps Script
  Code.gs                  # Point d'entree, menu, fonctions globales
  Config.gs                # Configuration via Script Properties
  GeminiClient.gs          # Client API Gemini (UrlFetchApp)
  Prompt.gs                # Contrat de prompt IA
  Models.gs                # Modele VintedListing
  Templates.gs             # Profils d'analyse (jean_levis, pull, jacket_carhart)
  Normalizer.gs            # Normalisation et post-traitement
  TitleEngine.gs           # Construction des titres
  TitleBuilder.gs          # Utilitaires titres
  DescriptionEngine.gs     # Construction des descriptions
  DescriptionBuilder.gs    # Utilitaires descriptions
  TextExtractors.gs        # Extraction de texte (modele, coupe, couleur, etc.)
  Validator.gs             # Validation SKU et listings
  JsonUtils.gs             # Parsing JSON robuste
  OCR.gs                   # OCR via Google Cloud Vision REST API
  Sidebar.html             # Interface utilisateur (panneau lateral)
  ConfigDialog.html        # Dialogue de configuration
```

## Installation

### 1. Creer le projet Apps Script

1. Ouvrez un Google Sheets
2. Menu **Extensions > Apps Script**
3. Supprimez le contenu par defaut de `Code.gs`

### 2. Copier les fichiers

Copiez le contenu de chaque fichier `.gs` dans un nouveau fichier Apps Script :
- Cliquez sur **+** a cote de "Fichiers" dans l'editeur Apps Script
- Selectionnez **Script** pour les fichiers `.gs`
- Selectionnez **HTML** pour les fichiers `.html`
- Nommez chaque fichier comme dans ce dossier (sans l'extension `.gs`)

Fichiers a creer :
- **Scripts (.gs)** : Code, Config, GeminiClient, Prompt, Models, Templates, Normalizer, TitleEngine, TitleBuilder, DescriptionEngine, DescriptionBuilder, TextExtractors, Validator, JsonUtils, OCR
- **HTML** : Sidebar, ConfigDialog

### 3. Configurer le manifeste

1. Dans l'editeur Apps Script, cliquez sur **Parametres du projet** (icone engrenage)
2. Cochez **Afficher le fichier manifeste "appsscript.json"**
3. Remplacez le contenu de `appsscript.json` par celui de ce dossier

### 4. Configurer les cles API

1. Rechargez votre Google Sheets
2. Un menu **Vinted Assistant** apparait
3. Cliquez sur **Vinted Assistant > Configuration**
4. Entrez votre cle API Gemini (obligatoire)
5. Optionnel : entrez votre cle API Cloud Vision (pour l'OCR)

### 5. Preparer les images

1. Creez un dossier dans Google Drive
2. Uploadez vos photos du vetement dans ce dossier
3. Copiez l'ID du dossier (visible dans l'URL : `https://drive.google.com/drive/folders/[ID_ICI]`)

## Utilisation

1. Ouvrez le panneau : **Vinted Assistant > Ouvrir le panneau**
2. Collez l'ID du dossier Drive et cliquez **Charger les images**
3. **Clic** sur une image = la selectionner pour l'analyse IA
4. **Double-clic** = la marquer pour l'OCR (bordure jaune)
5. Selectionnez le profil d'analyse
6. Remplissez les champs optionnels (taille FR/US, SKU, etc.)
7. Cliquez **Generer l'annonce**
8. Copiez le titre et la description, ou enregistrez dans la feuille

## Profils disponibles

| Profil | Description |
|--------|-------------|
| `jean_levis` | Jean Levi's (modele, coupe, taille FR/US, composition) |
| `pull` | Pull / Gilet (Tommy Hilfiger, vintage, etc.) |
| `jacket_carhart` | Veste Carhartt (modele, doublure, composition) |

## Differences avec la version desktop

| Aspect | Desktop (Python) | Apps Script |
|--------|-----------------|-------------|
| Runtime | Python 3.10+ | Google Apps Script (V8) |
| UI | CustomTkinter | Google Sheets + sidebar HTML |
| Images | Fichiers locaux | Google Drive |
| Config | Fichier .env | Script Properties |
| API Gemini | google-genai SDK | UrlFetchApp REST |
| OCR | google-cloud-vision SDK | Cloud Vision REST API |
| Extension Chrome | Oui (browser_bridge) | Non (copier/coller) |
| Threading | ThreadPoolExecutor | Single-threaded |
| Limite | Aucune | 6 min par execution |

## Limites Apps Script

- **6 minutes max** par execution de fonction
- **Single-threaded** : pas de traitement parallele
- **Images via Drive** : les images doivent etre dans Google Drive
- **Taille max** : 50 MB par requete UrlFetchApp
- **Quotas** : limites quotidiennes sur UrlFetchApp (20 000 appels/jour)

## Obtenir les cles API

### Gemini API
1. Allez sur [AI Studio](https://aistudio.google.com/app/apikey)
2. Cliquez "Create API key"
3. Copiez la cle

### Cloud Vision API (optionnel)
1. Allez sur [Google Cloud Console](https://console.cloud.google.com/)
2. Activez l'API Cloud Vision
3. Creez une cle API dans "Identifiants"
