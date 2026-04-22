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
// Pricing : bareme jean Levi's
// ============================================================
function isPremiumModel_(model) {
  if (!model) return false;
  var low = String(model).toLowerCase();
  var premiums = ['501', '505', '550', 'ribcage'];
  for (var i = 0; i < premiums.length; i++) {
    if (low.indexOf(premiums[i]) !== -1) return true;
  }
  return false;
}
function isBudgetBrand_(brand, model) {
  var combined = ((brand || '') + ' ' + (model || '')).toLowerCase();
  return combined.indexOf('denizen') !== -1 || combined.indexOf('signature') !== -1;
}
function parseSizeNumeric_(sizeRaw) {
  if (!sizeRaw) return null;
  var digits = String(sizeRaw).replace(/\D/g, '');
  return digits ? parseInt(digits, 10) : null;
}
/**
 * Calcule le prix conseille pour un jean Levi's selon le bareme.
 * @param {Object} features
 * @returns {Object} { price: number, retail: string }
 */
function calculateRecommendedPrice_(features) {
  var gender = (features.gender || '').toLowerCase().trim();
  var model = features.model || '';
  var brand = features.brand || '';
  var fit = normalizeFitCategory_(features.fit).toLowerCase();
  var premium = isPremiumModel_(model) || (features.is_premium === true);
  var budget = !premium && isBudgetBrand_(brand, model);
  var defectsText = features.defects || '';
  var condition = (features.condition || '').toLowerCase().trim();
  var hasDefects = false;
  // 1) Condition "satisfaisant" implique des defauts
  if (condition === 'satisfaisant') {
    hasDefects = true;
  }
  // 2) Analyser le texte de defauts (si present)
  if (!hasDefects && defectsText) {
    var dl = defectsText.toLowerCase();
    if (dl.indexOf('aucun') === -1 && dl.indexOf('sans défaut') === -1 && dl.indexOf('parfait') === -1
        && dl.indexOf('tres bon') === -1 && dl.indexOf('très bon') === -1
        && dl.indexOf('bon etat') === -1 && dl.indexOf('bon état') === -1
        && dl.indexOf('neuf') === -1 && dl.indexOf('comme neuf') === -1) {
      var terms = ['tache', 'usure', 'déchirure', 'trou', 'accroc', 'défaut', 'trace', 'usé', 'abîmé',
                   'décoloration', 'jaunissement', 'peluche', 'bouloché', 'endommagé'];
      for (var t = 0; t < terms.length; t++) { if (dl.indexOf(terms[t]) !== -1) { hasDefects = true; break; } }
    }
  }
  var result;
  if (gender === 'homme') {
    var sizeNum = parseSizeNumeric_(features.size_us);
    result = priceHomme_(premium, budget, fit, sizeNum, hasDefects);
  } else {
    var sizeNum = parseSizeNumeric_(features.size_fr);
    result = priceFemme_(premium, budget, fit, sizeNum, hasDefects);
  }
  // Securite finale : plafonner le prix pour rester sur une logique de rotation rapide.
  result.price = applyRotationCap_(result.price, premium, fit, sizeNum, hasDefects, gender);
  Logger.log('calculateRecommendedPrice_: gender=' + gender + ' model=' + model +
    ' fit=' + fit + ' premium=' + premium + ' budget=' + budget +
    ' hasDefects=' + hasDefects + ' size=' + sizeNum + ' => ' + result.price + '€');
  return result;
}
/**
 * Bareme "rotation ultra agressive" femme.
 * Objectif : cashflow et rotation rapide, pas la marge max.
 * Cible majoritaire : 18–23 €. 24–25 € = un peu meilleur. 26 € = zone haute.
 * 28 € = cas exceptionnels seulement. Jamais 30 € en automatique.
 */
