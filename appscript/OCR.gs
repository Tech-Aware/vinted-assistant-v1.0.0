/**
 * OCR.gs - Google Cloud Vision OCR via REST API
 *
 * Port de infrastructure/google_vision_ocr.py
 * Utilise UrlFetchApp pour appeler l'API Cloud Vision REST.
 */

var OCR = (function() {

  /**
   * Extrait le texte OCR de plusieurs images Google Drive.
   *
   * @param {string[]} fileIds - IDs des fichiers images dans Drive
   * @param {string} apiKey - Cle API Google Cloud Vision
   * @returns {string} Texte OCR concatene
   */
  function extractTextFromDriveFiles(fileIds, apiKey) {
    if (!fileIds || fileIds.length === 0) return '';
    if (!apiKey) {
      Logger.log('OCR: pas de cle API Vision, OCR ignore.');
      return '';
    }

    var allTexts = [];

    for (var i = 0; i < fileIds.length; i++) {
      try {
        var text = extractTextFromDriveFile_(fileIds[i], apiKey);
        if (text) {
          allTexts.push(text);
          Logger.log('OCR: fichier ' + fileIds[i] + ' -> ' + text.length + ' chars');
        }
      } catch (err) {
        Logger.log('OCR: erreur fichier ' + fileIds[i] + ': ' + err.message);
      }
    }

    return allTexts.join('\n---\n');
  }

  /**
   * Extrait le texte d'une seule image via Cloud Vision.
   */
  function extractTextFromDriveFile_(fileId, apiKey) {
    var file = DriveApp.getFileById(fileId);
    var blob = file.getBlob();
    var base64 = Utilities.base64Encode(blob.getBytes());

    var url = 'https://vision.googleapis.com/v1/images:annotate?key=' + apiKey;

    var payload = {
      requests: [
        {
          image: { content: base64 },
          features: [
            { type: 'DOCUMENT_TEXT_DETECTION' }
          ]
        }
      ]
    };

    var options = {
      method: 'post',
      contentType: 'application/json',
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    };

    var response = UrlFetchApp.fetch(url, options);
    var responseCode = response.getResponseCode();

    if (responseCode !== 200) {
      throw new Error('Vision API HTTP ' + responseCode + ': ' + response.getContentText().substring(0, 200));
    }

    var data = JSON.parse(response.getContentText());

    if (data.responses && data.responses.length > 0) {
      var annotation = data.responses[0].fullTextAnnotation;
      if (annotation && annotation.text) {
        return annotation.text.trim();
      }

      // Fallback: textAnnotations
      var textAnnotations = data.responses[0].textAnnotations;
      if (textAnnotations && textAnnotations.length > 0) {
        return textAnnotations[0].description.trim();
      }
    }

    return '';
  }

  return {
    extractTextFromDriveFiles: extractTextFromDriveFiles
  };

})();
