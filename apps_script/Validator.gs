/**
 * Validator.gs - Validation des SKU et listings
 *
 * Port de domain/validator.py
 */
var Validator = (function() {
  // SKU interne Durin : LETTRES + CHIFFRES (ex: JLF123, PTF42, PTNF007)
  var INTERNAL_SKU_RE = /^[A-Z]{2,6}\d{1,8}$/;
  // Codes usine / lavage (INTERDITS comme SKU) ex: 18-24-8
  var FACTORY_CODE_RE = /^\d{2}-\d{2}-\d{1,2}$/;
  function cleanSku(raw) {
    if (!raw) return null;
    return String(raw).trim().toUpperCase().replace(/\s/g, '') || null;
  }
  /**
   * Valide un SKU interne Durin.
   */
  function isValidInternalSku(profileName, sku) {
    var skuClean = cleanSku(sku);
    if (!skuClean) return false;
    // Refus des codes usine
    if (FACTORY_CODE_RE.test(skuClean)) {
      Logger.log('SKU rejete (profil=' + profileName + '): code usine detecte (' + skuClean + ')');
      return false;
    }
    // Format attendu : LETTRES + CHIFFRES
    if (!INTERNAL_SKU_RE.test(skuClean)) {
      Logger.log('SKU rejete (profil=' + profileName + '): format interne invalide (' + skuClean + ')');
      return false;
    }
    return true;
  }
  /**
   * Valide un listing basique.
   */
  function validateListing(data) {
    var errors = [];
    var title = data.title;
    if (!title || !title.trim()) {
      errors.push('title is required and must be non-empty');
    }
    var desc = data.description;
    if (!desc || desc.split(/\s+/).length < 5) {
      errors.push('description must contain at least 5 words');
    }
    if (title && title.indexOf('!!!!') !== -1) {
      errors.push('title contains spam punctuation');
    }
    if (errors.length > 0) {
      throw new Error('Validation errors: ' + errors.join(' / '));
    }
  }
  return {
    isValidInternalSku: isValidInternalSku,
    validateListing: validateListing,
    cleanSku: cleanSku
  };
})();