/**
 * Vinted Assistant Online - Google Apps Script
 *
 * Point d'entree principal.
 * Accessible via le menu Sheets "Vinted Assistant > Lancer l'assistant"
 * ou en tant que Web App autonome via doGet().
 */
// ============================================================
// Menu Google Sheets
// ============================================================
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Vinted Assistant')
    .addItem('Lancer l\'assistant', 'launchAssistant')
    .addSeparator()
    .addItem('Créer / Mettre à jour les statistiques', 'createOrUpdateStatistics')
    .addItem('📊 Ouvrir le dashboard', 'openDashboard')
    .addSeparator()
    .addItem('Configurer le lien de l\'assistant', 'configureWebAppUrl')
    .addToUi();
}
/**
 * Ouvre la web app dans un nouvel onglet du navigateur.
 * Affiche un petit dialog avec le lien cliquable.
 */
function launchAssistant() {
  var url = Config.getWebAppUrl();
  if (!url) {
    SpreadsheetApp.getUi().alert(
      'Lien non configure',
      'Le lien vers la web app n\'est pas encore configure.\n\n' +
      'Allez dans : Vinted Assistant > Configurer le lien de l\'assistant',
      SpreadsheetApp.getUi().ButtonSet.OK
    );
    return;
  }
  var html = HtmlService.createHtmlOutput(
    '<html><head><style>' +
    'body{font-family:Google Sans,Roboto,sans-serif;display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;margin:0;padding:16px;box-sizing:border-box;}' +
    '.btn{display:inline-block;padding:10px 28px;background:#09B1BA;color:#fff;text-decoration:none;border-radius:8px;font-size:15px;font-weight:500;cursor:pointer;border:none;transition:background .2s;}' +
    '.btn:hover{background:#078a91;}' +
    '.hint{font-size:12px;color:#888;margin-top:10px;}' +
    '</style></head><body>' +
    '<a class="btn" href="' + url + '" target="_blank" ' +
    'onclick="setTimeout(function(){google.script.host.close()},500);">' +
    'Ouvrir Vinted Assistant</a>' +
    '<p class="hint">Cliquez le bouton pour ouvrir l\'assistant dans un nouvel onglet.</p>' +
    '</body></html>'
  ).setWidth(340).setHeight(130);
  SpreadsheetApp.getUi().showModalDialog(html, 'Vinted Assistant');
}
/**
 * Dialog pour configurer / mettre a jour le lien de la web app.
 */
function configureWebAppUrl() {
  var currentUrl = Config.getWebAppUrl();
  var ui = SpreadsheetApp.getUi();
  var response = ui.prompt(
    'Configurer le lien Vinted Assistant',
    'Collez l\'URL de deploiement de la web app :\n' +
    '(ex: https://script.google.com/macros/s/.../exec)\n\n' +
    'URL actuelle : ' + (currentUrl || '(non configure)'),
    ui.ButtonSet.OK_CANCEL
  );
  if (response.getSelectedButton() === ui.Button.OK) {
    var newUrl = response.getResponseText().trim();
    if (newUrl) {
      Config.setWebAppUrl(newUrl);
      ui.alert('Lien mis a jour !', 'Le lien a ete enregistre avec succes.', ui.ButtonSet.OK);
    }
  }
}
// ============================================================
// Web App Entry Point (acces par URL)
// ============================================================
function doGet() {
  return HtmlService.createHtmlOutputFromFile('WebApp')
    .setTitle('Vinted Assistant')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}
// ============================================================
// Configuration (appelees depuis le HTML)
// ============================================================
function getConfig() {
  return Config.getAll();
}
function saveConfig(config) {
  Config.setGeminiApiKey(config.geminiApiKey || '');
  Config.setGeminiModel(config.geminiModel || '');
  if (config.openAiApiKey !== undefined) {
    Config.setOpenAiApiKey(config.openAiApiKey || '');
  }
  if (config.openAiModel !== undefined) {
    Config.setOpenAiModel(config.openAiModel || '');
  }
  if (config.aiProvider !== undefined) {
    Config.setAiProvider(config.aiProvider || 'gemini');
  }
  if (config.logSheetId !== undefined) {
    Config.setLogSheetId(config.logSheetId || '');
  }
  return { success: true };
}
// ============================================================
// Generation d'annonce (appelee depuis le HTML)
// ============================================================
/**
 * Genere une annonce Vinted a partir d'images uploadees.
 *
 * @param {Object} params
 * @param {Object[]} params.imageDataArray - Images en base64 [{base64, mimeType, name}]
 * @param {string} params.profileName - Nom du profil (jean_levis, pull, jacket_carhart)
 * @param {Object} params.uiData - Donnees saisies manuellement (tailles, SKU, prix, premium, etc.)
 * @returns {Object} Resultat avec title, description, features, etc.
 */
function generateListing(params) {
  try {
    var imageDataArray = params.imageDataArray || [];
    var profileName = params.profileName || 'jean_levis';
    var uiData = params.uiData || {};
    if (imageDataArray.length === 0) {
      return { error: 'Aucune image selectionnee.' };
    }
    // Valider que les images contiennent effectivement des donnees base64
    var validImages = [];
    for (var i = 0; i < imageDataArray.length; i++) {
      var img = imageDataArray[i];
      if (img && img.base64 && img.base64.length > 100 && img.mimeType) {
        validImages.push(img);
      } else {
        Logger.log('generateListing: image ' + i + ' ignoree (base64 manquant ou tronque, taille=' + (img && img.base64 ? img.base64.length : 0) + ')');
      }
    }
    if (validImages.length === 0) {
      return { error: 'Les images ont ete perdues lors du transfert (payload trop volumineux). Reduisez le nombre de photos ou leur resolution, puis reessayez.' };
    }
    imageDataArray = validImages;
    var profile = Templates.getProfile(profileName);
    if (!profile) {
      return { error: 'Profil d\'analyse inconnu : ' + profileName };
    }
    // Appel IA (dispatcher provider : Gemini / OpenAI selon Config.AI_PROVIDER,
    // avec fallback cross-provider automatique sur quota epuise).
    var geminiResult = AIClient.generateContent(
      imageDataArray,
      profile,
      uiData
    );
    if (geminiResult.error) {
      return geminiResult;
    }
    // Parse JSON
    var parsed = JsonUtils.safeJsonParse(geminiResult.text);
    if (!parsed) {
      return {
        error: 'Reponse IA illisible (JSON invalide).',
        rawText: geminiResult.text
      };
    }
    // Verifier le statut AI
    var aiMeta = parsed.ai || {};
    var aiStatus = (aiMeta.status || '').toLowerCase().trim();
    if (aiStatus && aiStatus !== 'ok' && aiStatus !== 'needs_user_input') {
      return {
        error: 'IA status: ' + aiStatus + ' - ' + (aiMeta.reason || 'raison inconnue'),
        missing: aiMeta.missing || [],
        rawText: geminiResult.text
      };
    }
    // Normalisation + post-traitement
    var normalized = Normalizer.normalizeAndPostprocess(parsed, profileName, uiData);
    // Corriger size_fr : FR = US+10 arrondi au pair superieur
    if (normalized.features) {
      ensureEvenFrSize_(normalized.features);
      // Normaliser la coupe en 3 categories
      if (profileName === 'jean_levis' && normalized.features.fit) {
        normalized.features.fit = normalizeFitCategory_(normalized.features.fit);
      }
    }
    // Injecter les defauts IA dans features pour le pricing
    if (normalized.features && !normalized.features.defects) {
      var aiDef = parsed.defects || (parsed.features || {}).defects;
      if (aiDef) normalized.features.defects = aiDef;
    }
    // Calculer prix conseille et prix neuf AVANT la description
    var pricingResult = { price: null, retail: '' };
    if (profileName === 'jean_levis') {
      pricingResult = calculateRecommendedPrice_(normalized.features || {});
      if (pricingResult.retail) {
        normalized.features.retail_price_range = pricingResult.retail;
      }
    } else if (profileName === 'short_adidas') {
      pricingResult = calculateShortAdidasPrice_(normalized.features || {});
      if (pricingResult.retail) {
        normalized.features.retail_price_range = pricingResult.retail;
      }
    }
    // Reconstruire titre/description avec la taille FR corrigee
    normalized.title = TitleEngine.buildTitle(profileName, normalized.features);
    normalized.description = DescriptionEngine.buildDescription(
      profileName, normalized.features,
      parsed.description || '', parsed.defects || (parsed.features || {}).defects || null
    );
    // Construire le resultat final
    var listing = Models.createListing(normalized);
    var generationCost = calculateGenerationCost_(geminiResult);
    return {
      success: true,
      title: listing.title,
      description: listing.description,
      brand: listing.brand,
      features: listing.features,
      sku: listing.sku,
      skuStatus: listing.skuStatus,
      recommended_price: pricingResult.price,
      retail_price_range: pricingResult.retail,
      generation_cost: generationCost,
      aiDescription: parsed.description || '',
      aiDefects: parsed.defects || (parsed.features || {}).defects || null,
      rawText: geminiResult.text
    };
  } catch (err) {
    Logger.log('generateListing error: ' + err.message + '\n' + err.stack);
    return { error: 'Erreur inattendue : ' + err.message };
  }
}
// ============================================================
// Correction / reconstruction d'annonce
// ============================================================
/**
 * Reconstruit le titre et la description a partir de features corrigees.
 *
 * @param {Object} params
 * @param {string} params.profileName - Profil (jean_levis, pull, jacket_carhart)
 * @param {Object} params.features - Features corrigees par l'utilisateur
 * @param {string} params.aiDescription - Description brute de l'IA (pour le template)
 * @param {string|null} params.aiDefects - Defauts detectes par l'IA
 * @returns {Object} { success, title, description, features }
 */
