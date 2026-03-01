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

    var title = TitleEngine.buildTitle(profileName, features);
    var description = DescriptionEngine.buildDescription(profileName, features, aiDescription, aiDefects);

    return {
      success: true,
      title: title,
      description: description,
      features: features
    };
  } catch (err) {
    Logger.log('rebuildListing error: ' + err.message);
    return { error: 'Erreur reconstruction : ' + err.message };
  }
}

// ============================================================
// Logging dans Google Sheets
// ============================================================

var LOG_HEADERS = [
  'Date', 'Agent', 'Profil', 'Type article', 'Marque', 'Modele', 'Premium',
  'Taille FR', 'Taille US', 'Rise', 'Couleur', 'Matiere', 'Coupe',
  'Genre', 'Prix', 'Etat', 'SKU'
];

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

    // Taille FR : selon le profil
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

    // Rise : matching souple + fallback uiData + rise_cm
    var riseLabel = '';
    var riseRaw = features.rise_type || uiData.rise_type || '';
    if (!riseRaw && features.rise_cm != null) {
      riseRaw = TitleBuilder.classifyRiseFromCm(features.rise_cm) || '';
    }
    if (riseRaw) {
      var rl = riseRaw.toLowerCase();
      if (rl.indexOf('high') !== -1 || rl.indexOf('haute') !== -1) riseLabel = 'Haute';
      else if (rl.indexOf('low') !== -1 || rl.indexOf('basse') !== -1) riseLabel = 'Basse';
      else if (rl.indexOf('mid') !== -1 || rl.indexOf('moy') !== -1) riseLabel = 'Moyenne';
    }

    var row = [
      new Date(),
      agentEmail,
      profileName,
      articleType,
      features.brand || result.brand || '',
      features._raw_model || features.model || '',
      features.is_premium ? true : false,
      tailleFr,
      tailleUs,
      riseLabel,
      couleur,
      matiere,
      features.fit || '',
      features.gender || '',
      uiData.price || '',
      features.condition || '',
      skuForLog
    ];

    var newRow = sheet.getLastRow() + 1;
    sheet.getRange(newRow, 1, 1, row.length).setValues([row]);

    return { success: true, row: newRow };
  } catch (err) {
    Logger.log('logGenerationToSheet error: ' + err.message);
    return { error: 'Erreur ecriture log : ' + err.message };
  }
}
