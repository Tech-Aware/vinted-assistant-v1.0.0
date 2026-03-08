/**
 * ProfileEngine.gs - Moteur de profils dynamiques
 *
 * Gere la generation de titres et descriptions pour les profils custom
 * via un systeme de templates avec placeholders {field}.
 */

var ProfileEngine = (function() {

  // =====================================================
  // Title building
  // =====================================================

  /**
   * Construit un titre a partir du template du profil et des features.
   *
   * Template format: "Jean {brand} {model} {size} {color} #{sku}"
   * - Chaque {field} est remplace par la valeur correspondante dans features.
   * - Les champs vides sont supprimes proprement.
   * - #{field} est un prefixe special pour les hashtags inline.
   */
  function buildTitle(profile, features) {
    if (!profile || !profile.titleTemplate) {
      return features.title || '';
    }

    var template = profile.titleTemplate;
    var result = template.replace(/\{(\w+)\}/g, function(match, key) {
      var val = features[key];
      if (val == null || val === '' || val === false) return '';
      if (val === true) return key; // Pour les booleens (ex: {premium} -> "premium")
      if (Array.isArray(val)) return val.filter(Boolean).join(', ');
      return String(val);
    });

    // Nettoyer : supprimer les # sans valeur, les espaces multiples, les espaces avant ponctuation
    result = result.replace(/#\s/g, ' ');
    result = result.replace(/\s{2,}/g, ' ');
    result = result.trim();

    return result;
  }

  // =====================================================
  // Description building
  // =====================================================

  /**
   * Construit une description a partir du template du profil et des features.
   *
   * Si le profil a un descriptionTemplate, l'utilise avec les placeholders.
   * Sinon, utilise la description de l'IA enrichie des infos structurees.
   */
  function buildDescription(profile, features, aiDescription, aiDefects) {
    if (!profile) {
      return aiDescription || '';
    }

    if (profile.descriptionTemplate) {
      return buildFromTemplate_(profile.descriptionTemplate, features, aiDescription, aiDefects, profile);
    }

    // Fallback : description IA enrichie
    return buildGenericDescription_(features, aiDescription, aiDefects, profile);
  }

  /**
   * Construit une description a partir d'un template multi-sections.
   *
   * Format: Chaque ligne avec des placeholders {field}.
   * Lignes speciales:
   *   {ai_description} -> description de l'IA
   *   {ai_defects} -> defauts detectes par l'IA
   *   {hashtags} -> hashtags du profil
   *   {condition} -> etat normalise
   */
  function buildFromTemplate_(template, features, aiDescription, aiDefects, profile) {
    var vars = {};

    // Remplir les variables depuis features
    for (var key in features) {
      if (features.hasOwnProperty(key)) {
        var val = features[key];
        if (val == null || val === '') continue;
        if (Array.isArray(val)) vars[key] = val.filter(Boolean).join(', ');
        else if (typeof val === 'boolean') vars[key] = val ? 'Oui' : 'Non';
        else vars[key] = String(val);
      }
    }

    // Variables speciales
    vars.ai_description = aiDescription || '';
    vars.ai_defects = aiDefects || '';
    vars.hashtags = buildHashtags_(profile, features);
    vars.condition_label = normalizeConditionLabel_(features.condition);

    var result = template.replace(/\{(\w+)\}/g, function(match, key) {
      return vars[key] != null ? vars[key] : '';
    });

    // Nettoyer les lignes vides consecutives
    result = result.replace(/\n{3,}/g, '\n\n');
    return result.trim();
  }

  /**
   * Description generique quand pas de template custom.
   */
  function buildGenericDescription_(features, aiDescription, aiDefects, profile) {
    var parts = [];

    // Description IA
    if (aiDescription) {
      parts.push(aiDescription);
    }

    // Infos structurees
    var infoParts = [];
    if (features.brand) infoParts.push('Marque : ' + features.brand);
    if (features.size || features.size_fr) infoParts.push('Taille : ' + (features.size || features.size_fr));
    if (features.color || features.main_colors) {
      var colors = features.color || (Array.isArray(features.main_colors) ? features.main_colors.join(', ') : '');
      if (colors) infoParts.push('Couleur : ' + colors);
    }
    if (features.condition) infoParts.push('Etat : ' + normalizeConditionLabel_(features.condition));

    if (infoParts.length > 0) parts.push(infoParts.join('\n'));

    // Defauts
    if (aiDefects) {
      parts.push('Defauts : ' + aiDefects);
    }

    // Footer
    var footer = [];
    footer.push('📦 Envoi rapide et soigne.');
    footer.push("💡 Pensez a faire un lot pour beneficier d'une reduction !");

    var hashtags = buildHashtags_(profile, features);
    if (hashtags) footer.push('\n' + hashtags);
    parts.push(footer.join('\n'));

    return parts.filter(Boolean).join('\n\n');
  }

  // =====================================================
  // Prompt building for custom profiles
  // =====================================================

  /**
   * Genere un prompt suffix pour un profil custom.
   * Indique a Gemini quels champs extraire.
   */
  function buildPromptSuffix(profile) {
    if (!profile || !profile.fields || profile.fields.length === 0) {
      return '\nExtract all relevant clothing information.\n\nJSON ONLY.';
    }

    var lines = [
      '\nSelected analysis profile: "' + profile.profileName + '"',
      'You MUST include a "features" object with these fields:'
    ];

    var fieldLines = [];
    for (var i = 0; i < profile.fields.length; i++) {
      var f = profile.fields[i];
      var typeHint = 'string | null';
      if (f.type === 'checkbox') typeHint = 'boolean | null';
      else if (f.type === 'number') typeHint = 'number | null';
      else if (f.type === 'multicheck' || f.isArray) typeHint = 'array | null';
      fieldLines.push('    "' + f.key + '": ' + typeHint);
    }

    lines.push('{');
    lines.push('  "features": {');
    lines.push(fieldLines.join(',\n'));
    lines.push('  }');
    lines.push('}');
    lines.push('');
    lines.push('JSON ONLY.');

    return lines.join('\n');
  }

  // =====================================================
  // Normalization for custom profiles
  // =====================================================

  /**
   * Normalise un resultat IA pour un profil custom.
   * Equivalent de Normalizer.normalizeAndPostprocess mais generique.
   */
  function normalizeCustomProfile(aiData, profile, uiData) {
    uiData = uiData || {};
    var rawFeatures = aiData.features || {};

    // Merge IA + corrections UI
    var features = {};
    for (var key in rawFeatures) {
      if (rawFeatures.hasOwnProperty(key)) {
        features[key] = rawFeatures[key];
      }
    }

    // Appliquer les corrections UI
    var fields = profile.fields || [];
    for (var i = 0; i < fields.length; i++) {
      var field = fields[i];
      if (uiData[field.key] != null && uiData[field.key] !== '') {
        features[field.key] = uiData[field.key];
      }
    }

    // Condition par defaut
    if (!features.condition) features.condition = uiData.condition || 'tres bon etat';

    // SKU depuis UI
    if (uiData.sku) features.sku = uiData.sku;
    if (uiData.order_id) features.order_id = uiData.order_id;

    // Construire titre et description
    var title = buildTitle(profile, features);
    var aiDescription = aiData.description || '';
    var aiDefects = aiData.defects || null;
    var description = buildDescription(profile, features, aiDescription, aiDefects);

    return {
      title: title,
      description: description,
      brand: features.brand || aiData.brand || null,
      features: features,
      sku: features.sku || null,
      sku_status: features.sku_status || null,
      condition: features.condition || null,
      color: features.color || aiData.color || null
    };
  }

  // =====================================================
  // Helpers
  // =====================================================

  function buildHashtags_(profile, features) {
    if (!profile) return '';
    var tags = [];

    // Core hashtags du profil
    var hashtags = profile.hashtags || {};
    if (hashtags.core && Array.isArray(hashtags.core)) {
      for (var i = 0; i < hashtags.core.length; i++) {
        tags.push(hashtags.core[i]);
      }
    }
    if (hashtags.account) tags.push(hashtags.account);

    // Account tag
    if (profile.accountTag && tags.indexOf(profile.accountTag) === -1) {
      tags.push(profile.accountTag);
    }

    // Brand hashtag
    if (features.brand) {
      var brandTag = '#' + features.brand.toLowerCase().replace(/\s/g, '').replace(/'/g, '');
      if (tags.indexOf(brandTag) === -1) tags.push(brandTag);
    }

    return tags.filter(Boolean).join(' ');
  }

  function normalizeConditionLabel_(condition) {
    if (!condition) return 'Tres bon etat';
    var low = condition.toLowerCase().trim();
    if (low === 'neuf') return 'Neuf';
    if (low === 'tres bon etat') return 'Tres bon etat';
    if (low === 'bon etat') return 'Bon etat';
    if (low === 'satisfaisant') return 'Satisfaisant';
    return condition;
  }

  // =====================================================
  // Public API
  // =====================================================

  return {
    buildTitle: buildTitle,
    buildDescription: buildDescription,
    buildPromptSuffix: buildPromptSuffix,
    normalizeCustomProfile: normalizeCustomProfile
  };

})();
