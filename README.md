
# Assistant Vinted – Extraction Multimodale & Génération Automatique d’Annonces

L’Assistant Vinted est une application desktop qui permet de **générer automatiquement des annonces Vinted complètes (titre + description + métadonnées)** à partir de **plusieurs photos d’un même vêtement**, en s’appuyant exclusivement sur **Google Gemini** (modèle par défaut : gemini-3-pro-preview, option gemini-2.5-flash).

L’objectif est de **supprimer les tâches répétitives** (rédaction, titres, analyse des photos, extraction des infos, cohérence) et d’obtenir un **cadre de qualité constant**, avec une **approche orientée business** (règles métier Levi’s, nommage optimisé, paramètres réels du vêtement, précision, zéro hallucination).

L’architecture est **modulaire, robuste**, et sépare clairement l’UI, les clients IA, les modèles métier, et les profils d’analyse.


## ✨ Fonctionnalités principales

### Extraction d’informations à partir d’images
- Import **plusieurs photos du même article**
  - étiquettes (marque, taille, composition)
  - SKU manuscrits ou imprimés
  - photos globales et détails
  - mesures à plat avec mètre ruban
- **OCR dédié** pour les étiquettes (Google Vision), activé uniquement sur les images cochées "OCR" dans la galerie
- Extraction structurée par IA → JSON brut
- **Zéro invention**
- Gestion des incertitudes, champs null si doute

### Génération automatique de l’annonce
- **Titre optimisé**
  - ordre métier strict
  - normalisation coupe
  - tailles FR/US
  - % coton et stretch
  - genre et couleur
- **Description complète**
  - modèle, coupe
  - composition textile
  - mesures réalistes
  - état visuel
- Modèle VintedListing standardisé

### Modèle IA
- Provider unique : Google Gemini
- Modèle par défaut : **gemini-3-pro-preview**
- Option alternative : **gemini-2.5-flash**
- OCR : **Google Vision** (texte injecté dans le prompt Gemini lorsque présent)
- Fallback contrôlé : si la réponse Gemini est invalide, l’app affiche un avertissement “Résultat partiel (fallback)” et conserve l’UI opérationnelle.

### Architecture claire
- **Prompt contract** unique
- **Profiles** d’analyse (ex: jean Levi’s)
- **Normalizer** suivi d’un **Title builder**
- Séparation UI / Domain / Infrastructure

---

## 🏗 Architecture

```

AssistantVinted/
│
├── main.py
│
├── domain/
│   ├── prompt.py              # Contrat de prompt partagé
│   ├── templates/             # Profils d'analyse
│   │     ├── base.py
│   │     ├── jeans.py
│   │     └── **init**.py
│   ├── models.py              # modèle VintedListing
│   ├── normalizer.py          # merge AI+UI + génération titre
│   ├── title_builder.py       # règles métier Levi’s
│   ├── title_engine.py        # orchestration des titres
│   ├── description_engine.py  # orchestration des descriptions
│   ├── json_utils.py          # parsing robuste JSON IA
│
├── infrastructure/
│   ├── ai_factory.py          # provider abstrait
│   ├── gemini_client.py       # Gemini Vision+Texte
│   ├── google_vision_ocr.py   # provider OCR (Google Vision)
│   ├── http_utils.py
│
└── presentation/
├── ui_app.py              # UI CustomTkinter
├── assets/
└── …

````

---

## 🔥 Flux complet

**1) L’utilisateur fournit :**
- modèle Gemini
- profil d’analyse (ex: jean Levi’s)
- 1 à 10 images

**2) L’IA :**
- construit le prompt contract
- encode les images en base64
- appelle l’API
- renvoie un JSON brut

**3) Le normalizer :**
- extrait les features
- fusionne avec données UI si présentes
- applique les règles métier
- génère le titre final
- renvoie un dict final

**4) Modèle :**
```python
listing = VintedListing.from_dict(normalized)
````

**5) L’UI affiche**

* titre final
* description brute IA
* métadonnées

---

## 🧠 Prompt Contract

Un **contrat JSON strict**, identique entre modèles :

* extraction multi-image
* champ JSON fixe
* null si information incertaine
* aucune invention
* format déterministe

Cela garantit un comportement **stable** avec Gemini (quel que soit le modèle sélectionné).

---

## 🎯 Règles métier Levi’s (Title Builder)

Le titre suit un ordre **strict** :

```
Jean Levi's 501 FR42 W32 coupe Straight/Droit taille basse 100% coton homme bleu brut
```

Ordre des éléments :

