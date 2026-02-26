# Vinted Assistant Online - Google Apps Script

Application web autonome pour generer des annonces Vinted a partir de photos. Deployee via Google Apps Script, accessible par un simple lien URL partageable.

Les photos sont uploadees directement depuis votre ordinateur (pas besoin de Google Drive).

## Architecture

```
appscript/
  appsscript.json          # Manifeste Apps Script (webapp + scopes)
  Code.gs                  # Point d'entree doGet(), generation, logging
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
  WebApp.html              # Interface utilisateur (page web complete)
```

## Prerequis : obtenir une cle API Gemini

Avant tout, vous devez obtenir une cle API Gemini gratuite :

1. Allez sur **https://aistudio.google.com/app/apikey**
2. Connectez-vous avec votre compte Google
3. Cliquez **"Create API key"**
4. Selectionnez un projet Google Cloud (ou creez-en un)
5. Copiez la cle generee (commence par `AIzaSy...`)
6. Gardez-la de cote, vous en aurez besoin a l'etape 5

## Installation et deploiement

### 1. Creer le projet Apps Script

1. Allez sur [script.google.com](https://script.google.com/)
2. Cliquez **Nouveau projet**
3. Renommez-le "Vinted Assistant"

### 2. Copier les fichiers

Copiez le contenu de chaque fichier dans un nouveau fichier Apps Script :

**Scripts (.gs)** — Cliquez **+** > **Script** pour chacun :

| # | Nom (sans .gs) | Fichier source |
|---|----------------|----------------|
| 1 | `Code` | Code.gs (remplacer le contenu existant) |
| 2 | `Config` | Config.gs |
| 3 | `GeminiClient` | GeminiClient.gs |
| 4 | `Prompt` | Prompt.gs |
| 5 | `Models` | Models.gs |
| 6 | `Templates` | Templates.gs |
| 7 | `Normalizer` | Normalizer.gs |
| 8 | `TitleEngine` | TitleEngine.gs |
| 9 | `TitleBuilder` | TitleBuilder.gs |
| 10 | `DescriptionEngine` | DescriptionEngine.gs |
| 11 | `DescriptionBuilder` | DescriptionBuilder.gs |
| 12 | `TextExtractors` | TextExtractors.gs |
| 13 | `Validator` | Validator.gs |
| 14 | `JsonUtils` | JsonUtils.gs |

**HTML** — Cliquez **+** > **HTML** :

| # | Nom (sans .html) | Fichier source |
|---|------------------|----------------|
| 1 | `WebApp` | WebApp.html |

### 3. Configurer le manifeste

1. Cliquez **Parametres du projet** (icone engrenage dans la barre laterale)
2. Cochez **Afficher le fichier manifeste "appsscript.json"**
3. Revenez dans l'editeur, ouvrez `appsscript.json`
4. Remplacez tout le contenu par celui de `appscript/appsscript.json`
5. Sauvegardez (Ctrl+S)

### 4. Deployer en tant que Web App

1. Cliquez **Deployer** > **Nouveau deploiement**
2. A cote de "Type", cliquez l'icone engrenage et selectionnez **Application Web**
3. Remplissez :
   - **Description** : "Vinted Assistant v1.0"
   - **Executer en tant que** : **Moi**
   - **Qui a acces** : **Tout le monde**
4. Cliquez **Deployer**
5. **Autorisez le script** quand Google le demande :
   - Cliquez "Examiner les autorisations"
   - Choisissez votre compte Google
   - "Avancees" > "Acceder a Vinted Assistant (non securise)"
   - "Autoriser"
6. **Copiez l'URL** de la web app — c'est le lien a partager avec vos collegues !

### 5. Configurer l'application

1. Ouvrez l'URL de la web app dans votre navigateur
2. Cliquez l'icone **engrenage** en haut a droite
3. Collez votre **cle API Gemini** (obligatoire)
4. Choisissez le **modele Gemini** souhaite
5. Optionnel : entrez l'**ID du Google Sheet** pour les logs (voir section ci-dessous)
6. Cliquez **Enregistrer**

## Utilisation

1. Ouvrez l'URL de la web app
2. **Cliquez ou glissez-deposez** vos photos depuis votre ordinateur
3. Les images chargees sont toutes selectionnees par defaut (cliquez pour deselectionner)
4. Selectionnez le profil d'analyse
5. Remplissez les champs optionnels (taille, SKU, prix, premium...)
6. Cliquez **Generer l'annonce**
7. Copiez le titre et la description
8. Optionnel : cliquez **Enregistrer dans le Sheet de log**

## Configurer le Sheet de log

Pour loguer les details de chaque generation dans un Google Sheet :

1. Allez sur **https://sheets.google.com**
2. Creez un **nouveau classeur** (ou ouvrez un existant)
3. Dans l'URL du classeur, copiez l'**ID** :
   ```
   https://docs.google.com/spreadsheets/d/[COPIEZ_CET_ID]/edit
   ```
4. Dans l'app, ouvrez la **Configuration** (icone engrenage)
5. Collez l'ID dans le champ **"ID du Google Sheet de log"**
6. Cliquez **Enregistrer**

L'application creera automatiquement un onglet "Logs" avec les en-tetes.

> **Important** : le compte Google qui a deploye l'app doit avoir acces en ecriture au classeur.

### Colonnes du log

| Colonne | Description |
|---------|-------------|
| Date | Date/heure de la generation |
| Profil | Profil d'analyse utilise |
| Type article | Jean, Pull, Veste... |
| Marque | Marque detectee |
| Modele | Modele detecte |
| Taille FR | Taille francaise |
| Taille US | Taille americaine |
| Couleur | Couleur principale |
| Matiere | Matiere principale |
| Coupe | Coupe (pour les jeans) |
| Genre | Homme / Femme |
| Prix | Prix saisi manuellement |
| Premium | Oui / Non |
| SKU | Code produit interne |
| Order ID | ID de commande |
| Etat | Etat du vetement |
| Titre | Titre genere |
| Description | Description generee |

## Profils disponibles

| Profil | Description |
|--------|-------------|
| `jean_levis` | Jean Levi's (modele, coupe, taille FR/US, composition) |
| `pull` | Pull / Gilet (Tommy Hilfiger, vintage, etc.) |
| `jacket_carhart` | Veste Carhartt (modele, doublure, composition) |

## Partager avec vos collegues

Envoyez simplement l'URL de la web app. Vos collegues pourront l'utiliser depuis n'importe quel navigateur, quel que soit leur OS (Windows, Mac, Linux, mobile).

> **Note** : les collegues utilisent votre cle API Gemini (car le script s'execute en tant que vous). Ils n'ont rien a configurer de leur cote.

## Mettre a jour l'application

Apres une modification du code :
1. Cliquez **Deployer** > **Gerer les deploiements**
2. Cliquez l'icone **crayon** sur le deploiement actif
3. Changez la version en **Nouvelle version**
4. Cliquez **Deployer**

L'URL reste la meme, vos collegues verront la mise a jour automatiquement.

## Limites Apps Script

- **6 minutes max** par execution de fonction
- **Single-threaded** : pas de traitement parallele
- **Upload images** : les photos sont redimensionnees cote navigateur (max 1500px) pour optimiser le transfert
- **Taille max** : ~50 MB par appel `google.script.run`
- **Quotas** : limites quotidiennes sur UrlFetchApp (20 000 appels/jour)
