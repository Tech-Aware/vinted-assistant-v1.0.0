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
  return {
    safeClean: safeClean,
    formatPercent: formatPercent,
    formatRiseLabel: formatRiseLabel,
    normalizeDefects: normalizeDefects,
    normalizeFitDisplay: normalizeFitDisplay,
    normalizePullSize: normalizePullSize,
    buildHashtags: buildHashtags,
    stripFooterLines: stripFooterLines
  };
})();