function rebuildListing(params) {
  try {
    var profileName = params.profileName || 'jean_levis';
    var features = params.features || {};
    var aiDescription = params.aiDescription || '';
    var aiDefects = params.aiDefects || null;
    // Corriger size_fr avant reconstruction
    ensureEvenFrSize_(features);
    // Normaliser la coupe en 3 categories
    if (profileName === 'jean_levis' && features.fit) {
      features.fit = normalizeFitCategory_(features.fit);
    }
    // Normaliser l'état utilisateur AVANT pricing / title / description :
    // les corrections UI ("bon état", "good", etc.) doivent toujours être
    // ramenées à l'une des 3 valeurs canoniques attendues par les moteurs.
    if (profileName === 'jean_levis' && features.condition) {
      features.condition = Normalizer.normalizeJeanConditionLabel(features.condition);
    }
    // Injecter les defauts IA dans features pour le pricing
    if (!features.defects && aiDefects) {
      features.defects = aiDefects;
    }
    // Calculer prix conseille et prix neuf AVANT la description
    var rebuildPricing = { price: null, retail: '' };
    if (profileName === 'jean_levis') {
      rebuildPricing = calculateRecommendedPrice_(features);
      if (rebuildPricing && rebuildPricing.retail) {
        features.retail_price_range = rebuildPricing.retail;
      }
    } else if (profileName === 'short_adidas') {
      rebuildPricing = calculateShortAdidasPrice_(features);
      if (rebuildPricing && rebuildPricing.retail) {
        features.retail_price_range = rebuildPricing.retail;
      }
    }
    // Si l'utilisateur a saisi un SKU manuellement via le panneau de corrections,
    // on force sku_status = 'ok' pour qu'il soit pris en compte dans le titre.
    if (features.sku && String(features.sku).trim()) {
      features.sku_status = 'ok';
    }
    var title = TitleEngine.buildTitle(profileName, features);
    var description = DescriptionEngine.buildDescription(profileName, features, aiDescription, aiDefects);
    return {
      success: true,
      title: title,
      description: description,
      features: features,
      recommended_price: rebuildPricing.price,
      retail_price_range: rebuildPricing.retail
    };
  } catch (err) {
    Logger.log('rebuildListing error: ' + err.message);
    return { error: 'Erreur reconstruction : ' + err.message };
  }
}
// ============================================================
// Utilitaire : taille FR toujours paire (US+10 arrondi)
// ============================================================
/**
 * Si size_us est renseigne, recalcule size_fr = US+10 arrondi au pair superieur.
 * Modifie l'objet features en place et le retourne.
 */
function ensureEvenFrSize_(features) {
  var sizeUs = features.size_us || '';
  if (sizeUs) {
    var usNum = parseInt(String(sizeUs).replace(/\D/g, ''), 10);
    if (!isNaN(usNum)) {
      var fr = usNum + 10;
      if (fr % 2 !== 0) fr += 1;
      features.size_fr = String(fr);
    }
  }
  return features;
}
// ============================================================
// Normalisation coupe : 3 categories (Skinny / Droit / Évasé)
// ============================================================
function normalizeFitCategory_(fit) {
  if (!fit) return 'Droit';
  var low = String(fit).toLowerCase().trim();
  // Évasé markers (check first to catch "relaxed" before droit)
  var evaseMarkers = ['bootcut', 'boot cut', 'flare', 'évasé', 'evase', 'curve', 'curvy', 'wide', 'baggy', 'loose', 'relaxed', 'barrel'];
  for (var j = 0; j < evaseMarkers.length; j++) {
    if (low.indexOf(evaseMarkers[j]) !== -1) return 'Évasé';
  }
  // Droit markers (check before skinny/slim to catch "slim straight", "slim taper", etc.)
  var droitMarkers = ['straight', 'droit', 'mom', 'boyfriend', 'girlfriend', 'regular', 'taper'];
  for (var i = 0; i < droitMarkers.length; i++) {
    if (low.indexOf(droitMarkers[i]) !== -1) return 'Droit';
  }
  // Skinny/Slim pur (seulement si aucun autre marqueur)
  if (low.indexOf('skinny') !== -1 || low.indexOf('slim') !== -1) return 'Skinny';
  return 'Droit';
}
// ============================================================
// Pricing : barème jean Levi's — stratégie La Seconde Main
// ============================================================
var DEFAULT_BUY_PRICE_HOMME = 9;
var DEFAULT_BUY_PRICE_FEMME = 6;
// Prix d'achat unitaire des shorts Adidas (lot d'achat fournisseur).
// Sert de base à la stratégie de rotation rapide (x3 / x2,5 / x2).
var DEFAULT_BUY_PRICE_SHORT_ADIDAS = 4.98;
/**
 * Table canonique des modèles Levi's nommés reconnus.
 * Source unique utilisée par normalizeLevisModel_(), KNOWN_NAMED_MODELS et
 * categorizePremiumSegment_().
 *
 * Règle d'ordre : les variantes les plus longues en premier pour éviter
 * les captures partielles (ex : "mile high" avant "mile").
 */
var LEVIS_NAMED_MODELS_ = [
  { keys: ['mile high'],               label: 'Mile High'  },
  { keys: ['silver tab', 'silvertab'], label: 'Silver Tab' },
  { keys: ['ribcage'],                 label: 'Ribcage'    },
  { keys: ['wedgie'],                  label: 'Wedgie'     },
  { keys: ['boyfriend'],               label: 'Boyfriend'  },
  { keys: ['girlfriend'],              label: 'Girlfriend' },
  { keys: ['denizen'],                 label: 'Denizen'    },
  { keys: ['signature'],               label: 'Signature'  },
  { keys: ['chino'],                   label: 'Chino'      },
  { keys: ['barstow'],                 label: 'Barstow'    }
];
/** Labels des modèles nommés dans leur ordre canonique d'affichage. */
var KNOWN_NAMED_MODELS_ = LEVIS_NAMED_MODELS_.map(function (nm) { return nm.label; });
/**
 * Modèles Levi's considérés comme désirables / candidats au premium.
 *
 * IMPORTANT : cette fonction sert UNIQUEMENT à signaler qu'une pièce
 * est potentiellement intéressante (501, 505, 550, Ribcage, Silver Tab…).
 * Elle ne doit JAMAIS déclencher seule le barème premium.
 *
 * Le passage en barème premium dépend exclusivement de :
 *   features.is_premium === true
 *
 * Cette information peut être utilisée pour du log ou pour proposer
 * à l'utilisateur de vérifier manuellement si la pièce mérite premium.
 */
