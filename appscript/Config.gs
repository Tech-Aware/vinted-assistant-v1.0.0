/**
 * Config.gs - Gestion de la configuration via PropertiesService
 *
 * Remplace le fichier .env de la version desktop.
 * Les cles API sont stockees dans les Script Properties (securise).
 */

var Config = (function() {

  var KEYS = {
    GEMINI_API_KEY: 'GEMINI_API_KEY',
    GEMINI_MODEL: 'GEMINI_MODEL',
    LOG_SHEET_ID: 'LOG_SHEET_ID',
    LOG_LEVEL: 'LOG_LEVEL',
    WEBAPP_URL: 'WEBAPP_URL'
  };

  var DEFAULT_MODEL = 'gemini-2.5-flash';

  function getProps_() {
    return PropertiesService.getScriptProperties();
  }

  return {

    getGeminiApiKey: function() {
      return getProps_().getProperty(KEYS.GEMINI_API_KEY) || '';
    },

    setGeminiApiKey: function(key) {
      getProps_().setProperty(KEYS.GEMINI_API_KEY, key);
    },

    getGeminiModel: function() {
      return getProps_().getProperty(KEYS.GEMINI_MODEL) || DEFAULT_MODEL;
    },

    setGeminiModel: function(model) {
      getProps_().setProperty(KEYS.GEMINI_MODEL, model);
    },

    getLogSheetId: function() {
      return getProps_().getProperty(KEYS.LOG_SHEET_ID) || '';
    },

    setLogSheetId: function(id) {
      getProps_().setProperty(KEYS.LOG_SHEET_ID, id);
    },

    getLogLevel: function() {
      return getProps_().getProperty(KEYS.LOG_LEVEL) || 'INFO';
    },

    setLogLevel: function(level) {
      getProps_().setProperty(KEYS.LOG_LEVEL, level);
    },

    getWebAppUrl: function() {
      return getProps_().getProperty(KEYS.WEBAPP_URL) || '';
    },

    setWebAppUrl: function(url) {
      getProps_().setProperty(KEYS.WEBAPP_URL, url);
    },

    getAll: function() {
      return {
        geminiApiKey: this.getGeminiApiKey(),
        geminiModel: this.getGeminiModel(),
        logSheetId: this.getLogSheetId(),
        logLevel: this.getLogLevel(),
        webAppUrl: this.getWebAppUrl()
      };
    },

    /**
     * Retourne l'API key effective pour un utilisateur.
     * Priorite : cle perso utilisateur > cle script globale.
     */
    getEffectiveApiKey: function(userEmail) {
      if (userEmail) {
        var user = UserStore.getUserByEmail(userEmail);
        if (user && user.apiKey) return user.apiKey;
      }
      return this.getGeminiApiKey();
    },

    /**
     * Retourne le modele effectif pour un utilisateur.
     */
    getEffectiveModel: function(userEmail) {
      if (userEmail) {
        var user = UserStore.getUserByEmail(userEmail);
        if (user && user.geminiModel) return user.geminiModel;
      }
      return this.getGeminiModel();
    },

    /**
     * Retourne le niveau de creativite pour un utilisateur.
     * Valeurs : 'conservative' (0.2), 'balanced' (0.5), 'creative' (0.8)
     */
    getCreativityLevel: function(userEmail) {
      if (userEmail) {
        var user = UserStore.getUserByEmail(userEmail);
        if (user && user.creativityLevel) return user.creativityLevel;
      }
      return 'balanced';
    },

    /**
     * Convertit un niveau de creativite en temperature.
     */
    creativityToTemperature: function(level) {
      if (level === 'conservative') return 0.2;
      if (level === 'creative') return 0.8;
      return 0.5; // balanced
    }
  };

})();
