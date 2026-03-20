/**
 * Models.gs - Modele VintedListing
 *
 * Port de domain/models.py
 */
var Models = (function() {
  var CONDITION_MAP = {
    'neuf': 'neuf',
    'neuf avec etiquette': 'neuf',
    'tres bon etat': 'tres bon etat',
    'très bon état': 'tres bon etat',
    'bon etat': 'bon etat',
    'bon état': 'bon etat',
    'satisfaisant': 'satisfaisant',
    'mauvais': 'a recycler',
    'pour pieces': 'a recycler',
    'pour pièces': 'a recycler',
    'pour piece': 'a recycler'
  };
  function parseCondition(raw) {
    if (!raw) return null;
    var txt = String(raw).trim().toLowerCase();
    return CONDITION_MAP[txt] || null;
  }
  /**
   * Cree un objet VintedListing a partir d'un dict normalise.
   */
  function createListing(data) {
    data = data || {};
    var listing = {
      title: data.title || '',
      description: data.description || '',
      brand: data.brand || null,
      size: data.size || null,
      condition: parseCondition(data.condition),
      color: data.color || null,
      tags: Array.isArray(data.tags) ? data.tags : [],
      sku: data.sku || null,
      skuStatus: data.sku_status || data.skuStatus || null,
      features: data.features || {},
      manualCompositionText: data.manual_composition_text || null,
      descriptionRaw: data.description_raw || null,
      fallbackReason: data.fallback_reason || null
    };
    validate(listing);
    return listing;
  }
  function validate(listing) {
    var errors = [];
    if (!listing.title || !listing.title.trim()) {
      errors.push('Le titre est obligatoire.');
    }
    if (!listing.description || !listing.description.trim()) {
      errors.push('La description est obligatoire.');
    }
    if (errors.length > 0) {
      throw new Error('Validation VintedListing: ' + errors.join(' / '));
    }
  }
  function toDict(listing) {
    return {
      title: listing.title,
      description: listing.description,
      description_raw: listing.descriptionRaw,
      brand: listing.brand,
      size: listing.size,
      condition: listing.condition,
      color: listing.color,
      tags: listing.tags,
      sku: listing.sku,
      sku_status: listing.skuStatus,
      features: listing.features,
      manual_composition_text: listing.manualCompositionText,
      fallback_reason: listing.fallbackReason
    };
  }
  return {
    createListing: createListing,
    toDict: toDict,
    parseCondition: parseCondition
  };
})();