function isPremiumCandidateModel_(model) {
  if (!model) return false;
  var low = String(model).toLowerCase();
  var candidates = [
    // Modèles iconiques à forte cote sur le marché de la seconde main
    '501', '505', '550',
    // Coupes contemporaines slim/skinny à forte demande
    '720', '721', '724', '725',
    // Modèles nommés à cote secondaire notable
    'ribcage', 'wedgie', 'mile high',
    'silver tab', 'silvertab'
  ];
  for (var i = 0; i < candidates.length; i++) {
    if (low.indexOf(candidates[i]) !== -1) return true;
  }
  return false;
}
/**
 * Alias historique conservé pour compatibilité.
 *
 * NE PAS utiliser pour décider du barème premium : utiliser
 * `features.is_premium === true` à la place.
 */
function isPremiumModel_(model) {
  return isPremiumCandidateModel_(model);
}
/**
 * Sous-gammes Levi's à traiter avec prudence.
 */
function isBudgetBrand_(brand, model) {
  var combined = ((brand || '') + ' ' + (model || '')).toLowerCase();
  return (
    combined.indexOf('denizen') !== -1 ||
    combined.indexOf('signature') !== -1 ||
    combined.indexOf('chino') !== -1 ||
    combined.indexOf('barstow') !== -1
  );
}
/**
 * Normalise le modèle d'un jean Levi's en une clé canonique.
 *
 *   - 3 chiffres exacts (ex : 501, 505, 550)  → renvoie tel quel
 *   - Modèle nommé reconnu (ex : Boyfriend, Mile High) → renvoie le nom normalisé
 *   - Tout le reste                            → renvoie 'Autres'
 *
 * Insensible à la casse, tolère les variantes orthographiques
 * (ex : "Mile High Super Skinny" → "Mile High", "silvertab" → "Silver Tab").
 *
 * @param {*} rawModel - Valeur brute de la cellule (number | string | null)
 * @returns {string}
 */
function normalizeLevisModel_(rawModel) {
  var modelStr;
  if (typeof rawModel === 'number' && isFinite(rawModel)) {
    modelStr = String(Math.trunc(rawModel));
  } else {
    modelStr = String(rawModel == null ? '' : rawModel).trim();
  }
  if (!modelStr) return 'Autres';
  // Modèles numériques — exactement 3 chiffres
  if (/^\d{3}$/.test(modelStr)) return modelStr;
  // Modèles nommés — utilise la table canonique LEVIS_NAMED_MODELS_
  var low = modelStr.toLowerCase();
  for (var i = 0; i < LEVIS_NAMED_MODELS_.length; i++) {
    var nm = LEVIS_NAMED_MODELS_[i];
    for (var j = 0; j < nm.keys.length; j++) {
      if (low.indexOf(nm.keys[j]) !== -1) return nm.label;
    }
  }
  return 'Autres';
}
/**
 * Catégorise un jean Levi's dans l'un des 4 segments premium.
 *
 * @param {string} brand          - Marque brute (ex : "Levi's", "Denizen")
 * @param {string} normalizedModel - Résultat de normalizeLevisModel_()
 * @param {boolean} isPremium     - Valeur de la colonne Premium / is_premium
 * @returns {'budget'|'confirmed'|'candidate'|'standard'}
 */
function categorizePremiumSegment_(brand, normalizedModel, isPremium) {
  if (isBudgetBrand_(brand, normalizedModel)) return 'budget';
  if (isPremium) return 'confirmed';
  if (isPremiumCandidateModel_(normalizedModel)) return 'candidate';
  return 'standard';
}
function parseSizeNumeric_(sizeRaw) {
  if (!sizeRaw) return null;
  var digits = String(sizeRaw).replace(/\D/g, '');
  return digits ? parseInt(digits, 10) : null;
}
/**
 * Détection simple des défauts pour ajuster le prix.
 */
function hasPricingDefects_(features) {
  features = features || {};
  var condition = String(features.condition || '').toLowerCase().trim();
  if (condition === 'satisfaisant') return true;
  var defectsText = String(features.defects || '').toLowerCase().trim();
  if (!defectsText) return false;
  var negativeTerms = [
    'aucun',
    'sans défaut',
    'sans defaut',
    'parfait',
    'très bon',
    'tres bon',
    'bon état',
    'bon etat',
    'neuf',
    'comme neuf',
    'impeccable',
    'rien à signaler',
    'rien a signaler'
  ];
  for (var n = 0; n < negativeTerms.length; n++) {
    if (defectsText.indexOf(negativeTerms[n]) !== -1) return false;
  }
  var defectTerms = [
    'tache',
    'tâche',
    'usure',
    'déchirure',
    'dechirure',
    'trou',
    'accroc',
    'défaut',
    'defaut',
    'trace',
    'usé',
    'use',
    'abîmé',
    'abime',
    'décoloration',
    'decoloration',
    'jaunissement',
    'peluche',
    'bouloché',
    'bouloche',
    'endommagé',
    'endommage'
  ];
  for (var t = 0; t < defectTerms.length; t++) {
    if (defectsText.indexOf(defectTerms[t]) !== -1) return true;
  }
  return defectsText.length > 0;
}
/**
 * Niveau d'état pour le pricing.
 *
 *   "defect"    : satisfaisant ou défaut textuel détecté → barème défaut existant
 *   "good"      : bon état général → baisse intermédiaire (-2 €) sur le prix
 *                 sans défaut, sans entrer dans le barème défaut
 *   "very_good" : très bon état (défaut) → prix normal sans défaut
 *
 * On réutilise hasPricingDefects_() pour conserver la logique défauts existante
 * (textes "tache", "trou", "satisfaisant", etc.) sans la réécrire.
 */
function getConditionPricingLevel_(features) {
  features = features || {};
  if (hasPricingDefects_(features)) return 'defect';
  var condition = String(features.condition || '').toLowerCase().trim();
  if (condition === 'bon état général' || condition === 'bon etat general') {
    return 'good';
  }
  return 'very_good';
}
/**
 * Applique l'ajustement "bon état général" sur un prix sans défaut.
 *
 * Règle métier : bon état général doit toujours produire un prix
 * STRICTEMENT INFÉRIEUR au prix très bon état. On applique -2 €
 * en garantissant un plancher cohérent (>= 1 €) pour ne jamais
 * tomber à 0 ou en négatif sur les barèmes les plus bas.
 */
function applyGoodConditionDiscount_(price) {
  var adjusted = price - 2;
  if (adjusted < 1) adjusted = 1;
  return adjusted;
}
/**
 * Calcule le prix conseillé pour un jean Levi's.
 *
 * Hiérarchie commerciale (La Seconde Main) :
 *   1. Denizen / Signature  → barème budget strict (≤ 19 €)
 *   2. features.is_premium === true → barème premium
 *   3. Sinon                 → barème Levi's standard
 *
 * Un modèle 501 / 505 / 550 / Ribcage / Silver Tab est considéré comme
 * "candidat premium" (information / suggestion) mais ne déclenche jamais
 * seul le barème premium.
 */
