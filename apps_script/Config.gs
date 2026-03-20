/**
 * Config.gs - Gestion de la configuration via PropertiesService
 *
 * Remplace le fichier .env de la version desktop.
 * Les cles API sont stockees dans les Script Properties (securise).
 */
var Config = (function() {
  var KEYS = {
    GEMINI_API_KEY: 'AIzaSyCf2bol5YwTjhS3wuX_mQlxPsOb5UMUsRo',
    GEMINI_MODEL: 'gemini-2.5-flash',
    LOG_SHEET_ID: '1pnkdcpgrJLPl9gtsuJUfVNQWPeYoXu1uzUthAkvoyOk',
    LOG_LEVEL: 'INFO',
    WEBAPP_URL: 'https://script.google.com/macros/s/AKfycbyrTLTMItIokiX040gXwFJmTLQhmMq_A5ZuLMZr8hTCEOFPm7n2X1_63OvfGXT1DjOa6Q/exec'
  };
  var DEFAULT_MODEL = 'gemini-3-flash-preview';
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
    }
  };
})();