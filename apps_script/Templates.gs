/**
 * Templates.gs - Profils d'analyse (AnalysisProfile)
 *
 * Port de domain/templates/
 */
var Templates = (function() {
  // Profils disponibles
  var PROFILES = {
    jean_levis: {
      name: 'jean_levis',
      label: 'Jean Levi\'s',
      promptSuffix: '\nSelected analysis profile: "jean_levis"\nYou MUST include the "features" object as defined in the EXTENDED OUTPUT section for jean_levis.\n\nJSON ONLY.',
      jsonSchema: {
        type: 'object',
        properties: {
          ai: { type: 'object' },
          title: { type: 'string' },
          description: { type: 'string' },
          brand: { type: ['string', 'null'] },
          style: { type: ['string', 'null'] },
          pattern: { type: ['string', 'null'] },
          neckline: { type: ['string', 'null'] },
          season: { type: ['string', 'null'] },
          defects: { type: ['string', 'null'] },
          features: {
            type: 'object',
            properties: {
              brand: { type: ['string', 'null'] },
              model: { type: ['string', 'null'] },
              fit: { type: ['string', 'null'] },
              color: { type: ['string', 'null'] },
              size_fr: { type: ['string', 'null'] },
              size_us: { type: ['string', 'null'] },
              length: { type: ['string', 'null'] },
              cotton_percent: { type: ['number', 'null'] },
              elasthane_percent: { type: ['number', 'null'] },
              rise_type: { type: ['string', 'null'] },
              rise_cm: { type: ['number', 'null'] },
              gender: { type: ['string', 'null'] },
              is_premium: { type: ['boolean', 'null'] },
              sku: { type: ['string', 'null'] },
              sku_status: { type: 'string' }
            }
          }
        },
        required: ['ai', 'title', 'description', 'brand', 'features']
      }
    },
    pull: {
      name: 'pull',
      label: 'Pull / Gilet',
      promptSuffix: '\nSelected analysis profile: "pull"\nYou MUST include the "features" object as defined in the EXTENDED OUTPUT section for pull.\n\nJSON ONLY.',
      jsonSchema: {
        type: 'object',
        properties: {
          ai: { type: 'object' },
          title: { type: 'string' },
          description: { type: 'string' },
          brand: { type: ['string', 'null'] },
          style: { type: ['string', 'null'] },
          pattern: { type: ['string', 'null'] },
          neckline: { type: ['string', 'null'] },
          season: { type: ['string', 'null'] },
          defects: { type: ['string', 'null'] },
          features: {
            type: 'object',
            properties: {
              brand: { type: ['string', 'null'] },
              garment_type: { type: ['string', 'null'] },
              neckline: { type: ['string', 'null'] },
              pattern: { type: ['string', 'null'] },
              main_colors: { type: ['array', 'null'] },
              material: { type: ['string', 'null'] },
              cotton_percent: { type: ['number', 'null'] },
              wool_percent: { type: ['number', 'null'] },
              gender: { type: ['string', 'null'] },
              size: { type: ['string', 'null'] },
              size_estimated: { type: ['string', 'null'] },
              size_source: { type: ['string', 'null'] },
              is_premium: { type: ['boolean', 'null'] },
              sku: { type: ['string', 'null'] },
              sku_status: { type: 'string' }
            }
          }
        },
        required: ['ai', 'title', 'description', 'brand', 'features']
      }
    },
    jacket_carhart: {
      name: 'jacket_carhart',
      label: 'Veste Carhartt',
      promptSuffix: '\nSelected analysis profile: "jacket_carhart"\nYou MUST include the "features" object as defined in the EXTENDED OUTPUT section for jacket_carhart.\n\nJSON ONLY.',
      jsonSchema: {
        type: 'object',
        properties: {
          ai: { type: 'object' },
          title: { type: 'string' },
          description: { type: 'string' },
          brand: { type: ['string', 'null'] },
          style: { type: ['string', 'null'] },
          pattern: { type: ['string', 'null'] },
          neckline: { type: ['string', 'null'] },
          season: { type: ['string', 'null'] },
          defects: { type: ['string', 'null'] },
          features: {
            type: 'object',
            properties: {
              brand: { type: ['string', 'null'] },
              model: { type: ['string', 'null'] },
              size: { type: ['string', 'null'] },
              color: { type: ['string', 'null'] },
              gender: { type: ['string', 'null'] },
              has_hood: { type: ['boolean', 'null'] },
              pattern: { type: ['string', 'null'] },
              lining: { type: ['string', 'null'] },
              closure: { type: ['string', 'null'] },
              patch_material: { type: ['string', 'null'] },
              is_camouflage: { type: ['boolean', 'null'] },
              is_realtree: { type: ['boolean', 'null'] },
              is_new_york: { type: ['boolean', 'null'] },
              is_premium: { type: ['boolean', 'null'] },
              sku: { type: ['string', 'null'] },
              sku_status: { type: 'string' }
            }
          }
        },
        required: ['ai', 'title', 'description', 'brand', 'features']
      }
    },
    short_carhart: {
      name: 'short_carhart',
      label: 'Short Carhartt',
      promptSuffix: '\nSelected analysis profile: "short_carhart"\nYou MUST include the "features" object as defined in the EXTENDED OUTPUT section for short_carhart.\n\nJSON ONLY.',
      jsonSchema: {
        type: 'object',
        properties: {
          ai: { type: 'object' },
          title: { type: 'string' },
          description: { type: 'string' },
          brand: { type: ['string', 'null'] },
          style: { type: ['string', 'null'] },
          pattern: { type: ['string', 'null'] },
          season: { type: ['string', 'null'] },
          defects: { type: ['string', 'null'] },
          features: {
            type: 'object',
            properties: {
              brand: { type: ['string', 'null'] },
              model: { type: ['string', 'null'] },
              size: { type: ['string', 'null'] },
              color: { type: ['string', 'null'] },
              gender: { type: ['string', 'null'] },
              material: { type: ['string', 'null'] },
              closure: { type: ['string', 'null'] },
              has_cargo_pockets: { type: ['boolean', 'null'] },
              has_belt_loops: { type: ['boolean', 'null'] },
              pattern: { type: ['string', 'null'] },
              origin_country: { type: ['string', 'null'] },
              is_premium: { type: ['boolean', 'null'] },
              sku: { type: ['string', 'null'] },
              sku_status: { type: 'string' }
            }
          }
        },
        required: ['ai', 'title', 'description', 'brand', 'features']
      }
    },
    short_adidas: {
      name: 'short_adidas',
      label: 'Short Adidas',
      promptSuffix: '\nSelected analysis profile: "short_adidas"\nYou MUST include the "features" object as defined in the EXTENDED OUTPUT section for short_adidas.\n\nJSON ONLY.',
      jsonSchema: {
        type: 'object',
        properties: {
          ai: { type: 'object' },
          title: { type: 'string' },
          description: { type: 'string' },
          brand: { type: ['string', 'null'] },
          style: { type: ['string', 'null'] },
          pattern: { type: ['string', 'null'] },
          season: { type: ['string', 'null'] },
          defects: { type: ['string', 'null'] },
          features: {
            type: 'object',
            properties: {
              brand: { type: ['string', 'null'] },
              model: { type: ['string', 'null'] },
              size: { type: ['string', 'null'] },
              color: { type: ['string', 'null'] },
              gender: { type: ['string', 'null'] },
              material: { type: ['string', 'null'] },
              technology: { type: ['string', 'null'] },
              has_side_pockets: { type: ['boolean', 'null'] },
              has_drawstring: { type: ['boolean', 'null'] },
              pattern: { type: ['string', 'null'] },
              origin_country: { type: ['string', 'null'] },
              is_premium: { type: ['boolean', 'null'] },
              sku: { type: ['string', 'null'] },
              sku_status: { type: 'string' }
            }
          }
        },
        required: ['ai', 'title', 'description', 'brand', 'features']
      }
    }
  };
  return {
    getProfile: function(name) {
      return PROFILES[name] || null;
    },
    listProfiles: function() {
      var list = [];
      for (var key in PROFILES) {
        list.push({ name: key, label: PROFILES[key].label });
      }
      return list;
    },
    getAllProfiles: function() {
      return PROFILES;
    }
  };
})();