function calculateRecommendedPrice_(features) {
  features = features || {};
  var gender = String(features.gender || '').toLowerCase().trim();
  var model = features.model || '';
  var brand = features.brand || '';
  var fit = normalizeFitCategory_(features.fit).toLowerCase();
  // Le budget Denizen / Signature prime TOUJOURS, même si is_premium=true
  // ou si le modèle est un candidat premium (501, 505, etc.).
  var budget = isBudgetBrand_(brand, model);
  var premium = !budget && features.is_premium === true;
  var premiumCandidate = isPremiumCandidateModel_(model);
  var hasDefects = hasPricingDefects_(features);
  var conditionLevel = getConditionPricingLevel_(features);
  var sizeNum;
  var result;
  if (gender === 'homme') {
    sizeNum = parseSizeNumeric_(features.size_us);
    result = priceHomme_(premium, budget, fit, sizeNum, hasDefects, conditionLevel);
  } else {
    sizeNum = parseSizeNumeric_(features.size_fr);
    result = priceFemme_(premium, budget, fit, sizeNum, hasDefects, conditionLevel);
  }
  Logger.log(
    'calculateRecommendedPrice_: gender=' + gender +
    ' model=' + model +
    ' fit=' + fit +
    ' premium=' + premium +
    ' budget=' + budget +
    ' premiumCandidate=' + premiumCandidate +
    ' hasDefects=' + hasDefects +
    ' conditionLevel=' + conditionLevel +
    ' size=' + sizeNum +
    ' => price=' + result.price + '€' +
    ' acceptable=' + result.acceptable_price + '€' +
    ' floor=' + result.floor_price + '€' +
    ' coefficient=' + result.coefficient
  );
  return result;
}
/**
 * Barème femme — politique La Seconde Main.
 *
 * Denizen / Signature  : 19 € (sans défaut), 16 € (avec défaut), aucune prime grande taille.
 * Standard             : skinny 24 / droit 24 / évasé 25 ; +1 € si FR ≥ 42 ; plafond 26 €.
 *                        Avec défaut : skinny 20 / droit 20 / évasé 21.
 * Premium              : skinny 24 / droit 27 / évasé 27 ; FR ≥ 42 → 29 € max ; plafond 29 €.
 *                        Avec défaut : 22 € quel que soit le fit.
 */
function priceFemme_(premium, budget, fit, sizeNum, hasDefects, conditionLevel) {
  var buyPrice = DEFAULT_BUY_PRICE_FEMME;
  var bigSize = !!(sizeNum && sizeNum >= 42);
  var price;
  var retail;
  var isGood = (conditionLevel === 'good');
  if (budget) {
    // Denizen / Signature : strictement plafonné à 19 €, jamais de prime grande taille.
    retail = '24–45 €';
    price = hasDefects ? 16 : 19;
    if (isGood && !hasDefects) price = applyGoodConditionDiscount_(price);
    return buildPricingResult_(price, buyPrice, retail);
  }
  if (premium) {
    retail = '90–130 €';
    if (hasDefects) {
      price = 22;
    } else if (fit === 'skinny') {
      price = 24;
    } else {
      // Droit / évasé / autres : 27 €, 29 € si FR ≥ 42 (plafond premium femme).
      price = bigSize ? 29 : 27;
    }
    if (isGood && !hasDefects) price = applyGoodConditionDiscount_(price);
    return buildPricingResult_(price, buyPrice, retail);
  }
  // Levi's standard femme.
  retail = '70–110 €';
  if (hasDefects) {
    if (fit === 'évasé') {
      price = 21;
    } else {
      // skinny / droit / autres
      price = 20;
    }
  } else if (fit === 'évasé') {
    price = 25;
  } else {
    // skinny / droit / autres
    price = 24;
  }
  // Prime grande taille : +1 € pour FR ≥ 42, uniquement sans défaut,
  // uniquement sur les vrais Levi's standard. Plafond 26 €.
  if (bigSize && !hasDefects) {
    price = Math.min(price + 1, 26);
  }
  if (isGood && !hasDefects) price = applyGoodConditionDiscount_(price);
  return buildPricingResult_(price, buyPrice, retail);
}
/**
 * Barème homme — politique La Seconde Main.
 *
 * Denizen / Signature  : 19 € (sans défaut), 17 € (avec défaut), aucune prime grande taille.
 * Standard             : skinny 26 / droit 29 / évasé 29 ; W ≥ 38 → droit/évasé 32 € max.
 *                        Avec défaut : skinny 21 / droit 23 / évasé 23.
 * Premium              : skinny 29 / droit 32 / évasé 32 ; W ≥ 38 → droit/évasé 35 € max.
 *                        Avec défaut : 25 € quel que soit le fit.
 */
function priceHomme_(premium, budget, fit, sizeNum, hasDefects, conditionLevel) {
  var buyPrice = DEFAULT_BUY_PRICE_HOMME;
  var bigSize = !!(sizeNum && sizeNum >= 38);
  var price;
  var retail;
  var isGood = (conditionLevel === 'good');
  if (budget) {
    // Denizen / Signature : strictement plafonné à 19 €, jamais de prime grande taille.
    retail = '24–45 €';
    price = hasDefects ? 17 : 19;
    if (isGood && !hasDefects) price = applyGoodConditionDiscount_(price);
    return buildPricingResult_(price, buyPrice, retail);
  }
  if (premium) {
    retail = '90–130 €';
    if (hasDefects) {
      price = 25;
    } else if (fit === 'skinny') {
      price = 29;
    } else {
      // Droit / évasé / autres : 32 €, 35 € si W ≥ 38 (plafond premium homme).
      price = bigSize ? 35 : 32;
    }
    if (isGood && !hasDefects) price = applyGoodConditionDiscount_(price);
    return buildPricingResult_(price, buyPrice, retail);
  }
  // Levi's standard homme.
  retail = '70–110 €';
  if (hasDefects) {
    if (fit === 'skinny') {
      price = 21;
    } else {
      // droit / évasé / autres
      price = 23;
    }
  } else if (fit === 'skinny') {
    price = 26;
  } else {
    // droit / évasé / autres
    price = 29;
  }
  // Grande taille : W ≥ 38 → droit / évasé valorisés à 32 € max si pièce propre.
  // Jamais sur Denizen / Signature.
  if (bigSize && !hasDefects && fit !== 'skinny') {
    price = 32;
  }
  if (isGood && !hasDefects) price = applyGoodConditionDiscount_(price);
  return buildPricingResult_(price, buyPrice, retail);
}
/**
 * Résultat enrichi.
 *
 * price            = prix affiché conseillé (entier, prix rond uniquement)
 * acceptable_price = prix acceptable après négociation
 *                    ≈ price * 0.90, jamais > price
 * floor_price      = prix plancher absolu
 *                    ≈ price * 0.80, jamais > acceptable_price
 *
 * Une protection liée au prix d'achat (x2 / x2.5) est appliquée mais
 * elle ne peut JAMAIS faire dépasser le prix affiché.
 */
function buildPricingResult_(price, buyPrice, retail) {
  var displayPrice = Math.round(price);
  // Règle recommandée : acceptable = price * 0.90, floor = price * 0.80.
  var acceptablePrice = Math.round(displayPrice * 0.90);
  var floorPrice = Math.round(displayPrice * 0.80);
  // Garde-fous : acceptable ≤ prix affiché, floor ≤ acceptable, floor ≤ price.
  if (acceptablePrice > displayPrice) acceptablePrice = displayPrice;
  if (floorPrice > acceptablePrice) floorPrice = acceptablePrice;
  if (floorPrice > displayPrice) floorPrice = displayPrice;
  var margin = displayPrice - buyPrice;
  var coefficient = buyPrice > 0 ? displayPrice / buyPrice : null;
  return {
    price: displayPrice,
    retail: retail,
    buy_price_estimate: buyPrice,
    margin_estimate: Math.round(margin * 100) / 100,
    coefficient: coefficient ? Math.round(coefficient * 100) / 100 : null,
    acceptable_price: acceptablePrice,
    floor_price: floorPrice
  };
}
/**
 * Pricing — short Adidas (rotation rapide).
 *
 * Stratégie produit : sourcing massif à 4,98 € l'unité, objectif rotation
 * rapide sur Vinted. Le prix conseillé n'est pas indexé sur le retail neuf
 * mais sur le prix d'achat, avec 3 paliers multiplicatifs :
 *
 *   - x3   → prix conseillé affiché          (~ 15 €)
 *   - x2,5 → prix acceptable après négociation (~ 12 €)
 *   - x2   → prix plancher absolu             (~ 10 €)
 *
 * En cas de défaut ou de "bon état général", on rétrograde d'un cran :
 * prix conseillé = x2,5, acceptable = x2, plancher = x1,8 (jamais < 1 €).
 *
 * Les paliers sont arrondis à l'euro pour rester sur des prix ronds.
 *
 * @param {Object} features
 * @returns {Object} même forme que buildPricingResult_()
 */
