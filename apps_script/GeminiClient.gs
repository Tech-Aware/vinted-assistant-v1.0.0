/**
 * GeminiClient.gs - Client API Gemini via UrlFetchApp
 *
 * Port de infrastructure/gemini_client.py
 * Utilise l'API REST Gemini directement avec UrlFetchApp.
 *
 * Gestion robuste des quotas Free Tier (HTTP 429) :
 *  - MAX_RETRIES limite a 2 (au-dela on aggrave la saturation)
 *  - Lecture du RetryInfo structure (google.rpc.RetryInfo) du payload d'erreur
 *  - Lecture de l'en-tete HTTP Retry-After
 *  - Distinction quota/jour (pas de retry) vs quota/minute (retry court)
 *  - Fallback automatique de modele sur 429 (chaine MODEL_FALLBACK_CHAIN)
 *  - Cache de resultat (hash du payload, TTL 1h) pour eviter les rejouages
 *  - Verrou utilisateur (LockService) anti double-clic
 *  - Message d'erreur utilisateur clair (delai d'attente + lien facturation)
 */
var GeminiClient = (function() {
  var CLIENT_VERSION = '2026-04-22-r1';
  // Sur 429 on consomme une requete par tentative : 2 max suffit.
  var MAX_RETRIES = 2;
  var BASE_DELAY_MS = 2000;
  var MAX_DELAY_MS = 60000;
  // Chaine de fallback : chaque modele a son propre seau de quota Free Tier.
  // L'ordre va du plus capable au plus economique.
  var MODEL_FALLBACK_CHAIN = [
    'gemini-2.5-flash',
    'gemini-2.5-flash-lite',
    'gemini-2.0-flash'
  ];
  // Cache de resultat : 1h. Permet de relancer la meme analyse sans rappel API.
  var CACHE_TTL_SECONDS = 3600;
  // CacheService.put() limite la valeur a 100 Ko.
  var CACHE_MAX_VALUE_BYTES = 95 * 1024;
  // Verrou par utilisateur : 0ms => fail-fast si un appel est deja en cours.
  var USER_LOCK_TIMEOUT_MS = 0;
  // Lien explicite pour activer la facturation Gemini (Tier 1).
  var BILLING_URL = 'https://aistudio.google.com/apikey';

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
    // Log du nombre d'images effectivement ajoutees
    var imageCount = parts.length - 1; // -1 pour le part texte
    Logger.log('GeminiClient: ' + imageCount + ' image(s) ajoutee(s) sur ' + imageDataArray.length + ' recue(s)');
    Logger.log(
      'GeminiClient version=%s model=%s retries=%s baseDelayMs=%s maxDelayMs=%s',
      CLIENT_VERSION,
      normalizeModelName_(modelName),
      MAX_RETRIES,
      BASE_DELAY_MS,
      MAX_DELAY_MS
    );
    if (imageCount === 0) {
      return { error: 'Aucune image valide a envoyer a Gemini. Les donnees base64 sont absentes.' };
    }

    var requestedModel = normalizeModelName_(modelName);

    // 1) Cache : si la meme analyse a deja ete faite, on resert le resultat.
    var cacheKey = buildCacheKey_(requestedModel, parts);
    var cached = readCache_(cacheKey);
    if (cached) {
      Logger.log('GeminiClient: cache hit (key=' + cacheKey + '). Pas d\'appel API.');
      return cached;
    }

    // 2) Verrou utilisateur : evite les double-clics et appels concurrents
    //    par le meme utilisateur (ne bloque pas les autres utilisateurs).
    var lock = null;
    try {
      lock = LockService.getUserLock();
    } catch (lockInitErr) {
      // En contexte non interactif (ex: trigger) getUserLock peut echouer.
      lock = null;
    }
    if (lock) {
      try {
        if (!lock.tryLock(USER_LOCK_TIMEOUT_MS)) {
          return { error: 'Une analyse est deja en cours pour votre session. Patientez quelques secondes avant de relancer.' };
        }
      } catch (lockErr) {
        // Si le lock n'est pas disponible, on continue quand meme.
        lock = null;
      }
    }

    try {
      // 3) Appel avec fallback de modele en cascade sur 429.
      var result = callWithModelFallback_(apiKey, requestedModel, parts);

      // 4) Mise en cache si succes.
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
   * Tente l'appel API avec le modele demande, puis bascule sur les modeles
   * de fallback si on prend un 429 quota/minute (chaque modele ayant son
   * propre seau de quota Free Tier). Le quota journalier ne declenche PAS
   * de fallback (la cle entiere est limitee).
   */
  function callWithModelFallback_(apiKey, requestedModel, parts) {
    var chain = buildFallbackChain_(requestedModel);
    var lastResult = null;
    for (var i = 0; i < chain.length; i++) {
      var model = chain[i];
      if (i > 0) {
        Logger.log('GeminiClient: fallback de modele -> ' + model);
      }
      var result = callApiWithRetry_(apiKey, model, parts);
      if (result && result.text) {
        return result;
      }
      lastResult = result;
      // On ne bascule QUE sur quota/minute. Pour quota/jour, daily est sur
      // toute la cle et changer de modele ne sert a rien.
      if (!result || !result._retryWithOtherModel) {
        return result;
      }
    }
    return lastResult;
  }

  /**
   * Construit la chaine de fallback de modele en commencant par le modele
   * demande, puis en ajoutant les autres dans l'ordre, sans doublon.
   */
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

  /**
   * Appel API Gemini avec retry exponentiel court.
   * Retourne {text} en succes, {error, ...} en echec.
   * En cas de 429 quota/minute le retour porte _retryWithOtherModel:true
   * pour signaler au caller qu'un fallback de modele est pertinent.
   */
  function callApiWithRetry_(apiKey, modelName, parts) {
    var lastError = null;
    for (var attempt = 0; attempt < MAX_RETRIES; attempt++) {
      try {
        var result = callApi_(apiKey, modelName, parts);
        return result;
      } catch (err) {
        lastError = err;
        var errMsg = String(err && err.message ? err.message : '').toLowerCase();
        var status = err && err.statusCode ? err.statusCode : 0;

        // Auth : non recuperable, on s'arrete tout de suite.
        var authPatterns = ['api key expired', 'api_key_expired', 'api key invalid', 'permission denied', 'unauthenticated'];
        var isAuthError = status === 401 || status === 403 || authPatterns.some(function(p) { return errMsg.indexOf(p) !== -1; });
        if (isAuthError) {
          break;
        }

        // Quota journalier : pas de retry (la fenetre est de 24h).
        if (err && err.isDailyQuota) {
          Logger.log('GeminiClient: quota journalier epuise (model=' + modelName + '). Pas de retry.');
          break;
        }

        // Recuperabilite : 429, 5xx, timeout, reseau.
        var retryablePatterns = ['timeout', 'rate limit', 'quota', '503', '502', '504',
                                 'connection', 'network', 'temporarily unavailable',
                                 'resource exhausted', 'deadline exceeded'];
        var isRetryable = status === 429 || status === 502 || status === 503 || status === 504 ||
                          retryablePatterns.some(function(p) { return errMsg.indexOf(p) !== -1; });

        if (isRetryable && attempt < MAX_RETRIES - 1) {
          var delay = computeRetryDelayMs_(err, attempt);
          Logger.log('GeminiClient: erreur recuperable (tentative ' + (attempt + 1) + '/' + MAX_RETRIES + ', model=' + modelName + '). Retry dans ' + delay + 'ms. Erreur: ' + err.message);
          Utilities.sleep(delay);
        } else {
          break;
        }
      }
    }
    return buildErrorResult_(lastError, modelName);
  }

  /**
   * Calcule le delai de retry. Ordre de priorite :
   *  1. RetryInfo structure (err.retryDelayMs) - source de verite Google
   *  2. En-tete HTTP Retry-After (err.retryAfterMs)
   *  3. Mention "please retry in Xs" dans le message texte
   *  4. Backoff exponentiel
   */
  function computeRetryDelayMs_(err, attempt) {
    if (err && typeof err.retryDelayMs === 'number' && err.retryDelayMs > 0) {
      return Math.min(err.retryDelayMs + 500, MAX_DELAY_MS);
    }
    if (err && typeof err.retryAfterMs === 'number' && err.retryAfterMs > 0) {
      return Math.min(err.retryAfterMs + 500, MAX_DELAY_MS);
    }
    var msg = String(err && err.message ? err.message : '');
    var explicitDelayMatch = msg.match(/please retry in\s+([0-9]+(?:\.[0-9]+)?)s/i);
    if (explicitDelayMatch && explicitDelayMatch[1]) {
      var apiDelayMs = Math.ceil(parseFloat(explicitDelayMatch[1]) * 1000);
      if (!isNaN(apiDelayMs) && apiDelayMs > 0) {
        return Math.min(apiDelayMs + 500, MAX_DELAY_MS);
      }
    }
    var exponential = BASE_DELAY_MS * Math.pow(2, attempt);
    return Math.min(exponential, MAX_DELAY_MS);
  }
  /**
   * Appel direct a l'API Gemini REST.
   * Sur erreur HTTP, leve une Error enrichie avec :
   *   - statusCode  : code HTTP
   *   - retryAfterMs: depuis l'en-tete Retry-After (si present)
   *   - retryDelayMs: depuis google.rpc.RetryInfo (si present)
   *   - isDailyQuota: true si le 429 cible un quota journalier (PerDay)
   *   - errorBody  : payload d'erreur parse (pour message utilisateur)
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
      // En-tete HTTP Retry-After (en secondes ou date HTTP)
      try {
        var headers = response.getHeaders() || {};
        var retryAfter = headers['Retry-After'] || headers['retry-after'];
        if (retryAfter) {
          var asInt = parseInt(retryAfter, 10);
          if (!isNaN(asInt) && asInt > 0) {
            err.retryAfterMs = asInt * 1000;
          }
        }
      } catch (e) { /* headers non disponibles */ }
      // RetryInfo structure dans error.details[]
      var retryInfo = extractRetryInfo_(errorBody);
      if (retryInfo && retryInfo > 0) {
        err.retryDelayMs = retryInfo;
      }
      // Detection quota journalier (PerDay) : pas de retry pertinent.
      if (responseCode === 429) {
        err.isDailyQuota = isDailyQuotaError_(errorBody, errorMsg);
      }
      throw err;
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

  /**
   * Cherche un bloc google.rpc.RetryInfo dans error.details[] et renvoie
   * le delai en ms, ou null s'il n'y en a pas.
   * Format Google: { "@type": "type.googleapis.com/google.rpc.RetryInfo",
   *                  "retryDelay": "41s" } ou "41.6s".
   */
  function extractRetryInfo_(errorBody) {
    if (!errorBody || !errorBody.error || !errorBody.error.details) return null;
    var details = errorBody.error.details;
    for (var i = 0; i < details.length; i++) {
      var d = details[i] || {};
      var t = d['@type'] || '';
      if (t.indexOf('google.rpc.RetryInfo') !== -1 && d.retryDelay) {
        var m = String(d.retryDelay).match(/^([0-9]+(?:\.[0-9]+)?)s$/i);
        if (m) {
          return Math.ceil(parseFloat(m[1]) * 1000);
        }
      }
    }
    return null;
  }

  /**
   * Detecte si un 429 cible un quota journalier (PerDay) plutot que par minute.
   * On scanne les details QuotaFailure et le texte du message.
   */
  function isDailyQuotaError_(errorBody, fallbackMessage) {
    var lower = String(fallbackMessage || '').toLowerCase();
    if (lower.indexOf('per day') !== -1 || lower.indexOf('per_day') !== -1 || lower.indexOf('perday') !== -1) {
      return true;
    }
    if (!errorBody || !errorBody.error || !errorBody.error.details) return false;
    var details = errorBody.error.details;
    for (var i = 0; i < details.length; i++) {
      var d = details[i] || {};
      var t = d['@type'] || '';
      if (t.indexOf('QuotaFailure') !== -1 && Array.isArray(d.violations)) {
        for (var j = 0; j < d.violations.length; j++) {
          var v = d.violations[j] || {};
          var qid = String(v.quotaId || v.quotaMetric || '').toLowerCase();
          if (qid.indexOf('perday') !== -1 || qid.indexOf('per_day') !== -1) {
            return true;
          }
        }
      }
    }
    return false;
  }

  /**
   * Construit le message d'erreur a remonter a l'utilisateur, avec :
   *  - delai d'attente recommande quand on l'a ;
   *  - message specifique pour quota journalier ;
   *  - lien vers la page Gemini API (facturation / cles).
   * Pose le drapeau _retryWithOtherModel sur 429 quota/minute pour permettre
   * au caller de basculer de modele.
   */
  function buildErrorResult_(err, modelName) {
    if (!err) {
      return { error: 'Erreur API Gemini inconnue.' };
    }
    var status = err.statusCode || 0;
    var raw = err.message || 'erreur inconnue';

    if (status === 429) {
      var waitMs = err.retryDelayMs || err.retryAfterMs || 0;
      var waitSec = waitMs > 0 ? Math.ceil(waitMs / 1000) : 0;
      if (err.isDailyQuota) {
        return {
          error: 'Quota journalier Gemini Free Tier epuise pour le modele ' + modelName + '. ' +
                 'Reessayez demain ou activez la facturation (Tier payant) : ' + BILLING_URL,
          quotaExceeded: true,
          quotaPeriod: 'day',
          model: modelName
        };
      }
      var msg = 'Quota Gemini Free Tier sature (' + MAX_RETRIES + ' tentatives, modele ' + modelName + ').';
      if (waitSec > 0) {
        msg += ' Reessayez dans ' + waitSec + ' s.';
      }
      msg += ' Pour eviter ce blocage, activez la facturation : ' + BILLING_URL;
      return {
        error: msg,
        quotaExceeded: true,
        quotaPeriod: 'minute',
        retryAfterSec: waitSec || null,
        model: modelName,
        // Drapeau interne pour declencher un fallback de modele.
        _retryWithOtherModel: true
      };
    }
    if (status === 401 || status === 403) {
      return {
        error: 'Cle API Gemini invalide ou non autorisee. Verifiez la configuration.',
        authError: true
      };
    }
    return { error: 'Erreur API Gemini apres ' + MAX_RETRIES + ' tentatives: ' + raw };
  }

  // ============================================================
  // Cache de resultat
  // ============================================================

  /**
   * Cle de cache = SHA-1 hex de (modele + parts JSON).
   * Couvre prompt + images + measurement_mode (puisque tout est dans parts).
   */
  function buildCacheKey_(modelName, parts) {
    var raw = modelName + '|' + JSON.stringify(parts);
    var bytes = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, raw, Utilities.Charset.UTF_8);
    var hex = '';
    for (var i = 0; i < bytes.length; i++) {
      var b = bytes[i] & 0xff;
      hex += (b < 16 ? '0' : '') + b.toString(16);
    }
    return 'gemini:v1:' + hex;
  }

  function getCache_() {
    try {
      return CacheService.getScriptCache();
    } catch (e) {
      return null;
    }
  }

  function readCache_(key) {
    var cache = getCache_();
    if (!cache) return null;
    try {
      var raw = cache.get(key);
      if (!raw) return null;
      var parsed = JSON.parse(raw);
      return parsed;
    } catch (e) {
      return null;
    }
  }

  function writeCache_(key, value) {
    var cache = getCache_();
    if (!cache) return;
    try {
      var serialized = JSON.stringify(value);
      // CacheService limite la valeur a 100 Ko : on mesure la taille en
      // octets UTF-8 reels (et pas en chars JS) pour ne pas sous-estimer.
      var byteLength;
      try {
        byteLength = Utilities.newBlob(serialized).getBytes().length;
      } catch (e) {
        byteLength = serialized.length;
      }
      if (byteLength > CACHE_MAX_VALUE_BYTES) {
        Logger.log('GeminiClient: resultat trop gros pour cache (' + byteLength + ' bytes), skip.');
        return;
      }
      cache.put(key, serialized, CACHE_TTL_SECONDS);
    } catch (e) {
      Logger.log('GeminiClient: ecriture cache impossible: ' + e.message);
    }
  }

  return {
    generateContent: generateContent
  };
})();