1. Type (Jean)
2. Marque (Levi’s)
3. Modèle (501, 511, …)
4. Taille FR
5. Taille US (Wxx)
6. Coupe normalisée
7. Taille basse (si applicable)
8. % coton (si >=60%)
9. stretch (si >=2% élasthanne)
10. Genre
11. Couleur
12. SKU (si présent)

**Note** :
Longueur de jambe (Lxx) retirée du titre (trop bruyant).
Présente uniquement dans la description.

---

## 🚀 Installation

### Prérequis

* Python **3.10+**
* API key :

  * Google Gemini

### Installation

Pour un Chromebook (Crostini), exécute d'abord le script dédié qui installe les dépendances système (Tkinter, bibliothèques GUI) et prépare l'environnement Python :

```bash
./scripts/setup_crostini.sh
```

Sur un environnement classique :

```bash
git clone <repo>
cd AssistantVinted
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Configurer les clés via l'assistant interactif (recommandé pour les nouvelles machines) :

```bash
./scripts/configure_api_keys.py
```

L'assistant te demandera le modèle Gemini par défaut (gemini-3-pro-preview recommandé), la clé correspondante et le modèle à utiliser. Un fichier `.env` est généré avec tes choix. Tu peux également créer ou éditer manuellement un fichier `.env` :

```
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3-pro-preview
```

---

### Activer l'OCR Google Vision

1. Assure-toi d'avoir un compte de service Google Cloud Vision et un fichier de credentials JSON.
2. Défini la variable d'environnement `GOOGLE_APPLICATION_CREDENTIALS` vers ce fichier avant de lancer l'application :

   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS=/chemin/vers/ta-cle-vision.json
   ```

3. Dans l'UI, coche la case **OCR** sur chaque vignette correspondant à une étiquette (composition, taille, codes). Ces images seront traitées par l'OCR et **ne seront pas envoyées à Gemini**, sauf en cas de fallback contrôlé.
4. Le texte OCR extrait est injecté tel quel dans le prompt Gemini, uniquement en complément des autres images.

En absence de credentials ou si le service est indisponible, l'application continue de fonctionner en mode dégradé (sans OCR) avec journalisation explicite.

---

### Logs & diagnostics (PyCharm Community)

- Le niveau de log est réglé sur DEBUG par défaut (`setup_logging(logging.DEBUG)` dans `main.py`) : vérifie dans PyCharm que l’onglet **Run** n’applique pas de filtre.
- En cas de fallback JSON, l’UI affiche un avertissement (“Résultat partiel (fallback)”) et le log détaille la raison + un extrait du texte Gemini (tronqué). Consulte l’onglet Run pour diagnostiquer.
- Pour l’OCR, si `GOOGLE_APPLICATION_CREDENTIALS` est absent ou invalide, le log indique le passage en mode dégradé (noop). Assure-toi que la variable d’environnement est bien renseignée dans ta configuration PyCharm (Run Configuration > Environment variables).

## ▶️ Exécution

```bash
python main.py
```

Interface graphique simple :

* sélection des images
* choix du modèle Gemini
* sélection du profile
* génération automatique

---

## 🧩 Extension de l’application

Ajouter un **nouveau type de vêtement** :

1. Créer un fichier dans `domain/templates/`
2. Ajouter son nom dans `ALL_PROFILES`
3. Créer `build_<type>_title`
4. Étendre `normalize_and_postprocess`

Aucune modification du cœur de l’application.

---

## 🧭 Roadmap

### Court terme

* Flags UI sur infos incertaines
* Support Levi’s SilverTab et 501XX
* Gestion complète SKU : photo > OCR > doute > manuel

### Moyen terme

* Profils :

  * polaires TNF
  * doudounes Patagonia
  * sweats Tommy
* Prix auto et estimation marge
* Export direct vers Vinted (draft)

### Long terme

* Suite complète « Vinted Pro »

  * SEO interne
  * analyse concurrence
  * pricing dynamique
  * multi-plateformes (Vinted, LBC, eBay)
  * pipeline industrialisé

---

## 🎯 Objectif stratégique

L’objectif final est de **standardiser la qualité des annonces**, pour permettre :

* productivité ×5
* homogénéité du catalogue
* marges plus stables
* réduction des erreurs factuelles
* industrialisation de la publication

L’outil met l’accent sur **exactitude**, **pragmatisme**, et **exploitation business**, plutôt que sur du marketing flou ou des hallucinations IA.

---

## 👤 Auteur

Développé par **Kevin Andréazza**, dans le but de créer un **assistant complet** à la vente de vêtements en seconde main, automatisé, fiable et extensible, orienté marque et règles métier.

---
