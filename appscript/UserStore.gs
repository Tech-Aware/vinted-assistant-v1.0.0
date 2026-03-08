/**
 * UserStore.gs - Gestion des configurations utilisateur
 *
 * Stocke les preferences utilisateur et profils custom dans un Google Sheet dedie.
 * Chaque utilisateur est identifie par son email Google (Session.getActiveUser()).
 */

var UserStore = (function() {

  var CONFIG_SHEET_KEY = 'USER_CONFIG_SHEET_ID';
  var USERS_SHEET_NAME = 'Users';
  var PROFILES_SHEET_NAME = 'Profiles';

  var USER_HEADERS = ['email', 'displayName', 'apiKey', 'geminiModel', 'creativityLevel', 'defaultProfile', 'createdAt'];
  var PROFILE_HEADERS = [
    'email', 'profileName', 'label', 'isBuiltIn', 'fields', 'titleTemplate',
    'descriptionTemplate', 'promptSuffix', 'skuFormat', 'skuPrefix',
    'hashtags', 'accountTag', 'compositionMaterials', 'conditionOptions'
  ];

  // =====================================================
  // Sheet management
  // =====================================================

  /**
   * Retourne ou cree le Sheet de configuration utilisateur.
   */
  function getOrCreateConfigSheet() {
    var props = PropertiesService.getScriptProperties();
    var sheetId = props.getProperty(CONFIG_SHEET_KEY);

    if (sheetId) {
      try {
        return SpreadsheetApp.openById(sheetId);
      } catch (e) {
        Logger.log('UserStore: sheet configure introuvable, recreation...');
      }
    }

    // Creer un nouveau spreadsheet
    var ss = SpreadsheetApp.create('Vinted Assistant - User Config');
    props.setProperty(CONFIG_SHEET_KEY, ss.getId());

    // Initialiser les feuilles
    var usersSheet = ss.getActiveSheet();
    usersSheet.setName(USERS_SHEET_NAME);
    usersSheet.getRange(1, 1, 1, USER_HEADERS.length).setValues([USER_HEADERS]);
    usersSheet.getRange(1, 1, 1, USER_HEADERS.length).setFontWeight('bold');

    var profilesSheet = ss.insertSheet(PROFILES_SHEET_NAME);
    profilesSheet.getRange(1, 1, 1, PROFILE_HEADERS.length).setValues([PROFILE_HEADERS]);
    profilesSheet.getRange(1, 1, 1, PROFILE_HEADERS.length).setFontWeight('bold');

    Logger.log('UserStore: nouveau sheet cree: ' + ss.getId());
    return ss;
  }

  function getUsersSheet_() {
    return getOrCreateConfigSheet().getSheetByName(USERS_SHEET_NAME);
  }

  function getProfilesSheet_() {
    return getOrCreateConfigSheet().getSheetByName(PROFILES_SHEET_NAME);
  }

  // =====================================================
  // User CRUD
  // =====================================================

  /**
   * Retourne la config utilisateur par email, ou null.
   */
  function getUserByEmail(email) {
    if (!email) return null;
    var sheet = getUsersSheet_();
    var data = sheet.getDataRange().getValues();

    for (var i = 1; i < data.length; i++) {
      if (data[i][0] === email) {
        return {
          email: data[i][0],
          displayName: data[i][1] || '',
          apiKey: data[i][2] || '',
          geminiModel: data[i][3] || '',
          creativityLevel: data[i][4] || 'balanced',
          defaultProfile: data[i][5] || '',
          createdAt: data[i][6] || ''
        };
      }
    }
    return null;
  }

  /**
   * Sauvegarde ou met a jour un utilisateur.
   */
  function saveUser(email, config) {
    if (!email) throw new Error('Email requis');
    var sheet = getUsersSheet_();
    var data = sheet.getDataRange().getValues();

    var rowIndex = -1;
    for (var i = 1; i < data.length; i++) {
      if (data[i][0] === email) { rowIndex = i + 1; break; }
    }

    var row = [
      email,
      config.displayName || '',
      config.apiKey || '',
      config.geminiModel || '',
      config.creativityLevel || 'balanced',
      config.defaultProfile || '',
      config.createdAt || new Date().toISOString()
    ];

    if (rowIndex > 0) {
      sheet.getRange(rowIndex, 1, 1, row.length).setValues([row]);
    } else {
      sheet.appendRow(row);
    }
  }

  // =====================================================
  // Profile CRUD
  // =====================================================

  /**
   * Retourne tous les profils d'un utilisateur.
   */
  function getUserProfiles(email) {
    if (!email) return [];
    var sheet = getProfilesSheet_();
    var data = sheet.getDataRange().getValues();
    var profiles = [];

    for (var i = 1; i < data.length; i++) {
      if (data[i][0] === email) {
        profiles.push(rowToProfile_(data[i]));
      }
    }
    return profiles;
  }

  /**
   * Retourne un profil specifique d'un utilisateur.
   */
  function getProfile(email, profileName) {
    if (!email || !profileName) return null;
    var sheet = getProfilesSheet_();
    var data = sheet.getDataRange().getValues();

    for (var i = 1; i < data.length; i++) {
      if (data[i][0] === email && data[i][1] === profileName) {
        return rowToProfile_(data[i]);
      }
    }
    return null;
  }

  /**
   * Sauvegarde ou met a jour un profil.
   */
  function saveProfile(email, profile) {
    if (!email || !profile.profileName) throw new Error('Email et profileName requis');
    var sheet = getProfilesSheet_();
    var data = sheet.getDataRange().getValues();

    var rowIndex = -1;
    for (var i = 1; i < data.length; i++) {
      if (data[i][0] === email && data[i][1] === profile.profileName) {
        rowIndex = i + 1; break;
      }
    }

    var row = profileToRow_(email, profile);

    if (rowIndex > 0) {
      sheet.getRange(rowIndex, 1, 1, row.length).setValues([row]);
    } else {
      sheet.appendRow(row);
    }
  }

  /**
   * Supprime un profil (sauf built-in).
   */
  function deleteProfile(email, profileName) {
    if (!email || !profileName) return false;
    var sheet = getProfilesSheet_();
    var data = sheet.getDataRange().getValues();

    for (var i = data.length - 1; i >= 1; i--) {
      if (data[i][0] === email && data[i][1] === profileName) {
        sheet.deleteRow(i + 1);
        return true;
      }
    }
    return false;
  }

  // =====================================================
  // Default profiles initialization
  // =====================================================

  /**
   * Copie les profils par defaut pour un nouvel utilisateur.
   */
  function ensureDefaultProfiles(email) {
    if (!email) return;
    var existing = getUserProfiles(email);
    if (existing.length > 0) return; // deja initialise

    var defaults = DefaultProfiles.getAll();
    for (var i = 0; i < defaults.length; i++) {
      var p = defaults[i];
      p.isBuiltIn = true;
      saveProfile(email, p);
    }
    Logger.log('UserStore: profils par defaut crees pour ' + email);
  }

  // =====================================================
  // Serialization helpers
  // =====================================================

  function rowToProfile_(row) {
    return {
      profileName: row[1] || '',
      label: row[2] || '',
      isBuiltIn: row[3] === true || row[3] === 'true',
      fields: safeJsonParse_(row[4]) || [],
      titleTemplate: row[5] || '',
      descriptionTemplate: row[6] || '',
      promptSuffix: row[7] || '',
      skuFormat: row[8] || '',
      skuPrefix: row[9] || '',
      hashtags: safeJsonParse_(row[10]) || {},
      accountTag: row[11] || '',
      compositionMaterials: safeJsonParse_(row[12]) || [],
      conditionOptions: safeJsonParse_(row[13]) || []
    };
  }

  function profileToRow_(email, p) {
    return [
      email,
      p.profileName || '',
      p.label || '',
      p.isBuiltIn ? true : false,
      JSON.stringify(p.fields || []),
      p.titleTemplate || '',
      p.descriptionTemplate || '',
      p.promptSuffix || '',
      p.skuFormat || '',
      p.skuPrefix || '',
      JSON.stringify(p.hashtags || {}),
      p.accountTag || '',
      JSON.stringify(p.compositionMaterials || []),
      JSON.stringify(p.conditionOptions || [])
    ];
  }

  function safeJsonParse_(val) {
    if (!val) return null;
    if (typeof val === 'object') return val;
    try { return JSON.parse(val); } catch (e) { return null; }
  }

  // =====================================================
  // Public API
  // =====================================================

  return {
    getOrCreateConfigSheet: getOrCreateConfigSheet,
    getUserByEmail: getUserByEmail,
    saveUser: saveUser,
    getUserProfiles: getUserProfiles,
    getProfile: getProfile,
    saveProfile: saveProfile,
    deleteProfile: deleteProfile,
    ensureDefaultProfiles: ensureDefaultProfiles
  };

})();
