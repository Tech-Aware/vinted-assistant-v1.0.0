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
    var apiKey = Config.getGeminiApiKey();
    if (!apiKey) {
      return { error: 'Cle API Gemini non configuree. Ouvrez la configuration (icone engrenage).' };
    }
    var modelName = Config.getGeminiModel() || 'gemini-2.5-flash';
    var profile = Templates.getProfile(profileName);
    if (!profile) {
      return { error: 'Profil d\'analyse inconnu : ' + profileName };
    }
    // Appel Gemini
    var geminiResult = GeminiClient.generateContent(
      apiKey,
      modelName,
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
 * Bareme "rotation rapide" femme.
 * Zone standard : 20-26 €. Zone haute exceptionnelle : 27-30 €. Jamais > 30 €.
 * Les defauts retirent ~4 €. Skinny en bas de grille, evase legerement valorise.
 */
function priceFemme_(premium, budget, fit, sizeNum, hasDefects) {
  var bigSize = !!(sizeNum && sizeNum >= 42);
  if (premium) {
    var retailPremium = '110–140 €';
    if (fit === 'évasé') {
      return { price: bigSize ? (hasDefects ? 24 : 28) : (hasDefects ? 22 : 26), retail: retailPremium };
    }
    if (fit === 'skinny') {
      return { price: hasDefects ? 20 : 24, retail: retailPremium };
    }
    // droit (defaut)
    return { price: hasDefects ? 22 : 26, retail: retailPremium };
  }
  if (budget) {
    var retailBudget = '24–50 €';
    return { price: bigSize ? (hasDefects ? 18 : 22) : (hasDefects ? 16 : 20), retail: retailBudget };
  }
  // standard
  var retailStandard = '90–120 €';
  if (fit === 'évasé') {
    return { price: bigSize ? (hasDefects ? 22 : 26) : (hasDefects ? 20 : 24), retail: retailStandard };
  }
  if (fit === 'skinny') {
    return { price: hasDefects ? 18 : 22, retail: retailStandard };
  }
  // droit (defaut)
  return { price: hasDefects ? 20 : 24, retail: retailStandard };
}
/**
 * Bareme "rotation rapide" homme.
 * Zone standard : 20-26 €. Zone haute exceptionnelle : 27-30 €. Jamais > 30 €.
 */
function priceHomme_(premium, budget, fit, sizeNum, hasDefects) {
  var bigSize = !!(sizeNum && sizeNum >= 38);
  if (premium) {
    var retailPremium = '110–140 €';
    if (fit === 'évasé') {
      return { price: bigSize ? (hasDefects ? 26 : 30) : (hasDefects ? 24 : 28), retail: retailPremium };
    }
    if (fit === 'skinny') {
      return { price: hasDefects ? 21 : 25, retail: retailPremium };
    }
    // droit (defaut)
    return { price: hasDefects ? 24 : 28, retail: retailPremium };
  }
  if (budget) {
    var retailBudget = '24–50 €';
    return { price: bigSize ? (hasDefects ? 18 : 22) : (hasDefects ? 16 : 20), retail: retailBudget };
  }
  // standard
  var retailStandard = '90–120 €';
  if (fit === 'évasé') {
    return { price: bigSize ? (hasDefects ? 22 : 26) : (hasDefects ? 20 : 24), retail: retailStandard };
  }
  if (fit === 'skinny') {
    return { price: hasDefects ? 18 : 22, retail: retailStandard };
  }
  // droit (defaut)
  return { price: hasDefects ? 20 : 24, retail: retailStandard };
}
/**
 * Plafond commercial "rotation rapide".
 * - plafond par defaut : 26 €
 * - plafond exceptionnel : 28 € (premium, ou taille forte, ou coupe evasee, sans defaut)
 * - plafond ultra exceptionnel : 30 € (premium ET sans defaut ET (grande taille OU evase))
 * - jamais plus de 30 € en automatique
 */
function applyRotationCap_(price, premium, fit, sizeNum, hasDefects, gender) {
  if (typeof price !== 'number' || isNaN(price)) return price;
  var bigSize = !!(sizeNum && sizeNum >= ((gender === 'homme') ? 38 : 42));
  var attractiveFit = (fit === 'évasé');
  var cap = 26;
  if (!hasDefects && (premium || bigSize || attractiveFit)) {
    cap = 28;
  }
  if (premium && !hasDefects && (bigSize || attractiveFit)) {
    cap = 30;
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
  'Genre', 'Prix', 'Etat', 'SKU', 'Timestamp', 'Duree (min)'
];
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
    // SKU avec prefixe Order ID (ex: 01JLF0091)
    var rawSku = features.sku || result.sku || '';
    var orderId = features.order_id || '';
    var skuForLog = rawSku;
    if (rawSku && orderId) {
      var pad = ('00' + String(orderId).replace(/\D/g, '')).slice(-2);
      if (pad !== '00') skuForLog = pad + rawSku;
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
      dureeMins
    ];
    sheet.getRange(newRow, 1, 1, row.length).setValues([row]);
    return { success: true, row: newRow };
  } catch (err) {
    Logger.log('logGenerationToSheet error: ' + err.message);
    return { error: 'Erreur ecriture log : ' + err.message };
  }
}
