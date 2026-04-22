/**
 * AIClient.gs - Dispatcher de fournisseur IA (Gemini / OpenAI)
 *
 * API publique unique : AIClient.generateContent(imageDataArray, profile, uiData)
 *
 * Le provider primaire est determine par Config.getAiProvider() (gemini|openai).
 * Si l'autre provider est aussi configure (cle + modele), un fallback automatique
 * est tente sur erreur de quota (HTTP 429 ou quota épuisé) — ce qui donne une
 * vraie redondance multi-fournisseurs sans relancer l'analyse manuellement.
 *
 * Les erreurs d'authentification (401/403) ne declenchent PAS de fallback :
 * la cle est invalide, c'est a l'utilisateur de la corriger.
 */
var AIClient = (function() {

  /**
   * Genere le contenu IA en routant vers le bon provider et en basculant
   * sur l'autre en cas de quota.
   *
   * @param {Object[]} imageDataArray - Images en base64
   * @param {Object} profile - Profil d'analyse
   * @param {Object} uiData - Donnees UI
   * @returns {Object} { text } ou { error, ... }
   */
  function generateContent(imageDataArray, profile, uiData) {
    var primary = (Config.getAiProvider() || 'gemini').toLowerCase();
    var secondary = primary === 'openai' ? 'gemini' : 'openai';

    // Tentative primaire.
    var primaryResult = callProvider_(primary, imageDataArray, profile, uiData);
    if (primaryResult && primaryResult.text && !primaryResult.error) {
      return decorate_(primaryResult, primary);
    }

    // Fallback automatique cross-provider uniquement sur quota epuise,
    // si le second provider est configure.
    if (primaryResult && primaryResult.quotaExceeded && isProviderConfigured_(secondary)) {
      Logger.log('AIClient: fallback cross-provider ' + primary + ' -> ' + secondary + ' (quota).');
      var secondaryResult = callProvider_(secondary, imageDataArray, profile, uiData);
      if (secondaryResult && secondaryResult.text && !secondaryResult.error) {
        return decorate_(secondaryResult, secondary, { fallbackFrom: primary });
      }
      // Les deux ont echoue : on remonte l'erreur primaire enrichie.
      return decorate_(primaryResult, primary, {
        fallbackTried: secondary,
        fallbackError: secondaryResult && secondaryResult.error ? secondaryResult.error : null
      });
    }

    return decorate_(primaryResult || { error: 'Aucun resultat IA.' }, primary);
  }

  /**
   * Renvoie le provider configure par defaut.
   */
  function getProvider() {
    return (Config.getAiProvider() || 'gemini').toLowerCase();
  }

  // ============================================================
  // Internes
  // ============================================================

  function callProvider_(provider, imageDataArray, profile, uiData) {
    if (provider === 'openai') {
      var openAiKey = Config.getOpenAiApiKey();
      if (!openAiKey) {
        return { error: 'Cle API OpenAI non configuree. Ouvrez la configuration (icone engrenage).', authError: true };
      }
      var openAiModel = Config.getOpenAiModel();
      return OpenAIClient.generateContent(openAiKey, openAiModel, imageDataArray, profile, uiData);
    }
    // Default = gemini
    var geminiKey = Config.getGeminiApiKey();
    if (!geminiKey) {
      return { error: 'Cle API Gemini non configuree. Ouvrez la configuration (icone engrenage).', authError: true };
    }
    var geminiModel = Config.getGeminiModel();
    return GeminiClient.generateContent(geminiKey, geminiModel, imageDataArray, profile, uiData);
  }

  function isProviderConfigured_(provider) {
    if (provider === 'openai') {
      return !!(Config.getOpenAiApiKey() && Config.getOpenAiModel());
    }
    return !!(Config.getGeminiApiKey() && Config.getGeminiModel());
  }

  function decorate_(result, provider, extra) {
    if (!result || typeof result !== 'object') return result;
    result.provider = provider;
    if (extra) {
      for (var k in extra) {
        if (Object.prototype.hasOwnProperty.call(extra, k)) {
          result[k] = extra[k];
        }
      }
    }
    return result;
  }

  return {
    generateContent: generateContent,
    getProvider: getProvider
  };
})();
