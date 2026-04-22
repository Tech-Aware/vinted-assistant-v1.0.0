/**
 * DescriptionBuilder.gs - Fonctions utilitaires pour la construction des descriptions
 *
 * Port de domain/description_builder.py
 * Coupes normalisees en 3 categories : Skinny / Droit / Évasé
 */
var DescriptionBuilder = (function() {
  function safeClean(value) {
    if (value == null) return '';
    return String(value).trim();
  }
  function formatPercent(value) {
    if (value == null || value === '') return null;
    try { return parseInt(parseFloat(value)); } catch (e) { return null; }
  }
  function formatRiseLabel(riseType, riseCm) {
    var norm = TitleBuilder.normalizeRiseType(riseType, riseCm);
    if (norm === 'low') return 'taille basse';
    if (norm === 'high') return 'taille haute';
    return 'taille moyenne';
  }
  function normalizeDefects(defects) {
    var base = safeClean(defects);
    if (!base) return '';
    var lowered = base.toLowerCase();
    var cut = base;
    if (lowered.indexOf('voir photos') !== -1) {
      cut = lowered.split('voir photos')[0].trim();
      cut = base.substring(0, cut.length).trim();
    }
    cut = cut.replace(/[. ,;]+$/, '');
    cut = cut.replace(/généralisé/gi, 'visible').replace(/generalise/gi, 'visible');
    return cut;
  }
  function normalizeFitDisplay(rawFit, modelHint) {
    if (!rawFit && !modelHint) return 'coupe non précisée';
    var value = (rawFit || modelHint || '').trim();
    var low = value.toLowerCase();
    var secondaryLow = (modelHint || '').trim().toLowerCase();
    var combined = low + ' ' + secondaryLow;
    if (combined.indexOf('skinny') !== -1 || combined.indexOf('slim') !== -1) return 'Skinny';
    var droitMarkers = ['straight', 'droit', 'mom', 'boyfriend', 'girlfriend', 'regular', 'tapered'];
    for (var i = 0; i < droitMarkers.length; i++) {
      if (combined.indexOf(droitMarkers[i]) !== -1) return 'Droit';
    }
    var evaseMarkers = ['boot', 'flare', 'évas', 'evase', 'curve', 'curvy', 'wide', 'baggy', 'loose', 'relaxed', 'barrel'];
    for (var j = 0; j < evaseMarkers.length; j++) {
      if (combined.indexOf(evaseMarkers[j]) !== -1) return 'Évasé';
    }
    return value || 'coupe non précisée';
  }
  function normalizePullSize(size) {
    var raw = safeClean(size).toUpperCase();
    if (!raw) return '';
    var mainToken = raw.split('/')[0].trim();
    return mainToken || raw;
  }
  function buildHashtags(params) {
    var tokens = [];
    function add(t) { if (t && tokens.indexOf(t) === -1) tokens.push(t); }
    var brandToken = params.brand ? params.brand.toLowerCase().replace(/'/g, '') : 'levis';
    add('#' + brandToken);
    add('#jeanlevis');
    add('#jeandenim');
    if (params.gender) add('#levis' + params.gender.toLowerCase().replace(/\s/g, ''));
    if (params.model) {
      var modelMatch = params.model.match(/(\d{3})/);
      if (modelMatch) { add('#levis' + modelMatch[1]); add('#' + modelMatch[1]); }
    }
    if (params.fit) {
      var fitKey = params.fit.toLowerCase().replace(/é/g, 'e');
      var fitToken;
      if (fitKey.indexOf('evase') !== -1 || fitKey.indexOf('bootcut') !== -1 || fitKey.indexOf('flare') !== -1) {
        fitToken = 'évasé';
      } else if (fitKey.indexOf('skinny') !== -1 || fitKey.indexOf('slim') !== -1) {
        fitToken = 'skinny';
      } else if (fitKey.indexOf('droit') !== -1 || fitKey.indexOf('straight') !== -1) {
        fitToken = 'droit';
      } else {
        fitToken = fitKey.replace(/[\s\/]/g, '');
      }
      add('#' + fitToken);
      add('#jean' + fitToken);
    }
    if (params.color) add('#jean' + params.color.toLowerCase().replace(/\s/g, ''));
    // Hashtags combinés coupe + genre + taille FR (et couleur)
    if (params.fit && params.gender && params.sizeFr) {
      var fitKey = params.fit.toLowerCase().replace(/é/g, 'e');
      var fitCombined;
      if (fitKey.indexOf('evase') !== -1 || fitKey.indexOf('bootcut') !== -1 || fitKey.indexOf('flare') !== -1) {
        fitCombined = 'évasé';
      } else if (fitKey.indexOf('skinny') !== -1 || fitKey.indexOf('slim') !== -1) {
        fitCombined = 'skinny';
      } else if (fitKey.indexOf('droit') !== -1 || fitKey.indexOf('straight') !== -1) {
        fitCombined = 'droit';
      } else {
        fitCombined = fitKey.replace(/[\s\/]/g, '');
      }
      var genreToken = params.gender.toLowerCase().replace(/\s/g, '');
      add('#' + fitCombined + '_' + genreToken + '_FR' + params.sizeFr.toLowerCase());
      if (params.color) add('#' + fitCombined + '_' + genreToken + '_FR' + params.sizeFr.toLowerCase() + '_' + params.color.toLowerCase().replace(/\s/g, ''));
    }
    if (params.riseLabel) add('#' + params.riseLabel.toLowerCase().replace(/\s/g, ''));
    if (params.sizeFr) add('#fr' + params.sizeFr.toLowerCase());
    if (params.sizeUs) add('#w' + params.sizeUs.toLowerCase().replace('w', ''));
    if (params.length) add('#l' + params.length.toLowerCase().replace('l', ''));
    if (params.sizeTag) add(params.sizeTag);
    if (params.vintedAccountTag) add(params.vintedAccountTag);
    return tokens.join(' ');
  }
  function stripFooterLines(description) {
    if (!description) return '';
    var text = description.replace(/\u00A0/g, ' ');
    var lines = text.split('\n');
    var filtered = [];
    for (var i = 0; i < lines.length; i++) {
      var lowered = lines[i].trim().toLowerCase();
      if (/^[#*\-\s]*marque\s*:/.test(lowered)) continue;
      if (/^[#*\-\s]*couleur\s*:/.test(lowered)) continue;
      if (/^[#*\-\s]*taille\s*:/.test(lowered)) continue;
      if (/^[#*\-\s]*sku/.test(lowered)) continue;
      filtered.push(lines[i]);
    }
    var cleaned = filtered.join('\n');
    var final = [];
    var blankSeen = false;
    var rawLines = cleaned.split('\n');
    for (var j = 0; j < rawLines.length; j++) {
      if (!rawLines[j].trim()) {
        if (!blankSeen) { final.push(''); blankSeen = true; }
        continue;
      }
      final.push(rawLines[j].trimRight());
      blankSeen = false;
    }
    return final.join('\n').trim();
  }
  /**
   * Supprime les accents d'une chaîne (utile pour les hashtags).
   */
  function stripAccents(value) {
    if (!value) return '';
    var s = String(value);
    try {
      s = s.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    } catch (e) {
      // Fallback minimal si normalize() n'est pas dispo
      s = s
        .replace(/[àáâãäå]/g, 'a').replace(/[ÀÁÂÃÄÅ]/g, 'A')
        .replace(/[èéêë]/g, 'e').replace(/[ÈÉÊË]/g, 'E')
        .replace(/[ìíîï]/g, 'i').replace(/[ÌÍÎÏ]/g, 'I')
        .replace(/[òóôõö]/g, 'o').replace(/[ÒÓÔÕÖ]/g, 'O')
        .replace(/[ùúûü]/g, 'u').replace(/[ÙÚÛÜ]/g, 'U')
        .replace(/ç/g, 'c').replace(/Ç/g, 'C');
    }
    return s;
  }
  /**
   * Normalise une couleur pour les hashtags de navigation : retourne toujours
   * le nom de base sans variante (ex: "bleu clair", "bleu foncé", "navy" → "Bleu").
   * Utilisé exclusivement dans buildJeanNavigationTags.
   *
   * @param {string} rawColor - Couleur brute (peut contenir accents, espaces, variantes)
   * @returns {string} Token CamelCase simple (ex: "Bleu", "Noir") ou camelCaseToken en fallback.
   */
  function normalizeNavColorToken(rawColor) {
    if (!rawColor) return '';
    var base = stripAccents(safeClean(rawColor)).toLowerCase().replace(/[\s_\-]/g, '');
    var palette = [
      [['bleu', 'blue', 'marine', 'navy', 'turquoise', 'petrole', 'azur', 'cyan', 'ciel', 'indigo', 'cobalt', 'saphir'], 'Bleu'],
      [['noir', 'black', 'anthracite', 'onyx'], 'Noir'],
      [['blanc', 'white', 'ecru', 'ivoire', 'offwhite', 'creme', 'neige'], 'Blanc'],
      [['gris', 'gray', 'grey', 'chine', 'charcoal', 'ardoise', 'perle', 'argent'], 'Gris'],
      [['rouge', 'red', 'bordeaux', 'tomate', 'carmin', 'rubis', 'cerise'], 'Rouge'],
      [['rose', 'pink', 'fuchsia', 'saumon', 'corail'], 'Rose'],
      [['vert', 'green', 'kaki', 'khaki', 'olive', 'sauge', 'menthe', 'emeraude', 'bouteille'], 'Vert'],
      [['jaune', 'yellow', 'moutarde', 'citron', 'or', 'dore'], 'Jaune'],
      [['orange', 'rouille', 'brique', 'terracotta'], 'Orange'],
      [['beige', 'sable', 'sand', 'taupe', 'camel', 'nude', 'naturel'], 'Beige'],
      [['marron', 'brown', 'chocolat', 'caramel', 'cognac', 'noisette', 'cafe'], 'Marron'],
      [['violet', 'purple', 'lilas', 'lavande', 'prune', 'mauve', 'aubergine'], 'Violet']
    ];
    for (var i = 0; i < palette.length; i++) {
      var keywords = palette[i][0];
      var label = palette[i][1];
      for (var j = 0; j < keywords.length; j++) {
        if (base.indexOf(keywords[j]) !== -1) return label;
      }
    }
    return camelCaseToken(rawColor);
  }
  /**
   * Met en CamelCase chaque mot après nettoyage des accents/séparateurs.
   * "bleu clair" → "BleuClair", "Évasé" → "Evase".
   */
  function camelCaseToken(value) {
    var clean = stripAccents(safeClean(value));
    if (!clean) return '';
    return clean.split(/[\s_\-/]+/)
      .filter(Boolean)
      .map(function(w) { return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase(); })
      .join('');
  }
  /**
   * Normalise une coupe en token de hashtag : Skinny / Droit / Evase.
   * Retourne '' si la coupe ne peut pas être classée.
   */
  function normalizeFitToken(rawFit) {
    var low = stripAccents(safeClean(rawFit)).toLowerCase();
    if (!low) return '';
    if (low.indexOf('skinny') !== -1 || low.indexOf('slim') !== -1) return 'Skinny';
    var droitMarkers = ['straight', 'droit', 'mom', 'boyfriend', 'girlfriend', 'regular', 'tapered'];
    for (var i = 0; i < droitMarkers.length; i++) {
      if (low.indexOf(droitMarkers[i]) !== -1) return 'Droit';
    }
    var evaseMarkers = ['boot', 'flare', 'evas', 'curve', 'curvy', 'wide', 'baggy', 'loose', 'relaxed', 'barrel'];
    for (var j = 0; j < evaseMarkers.length; j++) {
      if (low.indexOf(evaseMarkers[j]) !== -1) return 'Evase';
    }
    return camelCaseToken(rawFit);
  }
  /**
   * Construit 2 à 3 hashtags de navigation dressing pour un jean Levi's.
   * Format : #LSM_FR{size}_{Gender}[_{Fit}[_{Color}]]
   *
   * @param {Object} params - { sizeFr, gender, fit, color }
   * @returns {string[]} Tableau de hashtags (avec le caractère #)
   */
  function buildJeanNavigationTags(params) {
    params = params || {};
    var sizeFr = safeClean(params.sizeFr);
    if (!sizeFr) return [];
    var sizeToken = 'FR' + stripAccents(sizeFr).replace(/\s/g, '').toUpperCase();
    var genderRaw = safeClean(params.gender).toLowerCase();
    var genderToken = genderRaw === 'femme' ? 'Femme' : 'Homme';
    var base = 'LSM_' + sizeToken + '_' + genderToken;
    var tags = ['#' + base];
    var fitToken = normalizeFitToken(params.fit);
    if (fitToken) {
      var withFit = base + '_' + fitToken;
      tags.push('#' + withFit);
      var colorToken = normalizeNavColorToken(params.color);
      if (colorToken) {
        tags.push('#' + withFit + '_' + colorToken);
      }
    }
    return tags;
  }
  /**
   * Construit le hashtag SKU final : forcé en MAJUSCULES, sans libellé,
   * avec préfixe d'order id (zero-paddé sur 2 chiffres) si fourni,
   * et partie numérique du SKU toujours sur 4 chiffres.
   *
   * @param {Object} params - { sku, orderId }
   * @returns {string} Hashtag SKU (ex: "#HJL0175", "#01HJL0175") ou '' si pas de SKU.
   */
  function buildJeanSkuTag(params) {
    params = params || {};
    var sku = safeClean(params.sku);
    if (!sku) return '';
    var clean = Normalizer.zeroPadSkuNumber(sku.replace(/\s/g, '').toUpperCase());
    var orderId = safeClean(params.orderId);
    if (orderId) {
      var pad = Normalizer.zeroPadOrderId(orderId);
      if (pad) clean = pad + clean;
    }
    return '#' + clean;
  }
  /**
   * Retire un éventuel hashtag SKU déjà présent en fin de titre, pour éviter
   * de le dupliquer (le SKU sera affiché seul en bas de description).
   */
  function stripSkuFromTitleLine(title) {
    if (!title) return '';
    return String(title).replace(/\s*#[A-Za-z0-9]+\s*$/, '').trim();
  }
  return {
    safeClean: safeClean,
    formatPercent: formatPercent,
    formatRiseLabel: formatRiseLabel,
    normalizeDefects: normalizeDefects,
    normalizeFitDisplay: normalizeFitDisplay,
    normalizePullSize: normalizePullSize,
    buildHashtags: buildHashtags,
    stripFooterLines: stripFooterLines,
    stripAccents: stripAccents,
    camelCaseToken: camelCaseToken,
    normalizeFitToken: normalizeFitToken,
    normalizeNavColorToken: normalizeNavColorToken,
    buildJeanNavigationTags: buildJeanNavigationTags,
    buildJeanSkuTag: buildJeanSkuTag,
    stripSkuFromTitleLine: stripSkuFromTitleLine
  };
})();
