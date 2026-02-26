/**
 * Vinted Assistant Online - Google Apps Script
 *
 * Point d'entree principal.
 * Deploye en tant que Web App autonome via doGet().
 */

// ============================================================
// Web App Entry Point
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
      rawText: geminiResult.text
    };

  } catch (err) {
    Logger.log('generateListing error: ' + err.message + '\n' + err.stack);
    return { error: 'Erreur inattendue : ' + err.message };
  }
}

// ============================================================
// Logging dans Google Sheets
// ============================================================

var LOG_HEADERS = [
  'Date', 'Profil', 'Type article', 'Marque', 'Modele',
  'Taille FR', 'Taille US', 'Couleur', 'Matiere', 'Coupe',
  'Genre', 'Prix', 'Premium', 'SKU', 'Order ID',
  'Etat', 'Titre', 'Description'
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
    var sheet = spreadsheet.getSheetByName('Logs') || spreadsheet.insertSheet('Logs');

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

    var row = [
      new Date(),
      profileName,
      articleType,
      features.brand || result.brand || '',
      features.model || '',
      tailleFr,
      tailleUs,
      couleur,
      features.material || '',
      features.fit || '',
      features.gender || '',
      uiData.price || '',
      uiData.premium ? 'Oui' : 'Non',
      features.sku || result.sku || '',
      features.order_id || uiData.order_id || '',
      features.condition || '',
      result.title || '',
      result.description || ''
    ];

    var newRow = sheet.getLastRow() + 1;
    sheet.getRange(newRow, 1, 1, row.length).setValues([row]);

    return { success: true, row: newRow };
  } catch (err) {
    Logger.log('logGenerationToSheet error: ' + err.message);
    return { error: 'Erreur ecriture log : ' + err.message };
  }
}
