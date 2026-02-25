/**
 * Vinted Assistant Online - Google Apps Script
 *
 * Point d'entree principal.
 * Ajoute un menu personnalise a Google Sheets et gere les interactions UI.
 */

// ============================================================
// Menu & UI
// ============================================================

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Vinted Assistant')
    .addItem('Ouvrir le panneau', 'showSidebar')
    .addItem('Configuration', 'showConfigDialog')
    .addSeparator()
    .addItem('Aide', 'showHelp')
    .addToUi();
}

function showSidebar() {
  var html = HtmlService.createHtmlOutputFromFile('Sidebar')
    .setTitle('Vinted Assistant')
    .setWidth(420);
  SpreadsheetApp.getUi().showSidebar(html);
}

function showConfigDialog() {
  var html = HtmlService.createHtmlOutputFromFile('ConfigDialog')
    .setTitle('Configuration')
    .setWidth(400)
    .setHeight(300);
  SpreadsheetApp.getUi().showModalDialog(html, 'Configuration Vinted Assistant');
}

function showHelp() {
  var ui = SpreadsheetApp.getUi();
  ui.alert(
    'Vinted Assistant - Aide',
    '1. Configurez votre cle API Gemini via le menu Configuration.\n' +
    '2. Placez vos images dans un dossier Google Drive.\n' +
    '3. Ouvrez le panneau lateral et selectionnez vos images.\n' +
    '4. Choisissez un profil d\'analyse et lancez la generation.\n' +
    '5. Le titre et la description seront generes automatiquement.\n\n' +
    'Profils disponibles : Jean Levi\'s, Pull Tommy, Veste Carhartt',
    ui.ButtonSet.OK
  );
}

// ============================================================
// Configuration (appelees depuis les dialogs HTML)
// ============================================================

function getConfig() {
  return Config.getAll();
}

function saveConfig(config) {
  Config.setGeminiApiKey(config.geminiApiKey || '');
  Config.setGeminiModel(config.geminiModel || '');
  if (config.visionApiKey) {
    Config.setVisionApiKey(config.visionApiKey);
  }
  return { success: true };
}

// ============================================================
// Generation d'annonce (appelee depuis la sidebar)
// ============================================================

/**
 * Genere une annonce Vinted a partir d'images Google Drive.
 *
 * @param {Object} params
 * @param {string[]} params.imageFileIds - IDs des fichiers images dans Drive
 * @param {string[]} params.ocrImageFileIds - IDs des images pour OCR
 * @param {string} params.profileName - Nom du profil (jean_levis, pull, jacket_carhart)
 * @param {Object} params.uiData - Donnees saisies manuellement (tailles, SKU, etc.)
 * @returns {Object} Resultat avec title, description, features, etc.
 */
function generateListing(params) {
  try {
    var imageFileIds = params.imageFileIds || [];
    var ocrImageFileIds = params.ocrImageFileIds || [];
    var profileName = params.profileName || 'jean_levis';
    var uiData = params.uiData || {};

    if (imageFileIds.length === 0) {
      return { error: 'Aucune image selectionnee.' };
    }

    var apiKey = Config.getGeminiApiKey();
    if (!apiKey) {
      return { error: 'Cle API Gemini non configuree. Allez dans Vinted Assistant > Configuration.' };
    }

    var modelName = Config.getGeminiModel() || 'gemini-2.5-flash';
    var profile = Templates.getProfile(profileName);
    if (!profile) {
      return { error: 'Profil d\'analyse inconnu : ' + profileName };
    }

    // OCR (optionnel)
    var ocrText = '';
    if (ocrImageFileIds.length > 0) {
      try {
        var visionApiKey = Config.getVisionApiKey();
        if (visionApiKey) {
          ocrText = OCR.extractTextFromDriveFiles(ocrImageFileIds, visionApiKey);
          Logger.log('OCR: ' + ocrText.length + ' caracteres extraits');
        } else {
          Logger.log('OCR ignore : cle API Vision non configuree');
        }
      } catch (ocrErr) {
        Logger.log('OCR erreur (non bloquante) : ' + ocrErr.message);
      }
    }

    // Appel Gemini
    var geminiResult = GeminiClient.generateContent(
      apiKey,
      modelName,
      imageFileIds,
      profile,
      uiData,
      ocrText
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
    var profileEnum = profileName;
    var normalized = Normalizer.normalizeAndPostprocess(parsed, profileEnum, uiData);

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
// Utilitaires Drive (appelees depuis la sidebar)
// ============================================================

/**
 * Liste les images d'un dossier Google Drive.
 */
function listImagesInFolder(folderId) {
  try {
    var folder = DriveApp.getFolderById(folderId);
    var files = folder.getFiles();
    var images = [];
    var imageTypes = [
      MimeType.JPEG, MimeType.PNG, MimeType.GIF, MimeType.BMP,
      'image/webp'
    ];

    while (files.hasNext()) {
      var file = files.next();
      var mimeType = file.getMimeType();
      if (imageTypes.indexOf(mimeType) !== -1 || mimeType.indexOf('image/') === 0) {
        images.push({
          id: file.getId(),
          name: file.getName(),
          mimeType: mimeType,
          url: file.getUrl(),
          thumbnailUrl: 'https://drive.google.com/thumbnail?id=' + file.getId() + '&sz=w200'
        });
      }
    }

    images.sort(function(a, b) { return a.name.localeCompare(b.name); });
    return { success: true, images: images };
  } catch (err) {
    return { error: 'Erreur acces dossier : ' + err.message };
  }
}

/**
 * Ecrit le resultat dans la feuille active.
 */
function writeResultToSheet(result) {
  try {
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    var lastRow = sheet.getLastRow();
    var newRow = lastRow + 1;

    sheet.getRange(newRow, 1).setValue(result.title || '');
    sheet.getRange(newRow, 2).setValue(result.description || '');
    sheet.getRange(newRow, 3).setValue(result.brand || '');
    sheet.getRange(newRow, 4).setValue(result.sku || '');
    sheet.getRange(newRow, 5).setValue(new Date());

    return { success: true, row: newRow };
  } catch (err) {
    return { error: 'Erreur ecriture : ' + err.message };
  }
}
