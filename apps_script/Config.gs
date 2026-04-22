/**
 * Config.gs - Gestion de la configuration via PropertiesService
 *
 * Remplace le fichier .env de la version desktop.
 * Les cles API sont stockees dans les Script Properties.
 */
var Config = (function() {
  // Noms CANONIQUES des Script Properties
  var KEYS = {
    GEMINI_API_KEY: 'GEMINI_API_KEY',
    GEMINI_MODEL: 'GEMINI_MODEL',
    OPENAI_API_KEY: 'OPENAI_API_KEY',
    OPENAI_MODEL: 'OPENAI_MODEL',
    AI_PROVIDER: 'AI_PROVIDER',
    LOG_SHEET_ID: 'LOG_SHEET_ID',
    LOG_LEVEL: 'LOG_LEVEL',
    WEBAPP_URL: 'WEBAPP_URL'
  };

  var DEFAULT_OPENAI_MODEL = 'gpt-5.4';
  var DEFAULT_AI_PROVIDER = 'gemini';
  var ALLOWED_PROVIDERS = ['gemini', 'openai'];

  // Legacy keys introduites par erreur dans un ancien commit:
  // des VALEURS concretes etaient utilisees comme noms de proprietes.
  // Note: les valeurs concretes ont ete retirees du code source pour des raisons de securite.
  var LEGACY_KEYS = {
    GEMINI_API_KEY: [],
    GEMINI_MODEL: ['gemini-2.5-flash'],
    LOG_SHEET_ID: [],
    WEBAPP_URL: []
  };

  // Modele stable recommande pour limiter les erreurs quota/free-tier.
  var DEFAULT_MODEL = 'gemini-2.5-flash';

  function getProps_() {
    return PropertiesService.getScriptProperties();
  }

  /**
   * Lit d'abord la cle canonique; en fallback lit une eventuelle cle legacy.
   * Si une valeur legacy est trouvee, elle est migree automatiquement.
   */
  function getPropertyWithLegacy_(canonicalKey, legacyKeys) {
    var props = getProps_();
    var canonicalValue = props.getProperty(canonicalKey);
    if (canonicalValue) {
      return canonicalValue;
    }
    for (var i = 0; i < legacyKeys.length; i++) {
      var legacyKey = legacyKeys[i];
      var legacyValue = props.getProperty(legacyKey);
      if (legacyValue) {
        props.setProperty(canonicalKey, legacyValue);
        return legacyValue;
      }
    }
    return '';
  }

  /**
   * Ecrit la cle canonique et supprime les anciennes cles legacy.
   */
  function setPropertyAndCleanupLegacy_(canonicalKey, value, legacyKeys) {
    var props = getProps_();
    props.setProperty(canonicalKey, value);
    for (var i = 0; i < legacyKeys.length; i++) {
      var legacyKey = legacyKeys[i];
      if (props.getProperty(legacyKey) !== null) {
        props.deleteProperty(legacyKey);
      }
    }
  }

  return {
    getGeminiApiKey: function() {
      return getPropertyWithLegacy_(KEYS.GEMINI_API_KEY, LEGACY_KEYS.GEMINI_API_KEY);
    },
    setGeminiApiKey: function(key) {
      setPropertyAndCleanupLegacy_(
        KEYS.GEMINI_API_KEY,
        key || '',
        LEGACY_KEYS.GEMINI_API_KEY
      );
    },
    getGeminiModel: function() {
      return (
        getPropertyWithLegacy_(KEYS.GEMINI_MODEL, LEGACY_KEYS.GEMINI_MODEL) ||
        DEFAULT_MODEL
      );
    },
    setGeminiModel: function(model) {
      setPropertyAndCleanupLegacy_(
        KEYS.GEMINI_MODEL,
        model || '',
        LEGACY_KEYS.GEMINI_MODEL
      );
    },
    getOpenAiApiKey: function() {
      return getProps_().getProperty(KEYS.OPENAI_API_KEY) || '';
    },
    setOpenAiApiKey: function(key) {
      getProps_().setProperty(KEYS.OPENAI_API_KEY, key || '');
    },
    getOpenAiModel: function() {
      return getProps_().getProperty(KEYS.OPENAI_MODEL) || DEFAULT_OPENAI_MODEL;
    },
    setOpenAiModel: function(model) {
      getProps_().setProperty(KEYS.OPENAI_MODEL, model || '');
    },
    getAiProvider: function() {
      var raw = (getProps_().getProperty(KEYS.AI_PROVIDER) || '').toLowerCase().trim();
      if (ALLOWED_PROVIDERS.indexOf(raw) === -1) {
        return DEFAULT_AI_PROVIDER;
      }
      return raw;
    },
    setAiProvider: function(provider) {
      var clean = (provider || '').toLowerCase().trim();
      if (ALLOWED_PROVIDERS.indexOf(clean) === -1) {
        clean = DEFAULT_AI_PROVIDER;
      }
      getProps_().setProperty(KEYS.AI_PROVIDER, clean);
    },
    getLogSheetId: function() {
      return getPropertyWithLegacy_(KEYS.LOG_SHEET_ID, LEGACY_KEYS.LOG_SHEET_ID);
    },
    setLogSheetId: function(id) {
      setPropertyAndCleanupLegacy_(
        KEYS.LOG_SHEET_ID,
        id || '',
        LEGACY_KEYS.LOG_SHEET_ID
      );
    },
    getLogLevel: function() {
      return getProps_().getProperty(KEYS.LOG_LEVEL) || 'INFO';
    },
    setLogLevel: function(level) {
      getProps_().setProperty(KEYS.LOG_LEVEL, level || 'INFO');
    },
    getWebAppUrl: function() {
      return getPropertyWithLegacy_(KEYS.WEBAPP_URL, LEGACY_KEYS.WEBAPP_URL);
    },
    setWebAppUrl: function(url) {
      setPropertyAndCleanupLegacy_(
        KEYS.WEBAPP_URL,
        url || '',
        LEGACY_KEYS.WEBAPP_URL
      );
    },
    getAll: function() {
      return {
        aiProvider: this.getAiProvider(),
        geminiApiKey: this.getGeminiApiKey(),
        geminiModel: this.getGeminiModel(),
        openAiApiKey: this.getOpenAiApiKey(),
        openAiModel: this.getOpenAiModel(),
        logSheetId: this.getLogSheetId(),
        logLevel: this.getLogLevel(),
        webAppUrl: this.getWebAppUrl()
      };
    }
  };
})();