function calculateShortAdidasPrice_(features) {
  features = features || {};
  var buyPrice = DEFAULT_BUY_PRICE_SHORT_ADIDAS;
  var hasDefects = hasPricingDefects_(features);
  var conditionLevel = getConditionPricingLevel_(features);
  var downgrade = hasDefects || conditionLevel === 'good';
  var displayPrice, acceptablePrice, floorPrice;
  if (downgrade) {
    displayPrice = Math.round(buyPrice * 2.5);  // ≈ 12 €
    acceptablePrice = Math.round(buyPrice * 2); // ≈ 10 €
    floorPrice = Math.round(buyPrice * 1.8);    // 9 €
  } else {
    displayPrice = Math.round(buyPrice * 3);    // ≈ 15 €
    acceptablePrice = Math.round(buyPrice * 2.5); // ≈ 12 €
    floorPrice = Math.round(buyPrice * 2);      // ≈ 10 €
  }
  // Garde-fous (cohérents avec buildPricingResult_).
  if (acceptablePrice > displayPrice) acceptablePrice = displayPrice;
  if (floorPrice > acceptablePrice) floorPrice = acceptablePrice;
  if (floorPrice < 1) floorPrice = 1;
  var retail = '20–35 €';
  var margin = displayPrice - buyPrice;
  var coefficient = buyPrice > 0 ? displayPrice / buyPrice : null;
  Logger.log(
    'calculateShortAdidasPrice_: defects=' + hasDefects +
    ' condition=' + conditionLevel +
    ' downgrade=' + downgrade +
    ' => price=' + displayPrice + '€' +
    ' acceptable=' + acceptablePrice + '€' +
    ' floor=' + floorPrice + '€' +
    ' coefficient=' + (coefficient ? Math.round(coefficient * 100) / 100 : null)
  );
  return {
    price: displayPrice,
    retail: retail,
    buy_price_estimate: buyPrice,
    margin_estimate: Math.round(margin * 100) / 100,
    coefficient: coefficient ? Math.round(coefficient * 100) / 100 : null,
    acceptable_price: acceptablePrice,
    floor_price: floorPrice
  };
}
// ============================================================
// Logging dans Google Sheets
// ============================================================
var LOG_HEADERS = [
  'Date', 'Agent', 'Profil', 'Type article', 'Marque', 'Modele', 'Premium',
  'Taille FR', 'Taille US', 'Rise', 'Couleur', 'Matiere', 'Coupe',
  'Genre', 'Motif', 'Origine', 'Etiquettes coupées',
  'Prix', 'Etat', 'SKU', 'Timestamp', 'Duree (min)', 'Coût ($)', 'Défauts'
];
// En-têtes qui doivent être rendus en checkbox dans la feuille "Générations"
var LOG_CHECKBOX_HEADERS = ['Etiquettes coupées', 'Défauts'];
/**
 * Détermine si l'article présente un défaut, pour la colonne checkbox "Défauts".
 *
 * Règles :
 *   - features.defects ou result.aiDefects contient un terme pertinent
 *     (tache, trou, accroc, trace, effilochage, peinture, altération, etc.)
 *   - features.condition vaut "satisfaisant" (implique un défaut visible)
 *
 * @param {Object} features - features de l'article
 * @param {Object} result - résultat de generateListing()
 * @returns {boolean} true si défaut détecté, false sinon
 */
function hasDefectsForLog_(features, result) {
  features = features || {};
  result = result || {};
  var condition = String(features.condition || '').toLowerCase().trim();
  if (condition === 'satisfaisant') return true;
  var aiDefects = String((result && result.aiDefects) || '');
  var rawDefects = String(features.defects || '') + ' ' + aiDefects;
  var dl = rawDefects.toLowerCase().trim();
  if (!dl) return false;
  // Mentions explicites "aucun défaut" / "très bon état" → pas de défaut
  // (sauf si un terme de défaut concret est aussi présent dans le texte)
  var negatives = ['aucun défaut', 'aucun defaut', 'sans défaut', 'sans defaut',
                   'parfait état', 'parfait etat', 'très bon état', 'tres bon etat',
                   'tres bon état', 'très bon etat', 'bon état', 'bon etat',
                   'comme neuf', 'impeccable', 'rien à signaler', 'rien a signaler'];
  var hasNegative = false;
  for (var n = 0; n < negatives.length; n++) {
    if (dl.indexOf(negatives[n]) !== -1) { hasNegative = true; break; }
  }
  // Vocabulaire indiquant un défaut visible (une tâche compte comme défaut).
  // Note: on n'inclut PAS le mot générique "défaut" pour éviter les faux positifs
  // sur "aucun défaut".
  var defectTerms = ['tache', 'tâche', 'tâché', 'tâcher', 'trou', 'trous',
                     'accroc', 'déchirure', 'dechirure', 'usure', 'abîmé', 'abime',
                     'trace', 'effilochage', 'effiloche',
                     'décoloration', 'decoloration', 'jaunissement',
                     'peluche', 'bouloché', 'bouloche', 'endommagé', 'endommage',
                     'peinture', 'altération', 'alteration'];
  for (var t = 0; t < defectTerms.length; t++) {
    if (dl.indexOf(defectTerms[t]) !== -1) return true;
  }
  // Si un terme négatif explicite est présent et aucun défaut concret détecté,
  // on considère qu'il n'y a pas de défaut.
  if (hasNegative) return false;
  // Texte non vide, non trivialement négatif → considéré comme un défaut
  return dl.length > 0;
}
/**
 * Calcule le coût approximatif d'une génération IA en USD,
 * à partir du modèle utilisé et des métadonnées d'utilisation des tokens.
 *
 * Tarifs approximatifs par million de tokens (input / output) :
 *   Gemini 2.5 Flash       : $0.075 / $0.30
 *   Gemini 2.5 Flash Lite  : $0.01875 / $0.075
 *   Gemini 2.0 Flash       : $0.10 / $0.40
 *   GPT-4o                 : $2.50 / $10.00
 *   GPT-4o-mini            : $0.15 / $0.60
 *
 * @param {Object} aiResult - Résultat brut de AIClient.generateContent()
 * @returns {number|null} Coût en USD arrondi à 6 décimales, ou null si inconnu
 */
function calculateGenerationCost_(aiResult) {
  if (!aiResult) return null;
  var model = String(aiResult._usedModel || aiResult.model || '').toLowerCase();
  // Gemini renvoie usageMetadata, OpenAI renvoie usage
  var meta = aiResult.usageMetadata || aiResult.usage || {};
  var inputTokens  = meta.promptTokenCount  || meta.prompt_tokens     || 0;
  var outputTokens = meta.candidatesTokenCount || meta.completion_tokens || 0;
  if (!inputTokens && !outputTokens) return null;
  var inputPrice, outputPrice;
  if (model.indexOf('gemini-2.5-flash-lite') !== -1) {
    inputPrice = 0.01875; outputPrice = 0.075;
  } else if (model.indexOf('gemini-2.5-flash') !== -1) {
    inputPrice = 0.075; outputPrice = 0.30;
  } else if (model.indexOf('gemini-2.0-flash') !== -1) {
    inputPrice = 0.10; outputPrice = 0.40;
  } else if (model.indexOf('gpt-4o-mini') !== -1) {
    inputPrice = 0.15; outputPrice = 0.60;
  } else if (model.indexOf('gpt-4o') !== -1) {
    inputPrice = 2.50; outputPrice = 10.0;
  } else {
    // Fallback générique : tarif Gemini Flash
    inputPrice = 0.10; outputPrice = 0.40;
  }
  var cost = (inputTokens * inputPrice + outputTokens * outputPrice) / 1000000;
  return Math.round(cost * 1000000) / 1000000;
}
/**
 * S'assure que la feuille "Générations" possède toutes les colonnes
 * définies dans LOG_HEADERS, dans le bon ordre, et applique la
 * validation checkbox sur les colonnes listées dans LOG_CHECKBOX_HEADERS.
 *
 * Migration douce : pour chaque colonne attendue absente, insère une
 * nouvelle colonne juste avant le prochain en-tête connu (ou en fin de
 * feuille si aucun en-tête postérieur n'est présent). Les anciennes
 * feuilles reçoivent ainsi automatiquement les nouvelles colonnes
 * (ex: "Motif", "Origine", "Etiquettes coupées") à la bonne place,
 * sans perte de données.
 *
 * Corrige aussi un cas historique où "Coût ($)" se retrouvait après
 * "Défauts" : la colonne mal placée est supprimée puis recréée à la
 * bonne position par l'algorithme générique.
 *
 * @param {Sheet} sheet
 * @returns {{ defects: number, indexByHeader: Object }}
 *   - defects : index 1-based de la colonne "Défauts"
 *   - indexByHeader : map { header → index 1-based } pour tous les en-têtes
 */
