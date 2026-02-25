/**
 * TextExtractors.gs - Fonctions d'extraction de texte
 *
 * Port de domain/normalizers/text_extractors.py
 */

var TextExtractors = (function() {

  function extractModelFromText(text) {
    if (!text) return null;
    var match = text.match(/\b(\d{3})\b/);
    return match ? match[1] : null;
  }

  function extractFitFromText(text) {
    if (!text) return null;
    var low = text.toLowerCase();
    if (low.indexOf('skinny') !== -1 || low.indexOf('slim') !== -1) return 'Skinny';
    if (low.indexOf('straight') !== -1 || low.indexOf('droit') !== -1) return 'Straight/Droit';
    if (low.indexOf('bootcut') !== -1 || low.indexOf('flare') !== -1 || low.indexOf('évasé') !== -1) return 'Bootcut/Évasé';
    return null;
  }

  function extractColorFromText(text) {
    if (!text) return null;
    var low = text.toLowerCase();
    var colorMap = [
      [['bleu brut', 'raw blue', 'raw denim', 'bleu foncé', 'dark blue'], 'bleu brut'],
      [['noir', 'black'], 'noir'],
      [['bleu moyen', 'medium blue', 'mid wash'], 'bleu moyen'],
      [['bleu clair', 'light blue', 'light wash'], 'bleu clair'],
      [['gris', 'grey', 'gray'], 'gris'],
      [['blanc', 'white', 'ecru'], 'blanc'],
      [['beige', 'cream', 'crème'], 'beige'],
      [['marron', 'brown'], 'marron'],
      [['vert', 'green', 'kaki', 'olive'], 'vert'],
      [['bordeaux', 'burgundy', 'wine'], 'bordeaux'],
      [['rouge', 'red'], 'rouge']
    ];

    for (var i = 0; i < colorMap.length; i++) {
      var keywords = colorMap[i][0];
      var label = colorMap[i][1];
      for (var j = 0; j < keywords.length; j++) {
        if (low.indexOf(keywords[j]) !== -1) return label;
      }
    }
    return null;
  }

  function extractSizesFromText(text) {
    if (!text) return [null, null];
    var upper = text.toUpperCase();
    var wMatch = upper.match(/W\s*(\d{2,3})/);
    var lMatch = upper.match(/L\s*(\d{2,3})/);
    var sizeUs = wMatch ? 'W' + wMatch[1] : null;
    var length = lMatch ? 'L' + lMatch[1] : null;
    return [sizeUs, length];
  }

  function normalizeFitLabel(value) {
    if (!value) return null;
    var v = String(value).trim().toLowerCase();
    if (v.indexOf('skinny') !== -1 || v.indexOf('slim') !== -1) return 'Skinny';
    if (v.indexOf('straight') !== -1 || v.indexOf('droit') !== -1) return 'Straight/Droit';
    if (v.indexOf('bootcut') !== -1 || v.indexOf('flare') !== -1 || v.indexOf('évasé') !== -1) return 'Bootcut/Évasé';
    return value.trim() || null;
  }

  function normalizeSkuValue(raw) {
    if (!raw) return null;
    var cleaned = String(raw).trim().toUpperCase().replace(/\s/g, '');
    if (!cleaned) return null;

    // Refuser les codes usine (ex: 18-24-8)
    if (/^\d{2}-\d{2}-\d{1,2}$/.test(cleaned)) return null;

    // Format attendu : LETTRES + CHIFFRES
    if (/^[A-Z]{2,6}\d{1,8}$/.test(cleaned)) return cleaned;

    return null;
  }

  function extractGenderFromSkuPrefix(sku) {
    if (!sku) return null;
    var upper = String(sku).trim().toUpperCase();
    if (upper.indexOf('JLF') === 0) return 'femme';
    if (upper.indexOf('JLH') === 0) return 'homme';
    if (upper.indexOf('PTF') === 0) return 'femme';
    if (upper.indexOf('PTH') === 0 || upper.indexOf('PTNF') === 0) return 'femme';
    return null;
  }

  function detectFlagFromText(text, keywords) {
    if (!text || !keywords) return false;
    var low = text.toLowerCase();
    for (var i = 0; i < keywords.length; i++) {
      if (low.indexOf(keywords[i].toLowerCase()) !== -1) return true;
    }
    return false;
  }

  function detectChestPocketFromText(text) {
    return detectFlagFromText(text, ['poche poitrine', 'chest pocket', 'poche avant']);
  }

  function normalizeCarharttModel(model, fullText) {
    if (!model) return null;
    var cleaned = model.trim();
    // Normaliser des noms courants
    var low = cleaned.toLowerCase();
    if (low.indexOf('detroit') !== -1) return 'Detroit';
    if (low.indexOf('michigan') !== -1) return 'Michigan';
    if (low.indexOf('active') !== -1) return 'Active';
    if (low.indexOf('chore') !== -1) return 'Chore';
    return cleaned;
  }

  function normalizeJcrSku(raw) {
    if (!raw) return null;
    var cleaned = String(raw).trim().toUpperCase().replace(/\s/g, '');
    if (/^JCR\d+$/.test(cleaned)) return cleaned;
    return null;
  }

  function extractCarharttModelFromText(text) {
    if (!text) return null;
    var low = text.toLowerCase();
    if (low.indexOf('detroit') !== -1) return 'Detroit';
    if (low.indexOf('michigan') !== -1) return 'Michigan';
    if (low.indexOf('active') !== -1) return 'Active';
    if (low.indexOf('chore') !== -1) return 'Chore';
    return null;
  }

  // Fonctions pour composition Carhartt
  function stripParenthesesNotes(text) {
    if (!text) return text;
    return text.replace(/\((?:[^)(]+|\([^)(]*\))*\)/g, '').trim();
  }

  function stripCompositionPrefixes(text) {
    if (!text) return text;
    return text
      .replace(/^(composition|matiere|material)[:\-]?\s*/i, '')
      .trim();
  }

  function extractLiningFromText(text) {
    if (!text) return null;
    var low = text.toLowerCase();
    if (low.indexOf('matelassé') !== -1 || low.indexOf('matelasse') !== -1 || low.indexOf('quilted') !== -1) return 'matelassée';
    if (low.indexOf('sherpa') !== -1) return 'sherpa';
    if (low.indexOf('blanket') !== -1) return 'blanket lining';
    return null;
  }

  function extractBodyLiningComposition(text) { return null; }
  function extractExteriorFromText(text) { return null; }
  function extractSleeveLiningFromText(text) { return null; }
  function extractClosureFromText(text) { return null; }
  function extractPatchMaterialFromText(text) { return null; }
  function extractCollarFromText(text) { return null; }
  function extractZipMaterialFromText(text) { return null; }
  function extractOriginCountryFromText(text) {
    if (!text) return null;
    var low = text.toLowerCase();
    if (low.indexOf('made in mexico') !== -1) return 'Mexico';
    if (low.indexOf('made in usa') !== -1 || low.indexOf('made in u.s.a') !== -1) return 'USA';
    if (low.indexOf('made in china') !== -1) return 'China';
    if (low.indexOf('made in bangladesh') !== -1) return 'Bangladesh';
    if (low.indexOf('made in turkey') !== -1 || low.indexOf('made in turquie') !== -1) return 'Turkey';
    if (low.indexOf('made in vietnam') !== -1) return 'Vietnam';
    return null;
  }

  function extractCarharttCompositionFromOcrStructured(ocrStructured) {
    return {};
  }

  function splitCarharttCompositionBlocks(text) {
    return {};
  }

  return {
    extractModelFromText: extractModelFromText,
    extractFitFromText: extractFitFromText,
    extractColorFromText: extractColorFromText,
    extractSizesFromText: extractSizesFromText,
    normalizeFitLabel: normalizeFitLabel,
    normalizeSkuValue: normalizeSkuValue,
    extractGenderFromSkuPrefix: extractGenderFromSkuPrefix,
    detectFlagFromText: detectFlagFromText,
    detectChestPocketFromText: detectChestPocketFromText,
    normalizeCarharttModel: normalizeCarharttModel,
    normalizeJcrSku: normalizeJcrSku,
    extractCarharttModelFromText: extractCarharttModelFromText,
    stripParenthesesNotes: stripParenthesesNotes,
    stripCompositionPrefixes: stripCompositionPrefixes,
    extractLiningFromText: extractLiningFromText,
    extractBodyLiningComposition: extractBodyLiningComposition,
    extractExteriorFromText: extractExteriorFromText,
    extractSleeveLiningFromText: extractSleeveLiningFromText,
    extractClosureFromText: extractClosureFromText,
    extractPatchMaterialFromText: extractPatchMaterialFromText,
    extractCollarFromText: extractCollarFromText,
    extractZipMaterialFromText: extractZipMaterialFromText,
    extractOriginCountryFromText: extractOriginCountryFromText,
    extractCarharttCompositionFromOcrStructured: extractCarharttCompositionFromOcrStructured,
    splitCarharttCompositionBlocks: splitCarharttCompositionBlocks
  };

})();