function priceFemme_(premium, budget, fit, sizeNum, hasDefects) {
  var bigSize = !!(sizeNum && sizeNum >= 42);
  if (premium) {
    var retailPremium = '90–120 €';
    if (fit === 'évasé') {
      // big size sans defaut : 26 € (cap pourra autoriser 28 € en cas exceptionnel)
      return { price: bigSize ? (hasDefects ? 22 : 26) : (hasDefects ? 21 : 24), retail: retailPremium };
    }
    if (fit === 'skinny') {
      return { price: hasDefects ? 19 : 21, retail: retailPremium };
    }
    // droit (defaut)
    return { price: hasDefects ? 20 : 23, retail: retailPremium };
  }
  if (budget) {
    var retailBudget = '24–45 €';
    // grande taille sans defaut : 20 € max
    return { price: bigSize ? (hasDefects ? 16 : 20) : (hasDefects ? 16 : 19), retail: retailBudget };
  }
  // standard
  var retailStandard = '70–100 €';
  if (fit === 'évasé') {
    return { price: bigSize ? (hasDefects ? 20 : 24) : (hasDefects ? 20 : 23), retail: retailStandard };
  }
  if (fit === 'skinny') {
    return { price: hasDefects ? 18 : 20, retail: retailStandard };
  }
  // droit (defaut)
  return { price: hasDefects ? 20 : 22, retail: retailStandard };
}
/**
 * Bareme "rotation ultra agressive" homme.
 * Meme philosophie que femme : majorite 18–23 €, 26 € zone haute, 28 € exception.
 */
function priceHomme_(premium, budget, fit, sizeNum, hasDefects) {
  var bigSize = !!(sizeNum && sizeNum >= 38);
  if (premium) {
    var retailPremium = '90–120 €';
    if (fit === 'évasé') {
      return { price: bigSize ? (hasDefects ? 22 : 26) : (hasDefects ? 21 : 24), retail: retailPremium };
    }
    if (fit === 'skinny') {
      return { price: hasDefects ? 19 : 21, retail: retailPremium };
    }
    // droit (defaut)
    return { price: hasDefects ? 20 : 23, retail: retailPremium };
  }
  if (budget) {
    var retailBudget = '24–45 €';
    return { price: bigSize ? (hasDefects ? 16 : 20) : (hasDefects ? 16 : 19), retail: retailBudget };
  }
  // standard
  var retailStandard = '70–100 €';
  if (fit === 'évasé') {
    return { price: bigSize ? (hasDefects ? 20 : 24) : (hasDefects ? 20 : 23), retail: retailStandard };
  }
  if (fit === 'skinny') {
    return { price: hasDefects ? 18 : 20, retail: retailStandard };
  }
  // droit (defaut)
  return { price: hasDefects ? 20 : 22, retail: retailStandard };
}
/**
 * Plafond commercial "rotation ultra agressive".
 * Hierarchie :
 * - plafond par defaut         : 23 €
 * - plafond intermediaire       : 25 € si propre ET au moins un signal favorable
 *                                 (premium, grande taille, ou coupe evasee)
 * - plafond haut                : 26 € si propre ET au moins deux signaux favorables
 * - plafond exceptionnel        : 28 € seulement si premium ET propre ET grande taille ET evase
 * - jamais 30 € en automatique
 */
function applyRotationCap_(price, premium, fit, sizeNum, hasDefects, gender) {
  if (typeof price !== 'number' || isNaN(price)) return price;
  var bigSize = !!(sizeNum && sizeNum >= ((gender === 'homme') ? 38 : 42));
  var attractiveFit = (fit === 'évasé');
  var signals = 0;
  if (premium) signals++;
  if (bigSize) signals++;
  if (attractiveFit) signals++;
  var cap = 23;
  if (!hasDefects && signals >= 1) {
    cap = 25;
  }
  if (!hasDefects && signals >= 2) {
    cap = 26;
  }
  if (!hasDefects && premium && bigSize && attractiveFit) {
    cap = 28;
  }
  if (price > cap) return cap;
  return price;
}
// ============================================================
// Logging dans Google Sheets
// ============================================================
var LOG_HEADERS = [
  'Date', 'Agent', 'Profil', 'Type article', 'Marque', 'Modele', 'Premium',
  'Taille FR', 'Taille US', 'Rise', 'Couleur', 'Matiere', 'Coupe',
  'Genre', 'Prix', 'Etat', 'SKU', 'Timestamp', 'Duree (min)', 'Coût ($)', 'Défauts'
];
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
 * S'assure que la colonne "Défauts" existe et est rendue checkbox.
 * Gère aussi la migration des feuilles existantes en ajoutant "Coût ($)"
 * entre "Duree (min)" et "Défauts" si elle est absente.
 *
 * @param {Sheet} sheet
 * @returns {number} index 1-based de la colonne "Défauts"
 */