function ensureLogHeaders_(sheet) {
  var defectsHeader = 'Défauts';
  var coutHeader = 'Coût ($)';
  function readHeaders() {
    var lc = sheet.getLastColumn();
    if (lc === 0) return [];
    return sheet.getRange(1, 1, 1, lc).getValues()[0]
      .map(function (v) { return String(v).trim(); });
  }
  // Cas 1 : feuille vierge → écriture complète des en-têtes
  if (sheet.getLastColumn() === 0) {
    sheet.getRange(1, 1, 1, LOG_HEADERS.length).setValues([LOG_HEADERS]);
    sheet.getRange(1, 1, 1, LOG_HEADERS.length).setFontWeight('bold');
  } else {
    // Cas 2 : "Coût ($)" est après "Défauts" → ordre incorrect, on le supprime
    // pour que la migration générique le réinsère au bon endroit.
    var existing = readHeaders();
    var coutIdx = existing.indexOf(coutHeader);   // 0-based
    var defIdx  = existing.indexOf(defectsHeader);
    if (coutIdx !== -1 && defIdx !== -1 && coutIdx > defIdx) {
      sheet.deleteColumn(coutIdx + 1); // 1-based
    }
    // Cas 3 : pour chaque en-tête attendu absent, l'insérer à la bonne
    // position relative (juste avant le prochain en-tête déjà présent).
    for (var i = 0; i < LOG_HEADERS.length; i++) {
      var expected = LOG_HEADERS[i];
      var current = readHeaders();
      if (current.indexOf(expected) !== -1) continue;
      // Cherche le prochain en-tête de LOG_HEADERS qui existe déjà :
      // l'insertion se fera juste avant lui pour préserver l'ordre.
      var insertAt = current.length + 1; // par défaut : ajout en fin
      for (var j = i + 1; j < LOG_HEADERS.length; j++) {
        var nextIdx = current.indexOf(LOG_HEADERS[j]);
        if (nextIdx !== -1) { insertAt = nextIdx + 1; break; }
      }
      if (insertAt > current.length) {
        // Append : pas besoin d'insertColumnBefore
        sheet.getRange(1, insertAt).setValue(expected).setFontWeight('bold');
      } else {
        sheet.insertColumnBefore(insertAt);
        sheet.getRange(1, insertAt).setValue(expected).setFontWeight('bold');
      }
    }
  }
  // Construit la map { header → index 1-based } à partir de l'état final
  var finalHeaders = readHeaders();
  var indexByHeader = {};
  for (var k = 0; k < finalHeaders.length; k++) {
    if (finalHeaders[k]) indexByHeader[finalHeaders[k]] = k + 1;
  }
  var defectsColIndex = indexByHeader[defectsHeader] || LOG_HEADERS.length;
  // Nettoyage : si "Coût ($)" porte encore une validation checkbox héritée
  // d'une ancienne migration, on la retire (Coût n'est PAS une checkbox).
  try {
    var maxRows = sheet.getMaxRows();
    var coutColIndex = indexByHeader[coutHeader];
    if (coutColIndex && maxRows > 1) {
      sheet.getRange(2, coutColIndex, maxRows - 1, 1).clearDataValidations();
    }
  } catch (eCout) {
    Logger.log('ensureLogHeaders_ clearDataValidations warning: ' + eCout.message);
  }
  // Applique la validation checkbox sur toutes les colonnes booléennes
  for (var c = 0; c < LOG_CHECKBOX_HEADERS.length; c++) {
    var hdrName = LOG_CHECKBOX_HEADERS[c];
    var colIdx = indexByHeader[hdrName];
    if (!colIdx) continue;
    try {
      var rows = sheet.getMaxRows();
      if (rows > 1) {
        sheet.getRange(2, colIdx, rows - 1, 1).insertCheckboxes();
      }
    } catch (eCk) {
      Logger.log('ensureLogHeaders_ insertCheckboxes warning (' + hdrName + '): ' + eCk.message);
    }
  }
  return { defects: defectsColIndex, indexByHeader: indexByHeader };
}
/**
 * @deprecated Conservé pour compatibilité. Utiliser ensureLogHeaders_().
 * @param {Sheet} sheet
 * @returns {number} index 1-based de la colonne "Défauts"
 */
function ensureDefectsCheckboxColumn_(sheet) {
  return ensureLogHeaders_(sheet).defects;
}
/**
 * Formate un objet Date en horodatage precis : "YYYY-MM-DD HH:mm:ss"
 * Utilise le fuseau horaire du script (Europe/Paris).
 *
 * @param {Date} date
 * @returns {string} Horodatage formate
 */
