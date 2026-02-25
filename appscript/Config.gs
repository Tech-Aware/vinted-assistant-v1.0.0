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
    VISION_API_KEY: 'VISION_API_KEY',
    LOG_LEVEL: 'LOG_LEVEL'
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

    getVisionApiKey: function() {
      return getProps_().getProperty(KEYS.VISION_API_KEY) || '';
    },

    setVisionApiKey: function(key) {
      getProps_().setProperty(KEYS.VISION_API_KEY, key);
    },

    getLogLevel: function() {
      return getProps_().getProperty(KEYS.LOG_LEVEL) || 'INFO';
    },

    setLogLevel: function(level) {
      getProps_().setProperty(KEYS.LOG_LEVEL, level);
    },

    getAll: function() {
      return {
        geminiApiKey: this.getGeminiApiKey(),
        geminiModel: this.getGeminiModel(),
        visionApiKey: this.getVisionApiKey(),
        logLevel: this.getLogLevel()
      };
    }
  };

})();
