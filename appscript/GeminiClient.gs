/**
 * GeminiClient.gs - Client API Gemini via UrlFetchApp
 *
 * Port de infrastructure/gemini_client.py
 * Utilise l'API REST Gemini directement avec UrlFetchApp.
 */

var GeminiClient = (function() {

  var MAX_RETRIES = 3;
  var BASE_DELAY_MS = 2000;

  /**
   * Genere le contenu via l'API Gemini.
   *
   * @param {string} apiKey - Cle API Gemini
   * @param {string} modelName - Nom du modele (ex: gemini-2.5-flash)
   * @param {Object[]} imageDataArray - Images en base64 [{base64, mimeType, name}]
   * @param {Object} profile - Profil d'analyse (de Templates)
   * @param {Object} uiData - Donnees UI
   * @returns {Object} { text: string } ou { error: string }
   */
  function generateContent(apiKey, modelName, imageDataArray, profile, uiData) {
    // Construire le prompt
    var fullPrompt = Prompt.getPromptContract() + '\n\n' + profile.promptSuffix;

    // Ajouter le mode de mesure si fourni
    var measurementMode = (uiData || {}).measurement_mode || (uiData || {}).measurementMode;
    if (measurementMode) {
      fullPrompt += '\n\nMODE_RELEVE: ' + measurementMode;
    }

    // Construire les parts (texte + images)
    var parts = [];
    parts.push({ text: fullPrompt });

    // Ajouter les images recues du navigateur (deja en base64)
    for (var i = 0; i < imageDataArray.length; i++) {
      var img = imageDataArray[i];
      if (img && img.base64 && img.mimeType) {
        parts.push({
          inline_data: {
            mime_type: img.mimeType,
            data: img.base64
          }
        });
      }
    }

    // Appel API avec retry
    var normalizedModel = normalizeModelName_(modelName);
    return callApiWithRetry_(apiKey, normalizedModel, parts);
  }

  /**
   * Normalise le nom du modele.
   */
  function normalizeModelName_(modelName) {
    var cleaned = (modelName || '').trim();
    if (!cleaned) {
      throw new Error('Nom de modele Gemini manquant ou vide.');
    }
    // L'API REST utilise le nom court (sans prefixe models/)
    if (cleaned.indexOf('models/') === 0) {
      cleaned = cleaned.substring(7);
    }
    return cleaned;
  }

  /**
   * Appel API Gemini avec retry exponentiel.
   */
  function callApiWithRetry_(apiKey, modelName, parts) {
    var lastError = null;

    for (var attempt = 0; attempt < MAX_RETRIES; attempt++) {
      try {
        var result = callApi_(apiKey, modelName, parts);
        return result;
      } catch (err) {
        lastError = err;
        var errMsg = err.message.toLowerCase();

        // Verifier si l'erreur est recuperable
        var retryable = ['timeout', 'rate limit', 'quota', '503', '502', '504',
                         'connection', 'network', 'temporarily unavailable',
                         'resource exhausted', 'deadline exceeded', '429'];
        var isRetryable = retryable.some(function(pattern) {
          return errMsg.indexOf(pattern) !== -1;
        });

        if (isRetryable && attempt < MAX_RETRIES - 1) {
          var delay = BASE_DELAY_MS * Math.pow(2, attempt);
          Logger.log('GeminiClient: erreur recuperable (tentative ' + (attempt + 1) + '/' + MAX_RETRIES + '). Retry dans ' + delay + 'ms. Erreur: ' + err.message);
          Utilities.sleep(delay);
        } else {
          break;
        }
      }
    }

    return { error: 'Erreur API Gemini apres ' + MAX_RETRIES + ' tentatives: ' + (lastError ? lastError.message : 'inconnue') };
  }

  /**
   * Appel direct a l'API Gemini REST.
   */
  function callApi_(apiKey, modelName, parts) {
    var url = 'https://generativelanguage.googleapis.com/v1beta/models/' + modelName + ':generateContent?key=' + apiKey;

    var payload = {
      contents: [
        {
          parts: parts
        }
      ],
      generationConfig: {
        temperature: 0.2,
        topP: 0.9,
        responseMimeType: 'application/json'
      }
    };

    var options = {
      method: 'post',
      contentType: 'application/json',
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    };

    var response = UrlFetchApp.fetch(url, options);
    var responseCode = response.getResponseCode();
    var responseText = response.getContentText();

    if (responseCode !== 200) {
      // Extraire le message d'erreur
      var errorMsg = 'HTTP ' + responseCode;
      try {
        var errorBody = JSON.parse(responseText);
        if (errorBody.error && errorBody.error.message) {
          errorMsg += ': ' + errorBody.error.message;
        }
      } catch (e) {
        errorMsg += ': ' + responseText.substring(0, 200);
      }
      throw new Error(errorMsg);
    }

    // Parser la reponse
    var responseData = JSON.parse(responseText);

    // Extraire le texte genere
    if (responseData.candidates && responseData.candidates.length > 0) {
      var candidate = responseData.candidates[0];
      if (candidate.content && candidate.content.parts && candidate.content.parts.length > 0) {
        var text = candidate.content.parts[0].text;
        if (text) {
          return { text: text };
        }
      }

      // Verifier les raisons de blocage
      if (candidate.finishReason && candidate.finishReason !== 'STOP') {
        return { error: 'Gemini a bloque la generation: ' + candidate.finishReason };
      }
    }

    return { error: 'Reponse Gemini vide ou invalide.' };
  }

  return {
    generateContent: generateContent
  };

})();