function formatTimestamp_(date) {
  return Utilities.formatDate(date, Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm:ss');
}
/**
 * Logue le resultat d'une generation dans le Google Sheet configure.
 *
 * @param {Object} result - Resultat de generateListing()
 * @param {Object} params - Parametres originaux (profileName, uiData)
 * @returns {Object} { success: true, row: number } ou { error: string }
 */
function logGenerationToSheet(result, params) {
  try {
    var sheetId = Config.getLogSheetId();
    if (!sheetId) {
      return { error: 'ID du Google Sheet de log non configure. Ouvrez la configuration.' };
    }
    var spreadsheet = SpreadsheetApp.openById(sheetId);
    var sheet = spreadsheet.getSheetByName('Générations') || spreadsheet.insertSheet('Générations');
    // Creer les en-tetes si la feuille est vide
    if (sheet.getLastRow() === 0) {
      sheet.getRange(1, 1, 1, LOG_HEADERS.length).setValues([LOG_HEADERS]);
      sheet.getRange(1, 1, 1, LOG_HEADERS.length).setFontWeight('bold');
    }
    // Garantit la présence de toutes les colonnes attendues + checkbox sur les
    // colonnes booléennes (compat. feuilles existantes : insère "Motif",
    // "Origine", "Etiquettes coupées" si absentes, à la bonne position).
    var headerInfo = ensureLogHeaders_(sheet);
    var defectsColIndex = headerInfo.defects;
    var labelsCutColIndex = headerInfo.indexByHeader['Etiquettes coupées'];
    var timestampColIndex = headerInfo.indexByHeader['Timestamp'];
    var features = result.features || {};
    var uiData = (params && params.uiData) || {};
    var profileName = (params && params.profileName) || '';
    // Determiner le type d'article
    var articleType = features.garment_type || '';
    if (!articleType) {
      if (profileName === 'jean_levis') articleType = 'Jean';
      else if (profileName === 'pull') articleType = 'Pull';
      else if (profileName === 'jacket_carhart') articleType = 'Veste';
      else if (profileName === 'short_carhart') articleType = 'Short Carhartt';
      else if (profileName === 'short_adidas') articleType = 'Short';
    }
    // Taille FR : selon le profil, corrigee au pair superieur
    ensureEvenFrSize_(features);
    var tailleFr = features.size_fr || features.size || '';
    var tailleUs = features.size_us || '';
    // Couleur : peut etre un string ou un array
    var couleur = features.color || '';
    if (!couleur && features.main_colors && features.main_colors.length > 0) {
      couleur = features.main_colors.join(', ');
    }
    // SKU avec prefixe Order ID (ex: 01JLF0091) – déjà paddé par le normalizer
    var skuForLog = features.sku || result.sku || '';
    var orderId = features.order_id || '';
    if (skuForLog && orderId) {
      var pad = Normalizer.zeroPadOrderId(orderId);
      if (pad) skuForLog = pad + skuForLog;
    }
    // Matiere : features.material ou construire depuis composition_materials
    var matiere = features.material || '';
    if (!matiere && features.composition_materials && features.composition_materials.length > 0) {
      matiere = features.composition_materials.join(', ');
    }
    var agentEmail = Session.getActiveUser().getEmail() || '';
    // Rise : meme logique centralisee que titre/description
    var riseNorm = TitleBuilder.normalizeRiseType(
      features.rise_type || uiData.rise_type,
      features.rise_cm
    );
    var riseLabel = '';
    if (riseNorm === 'low') riseLabel = 'Basse';
    else if (riseNorm === 'high') riseLabel = 'Haute';
    else if (riseNorm === 'mid') riseLabel = 'Moyenne';
    // Prix : bareme si non fourni par l'UI
    var price = uiData.price || '';
    if (!price && profileName === 'jean_levis') {
      var priceResult = calculateRecommendedPrice_(features);
      if (priceResult && priceResult.price) price = priceResult.price;
    } else if (!price && profileName === 'short_adidas') {
      var priceResultAdidas = calculateShortAdidasPrice_(features);
      if (priceResultAdidas && priceResultAdidas.price) price = priceResultAdidas.price;
    }
    // Horodatage precis de la generation (colonne Timestamp)
    var now = new Date();
    var timestamp = formatTimestamp_(now);
    // Calculer la duree en minutes depuis la derniere generation
    var newRow = sheet.getLastRow() + 1;
    var dureeMins = '';
    if (newRow > 2 && timestampColIndex) {
      var prevTimestamp = sheet.getRange(newRow - 1, timestampColIndex).getValue();
      if (prevTimestamp) {
        var prevDate = new Date(prevTimestamp);
        if (!isNaN(prevDate.getTime())) {
          dureeMins = Math.round((now.getTime() - prevDate.getTime()) / 60000);
        }
      }
    }
    var hasDefectFlag = hasDefectsForLog_(features, result);
    var generationCost = (result.generation_cost != null) ? result.generation_cost : '';
    var labelsCutFlag = features.labels_cut ? true : false;
    var row = [
      now,
      agentEmail,
      profileName,
      articleType,
      features.brand || result.brand || '',
      (function() {
        var m = features.model || features._raw_model || '';
        if (profileName === 'short_adidas' && features.technology) {
          return m ? m + ' ' + features.technology : features.technology;
        }
        return m;
      })(),
      features.is_premium ? true : false,
      tailleFr,
      tailleUs,
      riseLabel,
      couleur,
      matiere,
      features.fit || '',
      features.gender || '',
      features.pattern || '',
      features.origin_country || '',
      labelsCutFlag,
      price,
      features.condition || '',
      skuForLog,
      timestamp,
      dureeMins,
      generationCost,
      hasDefectFlag
    ];
    sheet.getRange(newRow, 1, 1, row.length).setValues([row]);
    // Force les cellules booléennes en checkbox (toujours sur les bons index,
    // jamais sur "Coût ($)" ou autre colonne adjacente).
    try {
      sheet.getRange(newRow, defectsColIndex).insertCheckboxes().setValue(hasDefectFlag);
    } catch (eCkRow) {
      Logger.log('logGenerationToSheet checkbox warning (Défauts): ' + eCkRow.message);
    }
    if (labelsCutColIndex) {
      try {
        sheet.getRange(newRow, labelsCutColIndex).insertCheckboxes().setValue(labelsCutFlag);
      } catch (eCkLc) {
        Logger.log('logGenerationToSheet checkbox warning (Etiquettes coupées): ' + eCkLc.message);
      }
    }
    // Créer la feuille Statistiques si elle n'existe pas encore
    try {
      ensureStatisticsSheet_(spreadsheet);
    } catch (eStats) {
      Logger.log('ensureStatisticsSheet_ warning: ' + eStats.message);
    }
    return { success: true, row: newRow };
  } catch (err) {
    Logger.log('logGenerationToSheet error: ' + err.message);
    return { error: 'Erreur ecriture log : ' + err.message };
  }
}
// ============================================================
// Menu : création / mise à jour des statistiques
// ============================================================
/**
 * Crée ou recrée la feuille "Statistiques" dans le Google Sheet configuré.
 * Accessible via le menu Sheets "Vinted Assistant > Créer / Mettre à jour les statistiques".
 *
 * - Si la feuille existe déjà, elle est supprimée puis reconstruite (mise à jour complète).
 * - Le Google Sheet utilisé est celui configuré dans Config.LOG_SHEET_ID ;
 *   si aucun ID n'est configuré, le classeur actif est utilisé en fallback.
 */
function createOrUpdateStatistics() {
  var ui = SpreadsheetApp.getUi();
  try {
    var sheetId = Config.getLogSheetId();
    var spreadsheet = sheetId
      ? SpreadsheetApp.openById(sheetId)
      : SpreadsheetApp.getActiveSpreadsheet();
    // Supprimer la feuille existante pour forcer la reconstruction complète
    var existing = spreadsheet.getSheetByName('Statistiques');
    if (existing) {
      spreadsheet.deleteSheet(existing);
    }
    ensureStatisticsSheet_(spreadsheet);
    ui.alert(
      'Statistiques mises à jour',
      'La feuille "Statistiques" a été créée / mise à jour avec succès.',
      ui.ButtonSet.OK
    );
  } catch (err) {
    Logger.log('createOrUpdateStatistics error: ' + err.message);
    ui.alert(
      'Erreur',
      'Impossible de créer les statistiques : ' + err.message,
      ui.ButtonSet.OK
    );
  }
}
// ============================================================
// Feuille Statistiques
// ============================================================
/**
 * Crée la feuille "Statistiques" si elle n'existe pas encore.
 * Cette feuille contient des formules qui agrègent les données
 * de la feuille Générations (modèle, prix, défauts, coût…).
 *
 * @param {Spreadsheet} spreadsheet
 */
function ensureStatisticsSheet_(spreadsheet) {
  var statsName = 'Statistiques';
  // La feuille existe déjà, rien à faire
  if (spreadsheet.getSheetByName(statsName)) return;
  // Insérer avant la feuille Générations (position 0)
  var statsSheet = spreadsheet.insertSheet(statsName, 0);
  statsSheet.setColumnWidth(1, 240);
  statsSheet.setColumnWidth(2, 160);
  var g = "'Générations'";
  var rows = [];
  function add(label, formula) { rows.push([label, formula != null ? formula : '']); }
  function hdr(label) { rows.push([label, '']); }
  function blank() { rows.push(['', '']); }
  hdr('📊 Vue d\'ensemble');
  add('Total articles traités', '=MAX(0;COUNTA(' + g + '!A:A)-1)');
  add('Dernière mise à jour', '=IFERROR(TEXT(MAX(' + g + '!A2:A);"dd/mm/yyyy hh:mm");"—")');
  blank();
  hdr('💰 Prix de vente (€)');
  add('Prix moyen (€)',    '=IFERROR(ROUND(AVERAGE(' + g + '!R2:R);2);"—")');
  add('Prix minimum (€)',  '=IFERROR(MIN(' + g + '!R2:R);"—")');
  add('Prix maximum (€)',  '=IFERROR(MAX(' + g + '!R2:R);"—")');
  blank();
  hdr('👗 Par type d\'article');
  add('Jean Levi\'s',    '=COUNTIF(' + g + '!C2:C;"jean_levis")');
  add('Pull / Gilet',    '=COUNTIF(' + g + '!C2:C;"pull")');
  add('Veste Carhartt',  '=COUNTIF(' + g + '!C2:C;"jacket_carhart")');
  blank();
  hdr('🏷️ Par état');
  add('Très bon état',  '=COUNTIF(' + g + '!S2:S;"tres bon etat")');
  add('Bon état',       '=COUNTIF(' + g + '!S2:S;"bon etat")');
  add('Neuf',           '=COUNTIF(' + g + '!S2:S;"neuf")');
  add('Satisfaisant',   '=COUNTIF(' + g + '!S2:S;"satisfaisant")');
  blank();
  hdr('⚠️ Défauts');
  add('Avec défauts',  '=COUNTIF(' + g + '!X2:X;TRUE)');
  add('Sans défauts',  '=COUNTIF(' + g + '!X2:X;FALSE)');
  blank();
  hdr('👥 Par genre');
  add('Femme',  '=COUNTIF(' + g + '!N2:N;"femme")');
  add('Homme',  '=COUNTIF(' + g + '!N2:N;"homme")');
  blank();
  hdr('🤖 Coûts IA ($)');
  add('Coût total ($)',              '=IFERROR(ROUND(SUM(' + g + '!W2:W);6);"—")');
  add('Coût moyen par article ($)',  '=IFERROR(ROUND(AVERAGE(' + g + '!W2:W);6);"—")');
  blank();
  hdr('🔑 Modèles Levi\'s');
  // Section modèles Levi's : agrégation côté Apps Script (plus robuste qu'une
  // formule QUERY qui souffre de l'inférence de type sur les colonnes mixtes).
  // La fonction normalizeLevisModel_() identifie les modèles 3 chiffres (501…)
  // et les modèles nommés (Boyfriend, Ribcage…) séparément.
  // Seul le résidu vraiment inconnu tombe dans "Autres".
  var generationsSheet = spreadsheet.getSheetByName('Générations');
  var modelHeaderRow = ['Modèle', 'Nb'];
  var modelDataRows = [];
  var namedCounts = {};   // modèles nommés reconnus
  var premiumBreakdown = { budget: 0, standard: 0, candidate: 0, confirmed: 0 };
  var autresCount = 0;
  if (generationsSheet && generationsSheet.getLastRow() >= 2) {
    var lastDataRow = generationsSheet.getLastRow();
    // Colonnes C (Profil) à G (Premium) — 5 colonnes contiguës
    var values = generationsSheet.getRange(2, 3, lastDataRow - 1, 5).getValues();
    var counts = {};
    for (var r = 0; r < values.length; r++) {
      var profil = String(values[r][0] || '').toLowerCase().trim();
      if (profil !== 'jean_levis') continue;
      var rawModel = values[r][3]; // index 3 = col F (Modèle)
      var normalized = normalizeLevisModel_(rawModel);
      if (/^\d{3}$/.test(normalized)) {
        counts[normalized] = (counts[normalized] || 0) + 1;
      } else if (normalized !== 'Autres') {
        namedCounts[normalized] = (namedCounts[normalized] || 0) + 1;
      } else {
        autresCount++;
      }
      // Répartition premium (4 catégories)
      var marqueVal = String(values[r][2] || ''); // index 2 = col E (Marque)
      var isPremVal = (values[r][4] === true) || String(values[r][4]).toLowerCase() === 'true'; // index 4 = col G
      var segment = categorizePremiumSegment_(marqueVal, normalized, isPremVal);
      premiumBreakdown[segment]++;
    }
    var modelKeys = Object.keys(counts);
    modelKeys.sort(function (a, b) {
      var diff = counts[b] - counts[a];
      if (diff !== 0) return diff;
      return a < b ? -1 : (a > b ? 1 : 0);
    });
    for (var k = 0; k < modelKeys.length; k++) {
      modelDataRows.push([modelKeys[k], counts[modelKeys[k]]]);
    }
    // Modèles nommés triés par fréquence décroissante
    var namedKeys = Object.keys(namedCounts).sort(function (a, b) {
      var diff = namedCounts[b] - namedCounts[a];
      return diff !== 0 ? diff : (a < b ? -1 : (a > b ? 1 : 0));
    });
    for (var k2 = 0; k2 < namedKeys.length; k2++) {
      modelDataRows.push([namedKeys[k2], namedCounts[namedKeys[k2]]]);
    }
    if (autresCount > 0) {
      modelDataRows.push(['Autres', autresCount]);
    }
  }
  // Ajoute l'en-tête de tableau (Modèle / Nb) puis les données.
  rows.push(modelHeaderRow);
  for (var d = 0; d < modelDataRows.length; d++) {
    rows.push(modelDataRows[d]);
  }
  var modelHeaderRowIndex = rows.length - modelDataRows.length; // 1-based row of "Modèle | Nb"

  // ---- Section : Modèles nommés Levi's (liste fixe, toujours visible) ----
  blank();
  hdr('🏷 Modèles nommés Levi\'s');
  var namedModelHeader = ['Modèle', 'Nb'];
  rows.push(namedModelHeader);
  var namedModelHeaderRowIndex = rows.length; // 1-based
  for (var nm = 0; nm < KNOWN_NAMED_MODELS_.length; nm++) {
    rows.push([KNOWN_NAMED_MODELS_[nm], namedCounts[KNOWN_NAMED_MODELS_[nm]] || 0]);
  }

  // ---- Section : Par coupe ----
  blank();
  hdr('📐 Par coupe');
  add('Skinny', '=COUNTIF(' + g + '!M2:M;"Skinny")');
  add('Droit',  '=COUNTIF(' + g + '!M2:M;"Droit")');
  add('Évasé',  '=COUNTIF(' + g + '!M2:M;"Évasé")');

  // ---- Section : Candidats premium ----
  blank();
  hdr('💡 Candidats premium');
  var premiumHeader = ['Catégorie', 'Nb'];
  rows.push(premiumHeader);
  var premiumHeaderRowIndex = rows.length; // 1-based
  rows.push(['Budget (Denizen / Signature / Chino / Barstow)', premiumBreakdown.budget]);
  rows.push(['Standard',           premiumBreakdown.standard]);
  rows.push(['Candidat premium',   premiumBreakdown.candidate]);
  rows.push(['Premium confirmé',   premiumBreakdown.confirmed]);
  // Écriture des données
  statsSheet.getRange(1, 1, rows.length, 2).setValues(rows);
  // Style des lignes d'en-tête (détectées par préfixe emoji)
  var headerPrefixes = ['📊', '💰', '👗', '🏷', '🔑', '⚠', '👥', '🤖', '📐', '💡'];
  for (var i = 0; i < rows.length; i++) {
    var label = String(rows[i][0]);
    var isHdr = false;
    for (var p = 0; p < headerPrefixes.length; p++) {
      if (label.indexOf(headerPrefixes[p]) === 0) { isHdr = true; break; }
    }
    if (isHdr) {
      statsSheet.getRange(i + 1, 1, 1, 2)
        .setBackground('#1a73e8').setFontColor('#ffffff').setFontWeight('bold');
    } else if (label) {
      // Alternance légère sur les lignes de données
      statsSheet.getRange(i + 1, 2, 1, 1).setHorizontalAlignment('right');
    }
  }
  // Style spécifique de la ligne d'en-tête de tableau "Modèle | Nb"
  statsSheet.getRange(modelHeaderRowIndex, 1, 1, 2)
    .setFontWeight('bold').setBackground('#e8f0fe');
  // Style des en-têtes de tableaux des nouvelles sections
  statsSheet.getRange(namedModelHeaderRowIndex, 1, 1, 2)
    .setFontWeight('bold').setBackground('#e8f0fe');
  statsSheet.getRange(premiumHeaderRowIndex, 1, 1, 2)
    .setFontWeight('bold').setBackground('#e8f0fe');
}