function ensureDefectsCheckboxColumn_(sheet) {
  var defectsHeader = 'Défauts';
  var coutHeader = 'Coût ($)';
  var lastCol = sheet.getLastColumn();
  // Lecture des en-têtes existants (s'ils existent)
  var existingHeaders = lastCol > 0
    ? sheet.getRange(1, 1, 1, lastCol).getValues()[0].map(function(v) { return String(v).trim(); })
    : [];
  var hasDefects = existingHeaders.indexOf(defectsHeader) !== -1;
  var hasCout = existingHeaders.indexOf(coutHeader) !== -1;
  if (!hasDefects) {
    // Feuille vide ou sans colonne Défauts → réécriture complète des en-têtes
    sheet.getRange(1, 1, 1, LOG_HEADERS.length).setValues([LOG_HEADERS]);
    sheet.getRange(1, 1, 1, LOG_HEADERS.length).setFontWeight('bold');
  } else if (!hasCout) {
    // Migration : "Défauts" existe mais "Coût ($)" est absent →
    // on insère la colonne "Coût ($)" juste avant "Défauts".
    var defautsIdx = existingHeaders.indexOf(defectsHeader); // 0-based
    sheet.insertColumnBefore(defautsIdx + 1); // 1-based
    sheet.getRange(1, defautsIdx + 1).setValue(coutHeader).setFontWeight('bold');
  }
  // Calcul de l'index final (1-based) de la colonne Défauts
  var newHeaders = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  var defectsColIndex = -1;
  for (var i = 0; i < newHeaders.length; i++) {
    if (String(newHeaders[i]).trim() === defectsHeader) { defectsColIndex = i + 1; break; }
  }
  if (defectsColIndex === -1) defectsColIndex = LOG_HEADERS.length;
  // Appliquer la validation checkbox sur toute la colonne (en dehors de l'en-tête)
  try {
    var maxRows = sheet.getMaxRows();
    if (maxRows > 1) {
      sheet.getRange(2, defectsColIndex, maxRows - 1, 1).insertCheckboxes();
    }
  } catch (eCk) {
    Logger.log('ensureDefectsCheckboxColumn_ insertCheckboxes warning: ' + eCk.message);
  }
  return defectsColIndex;
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
    // Garantit la présence de la colonne "Défauts" + checkbox (compat. feuilles existantes)
    var defectsColIndex = ensureDefectsCheckboxColumn_(sheet);
    var features = result.features || {};
    var uiData = (params && params.uiData) || {};
    var profileName = (params && params.profileName) || '';
    // Determiner le type d'article
    var articleType = features.garment_type || '';
    if (!articleType) {
      if (profileName === 'jean_levis') articleType = 'Jean';
      else if (profileName === 'pull') articleType = 'Pull';
      else if (profileName === 'jacket_carhart') articleType = 'Veste';
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
    }
    // Horodatage precis de la generation (colonne Timestamp)
    var now = new Date();
    var timestamp = formatTimestamp_(now);
    // Calculer la duree en minutes depuis la derniere generation
    var newRow = sheet.getLastRow() + 1;
    var dureeMins = '';
    if (newRow > 2) {
      var prevTimestamp = sheet.getRange(newRow - 1, 18).getValue(); // colonne R = Timestamp
      if (prevTimestamp) {
        var prevDate = new Date(prevTimestamp);
        if (!isNaN(prevDate.getTime())) {
          dureeMins = Math.round((now.getTime() - prevDate.getTime()) / 60000);
        }
      }
    }
    var hasDefectFlag = hasDefectsForLog_(features, result);
    var generationCost = (result.generation_cost != null) ? result.generation_cost : '';
    var row = [
      now,
      agentEmail,
      profileName,
      articleType,
      features.brand || result.brand || '',
      features.model || features._raw_model || '',
      features.is_premium ? true : false,
      tailleFr,
      tailleUs,
      riseLabel,
      couleur,
      matiere,
      features.fit || '',
      features.gender || '',
      price,
      features.condition || '',
      skuForLog,
      timestamp,
      dureeMins,
      generationCost,
      hasDefectFlag
    ];
    sheet.getRange(newRow, 1, 1, row.length).setValues([row]);
    // Force la cellule "Défauts" en checkbox même si la colonne a été ajoutée
    // manuellement à un autre index dans une feuille existante.
    try {
      if (defectsColIndex && defectsColIndex !== row.length) {
        sheet.getRange(newRow, defectsColIndex).insertCheckboxes().setValue(hasDefectFlag);
      } else {
        sheet.getRange(newRow, row.length).insertCheckboxes().setValue(hasDefectFlag);
      }
    } catch (eCkRow) {
      Logger.log('logGenerationToSheet checkbox warning: ' + eCkRow.message);
    }
    return { success: true, row: newRow };
  } catch (err) {
    Logger.log('logGenerationToSheet error: ' + err.message);
    return { error: 'Erreur ecriture log : ' + err.message };
  }
}
