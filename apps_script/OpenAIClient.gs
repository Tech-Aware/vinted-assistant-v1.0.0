/**
 * OpenAIClient.gs - Client API OpenAI (Chat Completions, vision) via UrlFetchApp
 *
 * Symetrique a GeminiClient.gs : meme API publique
 *   OpenAIClient.generateContent(apiKey, modelName, imageDataArray, profile, uiData)
 * et meme contrat de retour { text } / { error, ... }.
 *
 * Particularites OpenAI :
 *  - Endpoint : POST https://api.openai.com/v1/chat/completions
 *  - Auth : header "Authorization: Bearer <apiKey>"
 *  - Vision : message user avec content = [ {type:"text",...}, {type:"image_url", image_url:{url:"data:<mime>;base64,<b64>"}} ]
 *  - JSON force via response_format = { type: "json_object" }
 *  - Quota : pas de distinction explicite per-day / per-minute dans le payload,
 *    on s'appuie sur le code 429 + en-tete Retry-After + texte du message.
 *  - Fallback de modele : chaine MODEL_FALLBACK_CHAIN ; chaque modele a son propre quota.
 *  - Cache de resultat et verrou utilisateur identiques a GeminiClient (namespace cache distinct).
 */
var OpenAIClient = (function() {
  var CLIENT_VERSION = '2026-04-22-r1';
  var MAX_RETRIES = 2;
  var BASE_DELAY_MS = 2000;
  var MAX_DELAY_MS = 60000;
  var ENDPOINT = 'https://api.openai.com/v1/chat/completions';
  // Chaine de fallback : du plus capable au plus economique.
  var MODEL_FALLBACK_CHAIN = [
    'gpt-4o',
    'gpt-4o-mini'
  ];
  var CACHE_TTL_SECONDS = 3600;
  var CACHE_MAX_VALUE_BYTES = 95 * 1024;
  var USER_LOCK_TIMEOUT_MS = 500;
  // Page de gestion / facturation OpenAI.
  var BILLING_URL = 'https://platform.openai.com/account/billing';

  /**
   * Genere le contenu via l'API OpenAI Chat Completions (vision).
   *
   * @param {string} apiKey - Cle API OpenAI (sk-...)
   * @param {string} modelName - Nom du modele (ex: gpt-4o-mini)
   * @param {Object[]} imageDataArray - Images en base64 [{base64, mimeType, name}]
   * @param {Object} profile - Profil d'analyse (de Templates)
   * @param {Object} uiData - Donnees UI
   * @returns {Object} { text: string } ou { error: string, ... }
   */
  function generateContent(apiKey, modelName, imageDataArray, profile, uiData) {
    var fullPrompt = Prompt.getPromptContract() + '\n\n' + profile.promptSuffix;
    var measurementMode = (uiData || {}).measurement_mode || (uiData || {}).measurementMode;
    if (measurementMode) {
      fullPrompt += '\n\nMODE_RELEVE: ' + measurementMode;
    }

    // Construction du content multimodal au format OpenAI.
    var content = [{ type: 'text', text: fullPrompt }];
    var imageCount = 0;
    for (var i = 0; i < imageDataArray.length; i++) {
      var img = imageDataArray[i];
      if (img && img.base64 && img.mimeType) {
        content.push({
          type: 'image_url',
          image_url: {
            url: 'data:' + img.mimeType + ';base64,' + img.base64
          }
        });
        imageCount++;
      }
    }

    Logger.log('OpenAIClient: ' + imageCount + ' image(s) ajoutee(s) sur ' + imageDataArray.length + ' recue(s)');
    Logger.log(
      'OpenAIClient version=%s model=%s retries=%s baseDelayMs=%s maxDelayMs=%s',
      CLIENT_VERSION,
      normalizeModelName_(modelName),
      MAX_RETRIES,
      BASE_DELAY_MS,
      MAX_DELAY_MS
    );

    if (imageCount === 0) {
      return { error: 'Aucune image valide a envoyer a OpenAI. Les donnees base64 sont absentes.' };
    }

    var requestedModel = normalizeModelName_(modelName);

    // 1) Cache.
    var cacheKey = buildCacheKey_(requestedModel, content);
    var cached = readCache_(cacheKey);
    if (cached) {
      Logger.log('OpenAIClient: cache hit (key=' + cacheKey + '). Pas d\'appel API.');
      if (!cached._usedModel) cached._usedModel = requestedModel;
      return cached;
    }

    // 2) Verrou utilisateur.
    var lock = null;
    try {
      lock = LockService.getUserLock();
    } catch (lockInitErr) {
      lock = null;
    }
    if (lock) {
      try {
        if (!lock.tryLock(USER_LOCK_TIMEOUT_MS)) {
          return { error: 'Une analyse est deja en cours pour votre session. Patientez quelques secondes avant de relancer.' };
        }
      } catch (lockErr) {
        lock = null;
      }
    }

    try {
      var result = callWithModelFallback_(apiKey, requestedModel, content);
      if (result && result.text && !result.error) {
        writeCache_(cacheKey, result);
      }
      return result;
    } finally {
      if (lock) {
        try { lock.releaseLock(); } catch (e) { /* ignore */ }
      }
    }
  }

  function normalizeModelName_(modelName) {
    var cleaned = (modelName || '').trim();
    if (!cleaned) {
      throw new Error('Nom de modele OpenAI manquant ou vide.');
    }
    return cleaned;
  }

  function callWithModelFallback_(apiKey, requestedModel, content) {
    var chain = buildFallbackChain_(requestedModel);
    var lastResult = null;
    for (var i = 0; i < chain.length; i++) {
      var model = chain[i];
      if (i > 0) {
        Logger.log('OpenAIClient: fallback de modele -> ' + model);
      }
      var result = callApiWithRetry_(apiKey, model, content);
      if (result && result.text) {
        result._usedModel = model;
        return result;
      }
      lastResult = result;
      if (!result || !result._retryWithOtherModel) {
        return result;
      }
    }
    return lastResult;
  }

  function buildFallbackChain_(requestedModel) {
    var chain = [requestedModel];
    for (var i = 0; i < MODEL_FALLBACK_CHAIN.length; i++) {
      var m = MODEL_FALLBACK_CHAIN[i];
      if (m && chain.indexOf(m) === -1) {
        chain.push(m);
      }
    }
    return chain;
  }

  function callApiWithRetry_(apiKey, modelName, content) {
    var lastError = null;
    for (var attempt = 0; attempt < MAX_RETRIES; attempt++) {
      try {
        return callApi_(apiKey, modelName, content);
      } catch (err) {
        lastError = err;
        var errMsg = String(err && err.message ? err.message : '').toLowerCase();
        var status = err && err.statusCode ? err.statusCode : 0;

        // Auth : non recuperable.
        var authPatterns = ['invalid_api_key', 'incorrect api key', 'invalid api key', 'authentication', 'permission', 'unauthenticated'];
        var isAuthError = status === 401 || status === 403 || authPatterns.some(function(p) { return errMsg.indexOf(p) !== -1; });
        if (isAuthError) {
          break;
        }

        // OpenAI a un code dedie "insufficient_quota" qui n'est pas resolu par retry.
        if (errMsg.indexOf('insufficient_quota') !== -1) {
          err.isHardQuota = true;
          break;
        }

        var retryablePatterns = ['timeout', 'rate limit', 'rate_limit', 'quota', '503', '502', '504',
                                 'connection', 'network', 'temporarily unavailable',
                                 'overloaded', 'try again'];
        var isRetryable = status === 429 || status === 502 || status === 503 || status === 504 ||
                          retryablePatterns.some(function(p) { return errMsg.indexOf(p) !== -1; });

        if (isRetryable && attempt < MAX_RETRIES - 1) {
          var delay = computeRetryDelayMs_(err, attempt);
          Logger.log('OpenAIClient: erreur recuperable (tentative ' + (attempt + 1) + '/' + MAX_RETRIES + ', model=' + modelName + '). Retry dans ' + delay + 'ms. Erreur: ' + err.message);
          Utilities.sleep(delay);
        } else {
          break;
        }
      }
    }
    return buildErrorResult_(lastError, modelName);
  }

  /**
   * Priorite : header Retry-After > motifs textuels OpenAI > exponentiel.
   */
  function computeRetryDelayMs_(err, attempt) {
    if (err && typeof err.retryAfterMs === 'number' && err.retryAfterMs > 0) {
      return Math.min(err.retryAfterMs + 500, MAX_DELAY_MS);
    }
    var msg = String(err && err.message ? err.message : '');
    // Couvre : "try again in Xs", "retry after Xs", "please retry in Xs",
    //          "Rate limit ... in Xs", "Please try again in Xs".
    var match = msg.match(/(?:try again in|retry after|please retry in|rate limit[^.]*?in)\s+([0-9]+(?:\.[0-9]+)?)\s*s/i);
    if (match && match[1]) {
      var ms = Math.ceil(parseFloat(match[1]) * 1000);
      if (!isNaN(ms) && ms > 0) {
        return Math.min(ms + 500, MAX_DELAY_MS);
      }
    }
    var exponential = BASE_DELAY_MS * Math.pow(2, attempt);
    return Math.min(exponential, MAX_DELAY_MS);
  }

  function callApi_(apiKey, modelName, content) {
    var payload = {
      model: modelName,
      messages: [
        {
          role: 'system',
          content: 'You are a structured data extraction agent. Always respond with valid JSON only, no markdown, no extra text.'
        },
        { role: 'user', content: content }
      ],
      temperature: 0.2,
      top_p: 0.9,
      response_format: { type: 'json_object' }
    };
    var options = {
      method: 'post',
      contentType: 'application/json',
      headers: {
        'Authorization': 'Bearer ' + apiKey
      },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    };
    var response = UrlFetchApp.fetch(ENDPOINT, options);
    var responseCode = response.getResponseCode();
    var responseText = response.getContentText();

    if (responseCode !== 200) {
      var errorMsg = 'HTTP ' + responseCode;
      var errorBody = null;
      try {
        errorBody = JSON.parse(responseText);
        if (errorBody && errorBody.error && errorBody.error.message) {
          errorMsg += ': ' + errorBody.error.message;
        }
      } catch (e) {
        errorMsg += ': ' + responseText.substring(0, 200);
      }
      var err = new Error(errorMsg);
      err.statusCode = responseCode;
      err.errorBody = errorBody;
      try {
        var headers = response.getHeaders() || {};
        var retryAfter = headers['Retry-After'] || headers['retry-after'];
        if (retryAfter) {
          var asInt = parseInt(retryAfter, 10);
          if (!isNaN(asInt) && asInt > 0) {
            err.retryAfterMs = asInt * 1000;
          }
        }
      } catch (e) { /* ignore */ }
      throw err;
    }

    var responseData;
    try {
      responseData = JSON.parse(responseText);
    } catch (e) {
      return { error: 'Reponse OpenAI illisible (parsing JSON impossible).' };
    }

    if (responseData.choices && responseData.choices.length > 0) {
      var choice = responseData.choices[0];
      var msg = choice.message || {};
      var text = typeof msg.content === 'string' ? msg.content : null;
      // OpenAI peut renvoyer content sous forme de tableau de parts ; on concatene les parts texte.
      if (!text && Array.isArray(msg.content)) {
        var buf = [];
        for (var i = 0; i < msg.content.length; i++) {
          var part = msg.content[i] || {};
          if (part.type === 'text' && typeof part.text === 'string') {
            buf.push(part.text);
          }
        }
        text = buf.join('');
      }
      if (text) {
        return { text: text, usage: responseData.usage || null };
      }
      if (choice.finish_reason && choice.finish_reason !== 'stop') {
        return { error: 'OpenAI a bloque la generation: ' + choice.finish_reason };
      }
    }
    return { error: 'Reponse OpenAI vide ou invalide.' };
  }

  function buildErrorResult_(err, modelName) {
    if (!err) {
      return { error: 'Erreur API OpenAI inconnue.' };
    }
    var status = err.statusCode || 0;
    var raw = err.message || 'erreur inconnue';

    if (err.isHardQuota || (raw && raw.toLowerCase().indexOf('insufficient_quota') !== -1)) {
      return {
        error: 'Quota OpenAI epuise pour le modele ' + modelName + '. Verifiez votre solde / facturation : ' + BILLING_URL,
        quotaExceeded: true,
        quotaPeriod: 'account',
        model: modelName
      };
    }
    if (status === 429) {
      var waitMs = err.retryAfterMs || 0;
      var waitSec = waitMs > 0 ? Math.ceil(waitMs / 1000) : 0;
      var msg = 'Quota / limite de debit OpenAI atteinte (' + MAX_RETRIES + ' tentatives, modele ' + modelName + ').';
      if (waitSec > 0) {
        msg += ' Reessayez dans ' + waitSec + ' s.';
      }
      msg += ' Plus d\'infos : ' + BILLING_URL;
      return {
        error: msg,
        quotaExceeded: true,
        quotaPeriod: 'minute',
        retryAfterSec: waitSec || null,
        model: modelName,
        _retryWithOtherModel: true
      };
    }
    if (status === 401 || status === 403) {
      return {
        error: 'Cle API OpenAI invalide ou non autorisee. Verifiez la configuration.',
        authError: true
      };
    }
    return { error: 'Erreur API OpenAI apres ' + MAX_RETRIES + ' tentatives: ' + raw };
  }

  // ============================================================
  // Cache de resultat
  // ============================================================
  function buildCacheKey_(modelName, content) {
    var raw = modelName + '|' + JSON.stringify(content);
    var bytes = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, raw, Utilities.Charset.UTF_8);
    var hex = '';
    for (var i = 0; i < bytes.length; i++) {
      var b = bytes[i] & 0xff;
      hex += (b < 16 ? '0' : '') + b.toString(16);
    }
    return 'openai:v1:' + hex;
  }

  function getCache_() {
    try { return CacheService.getScriptCache(); } catch (e) { return null; }
  }

  function readCache_(key) {
    var cache = getCache_();
    if (!cache) return null;
    try {
      var raw = cache.get(key);
      if (!raw) return null;
      return JSON.parse(raw);
    } catch (e) {
      return null;
    }
  }

  function writeCache_(key, value) {
    var cache = getCache_();
    if (!cache) return;
    try {
      var serialized = JSON.stringify(value);
      var byteLength;
      try {
        byteLength = Utilities.newBlob(serialized).getBytes().length;
      } catch (e) {
        byteLength = serialized.length;
      }
      if (byteLength > CACHE_MAX_VALUE_BYTES) {
        Logger.log('OpenAIClient: resultat trop gros pour cache (' + byteLength + ' bytes), skip.');
        return;
      }
      cache.put(key, serialized, CACHE_TTL_SECONDS);
    } catch (e) {
      Logger.log('OpenAIClient: ecriture cache impossible: ' + e.message);
    }
  }

  return {
    generateContent: generateContent
  };
})();
