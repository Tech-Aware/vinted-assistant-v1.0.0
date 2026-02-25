/**
 * TitleBuilder.gs - Fonctions utilitaires pour la construction des titres
 *
 * Port de domain/title_builder.py
 */

var TitleBuilder = (function() {

  var SKU_PREFIX = '- ';

  function normalizeStr(value) {
    if (value == null) return null;
    var s = String(value).trim();
    return s || null;
  }

  function normalizeFit(value) {
    if (!value) return null;
    var v = value.trim().toLowerCase();

    if (v.indexOf('slim') !== -1 || v.indexOf('skinny') !== -1) return 'Skinny';
    if (v.indexOf('straight') !== -1 || v.indexOf('droit') !== -1) return 'Straight/Droit';
    if (v.indexOf('bootcut') !== -1 || v.indexOf('flare') !== -1 ||
        v.indexOf('évasé') !== -1 || v.indexOf('evase') !== -1 ||
        v.indexOf('curve') !== -1 || v.indexOf('curvy') !== -1) {
      return 'Bootcut/Évasé';
    }
    return value.trim();
  }

  function sanitizeModelLabel(value) {
    if (!value) return null;
    var raw = value.trim();
    var fitMarkers = ['skinny', 'slim', 'straight', 'droit', 'boot', 'flare', 'évas', 'evase', 'curve', 'curvy'];
    var dropMarkers = ['demi', 'cut'];
    var tokens = raw.replace(/[\/\-]/g, ' ').split(/\s+/);
    var cleaned = [];

    for (var i = 0; i < tokens.length; i++) {
      var tokenLow = tokens[i].toLowerCase();
      var isFit = fitMarkers.some(function(m) { return tokenLow.indexOf(m) !== -1; });
      var isDrop = dropMarkers.indexOf(tokenLow) !== -1;
      if (!isFit && !isDrop) {
        cleaned.push(tokens[i]);
      }
    }

    var result = cleaned.join(' ').trim();
    return result || null;
  }

  function normalizeGender(value) {
    if (!value) return null;
    var v = value.trim().toLowerCase();
    var female = ['f', 'femme', 'female', 'woman', 'women', 'girl'];
    var male = ['h', 'homme', 'male', 'man', 'men', 'boy'];

    if (female.indexOf(v) !== -1 || v.indexOf('fem') === 0 || v.indexOf('wom') === 0) return 'femme';
    if (male.indexOf(v) !== -1 || v.indexOf('hom') === 0 || v.indexOf('masc') === 0 || v.indexOf('men') === 0) return 'homme';
    return value.trim();
  }

  function safeJoin(parts) {
    return parts.filter(function(p) { return p && p.trim(); }).join(' ');
  }

  function normalizeGarmentType(value) {
    if (!value) return null;
    var low = value.trim().toLowerCase();
    if (low.indexOf('gilet') !== -1 || low.indexOf('cardi') !== -1) return 'Gilet';
    return 'Pull';
  }

  function formatColorsSegment(value) {
    if (!value) return null;
    var colors = [];
    if (Array.isArray(value)) {
      colors = value;
    } else {
      colors = String(value).replace(/\//g, ',').split(',');
    }

    var simplified = [];
    var seen = {};
    for (var i = 0; i < colors.length; i++) {
      var c = String(colors[i]).trim();
      if (!c) continue;
      var s = simplifyColorName_(c.toLowerCase());
      if (!s || seen[s]) continue;
      seen[s] = true;
      simplified.push(s);
    }

    if (simplified.length === 0) return null;
    if (simplified.length > 1) {
      simplified = simplified.filter(function(c) { return c !== 'multicolore'; });
      if (simplified.length === 0) simplified = ['multicolore'];
    }
    return simplified.slice(0, 2).join(', ');
  }

  function simplifyColorName_(color) {
    if (!color) return null;
    var base = color.trim().toLowerCase();
    var palettes = [
      [['bleu marine', 'navy', 'navy blue', 'marine'], 'marine'],
      [['bleu', 'blue', 'turquoise', 'petrole', 'pétrole', 'azur', 'cyan', 'ciel'], 'bleu'],
      [['noir', 'black'], 'noir'],
      [['blanc', 'white', 'ecru', 'écru', 'off-white', 'ivoire'], 'blanc'],
      [['gris', 'gray', 'grey', 'chiné', 'charcoal'], 'gris'],
      [['rouge', 'red', 'bordeaux'], 'rouge'],
      [['rose', 'pink', 'fuchsia'], 'rose'],
      [['vert', 'green', 'kaki', 'khaki', 'olive'], 'vert'],
      [['jaune', 'yellow', 'moutarde'], 'jaune'],
      [['orange', 'corail', 'coral'], 'orange'],
      [['beige', 'sable', 'sand', 'taupe'], 'beige'],
      [['marron', 'brown', 'chocolat'], 'marron'],
      [['violet', 'purple', 'lilas', 'lavande', 'prune'], 'violet']
    ];

    for (var i = 0; i < palettes.length; i++) {
      var keywords = palettes[i][0];
      var label = palettes[i][1];
      for (var j = 0; j < keywords.length; j++) {
        if (base.indexOf(keywords[j]) !== -1) return label;
      }
    }
    return base;
  }

  function formatMaterialSegment(material, cottonPercent, woolPercent) {
    var cottonValue = null;
    var woolValue = null;

    try { cottonValue = cottonPercent != null ? parseInt(cottonPercent) : null; } catch (e) {}
    try { woolValue = woolPercent != null ? parseInt(woolPercent) : null; } catch (e) {}

    var materialLabel = (material || '').trim().toLowerCase();
    var priorityMapping = {
      'cachemire': 'cachemire', 'cashmere': 'cachemire',
      'angora': 'angora', 'laine': 'laine', 'wool': 'laine',
      'lin': 'lin', 'linen': 'lin', 'satin': 'satin'
    };

    if (woolValue != null && woolValue > 0) return 'laine';

    for (var keyword in priorityMapping) {
      if (materialLabel.indexOf(keyword) !== -1) return priorityMapping[keyword];
    }

    if (cottonValue != null) {
      if (cottonValue >= 60) return cottonValue + '% coton';
      return 'coton';
    }

    if (materialLabel.indexOf('coton') !== -1 || materialLabel.indexOf('cotton') !== -1) {
      return 'coton';
    }

    return null;
  }

  function formatNeckline(neckline) {
    if (!neckline) return null;
    var neck = neckline.trim();
    if (neck.toLowerCase().indexOf('col') === 0) {
      var parts = neck.split(' ');
      neck = parts.length > 1 ? parts.slice(1).join(' ') : '';
    }
    neck = neck.trim();
    if (!neck) return null;
    return 'col ' + neck;
  }

  function normalizePullSize(value) {
    if (!value) return null;
    var raw = String(value).trim().toUpperCase().replace(/\s/g, '');
    if (raw.indexOf('/') !== -1) raw = raw.split('/')[0];
    if (raw.endsWith('P')) raw = raw.slice(0, -1);

    var numericMatch = raw.match(/^(\d+)X$/);
    if (numericMatch) {
      var count = parseInt(numericMatch[1]) + 1;
      return 'X'.repeat(count) + 'L';
    }

    if (raw === 'M') return 'M';

    var match = raw.match(/^(X{0,5})(S|L)$/);
    if (match) return match[1] + match[2];

    var allowed = ['XS', 'S', 'L', 'XL', 'XXL', 'XXXL', 'XXXXL', 'XXXS', 'XXXXS'];
    if (allowed.indexOf(raw) !== -1) return raw;

    return raw || null;
  }

  function normalizeCarharttSize(value) {
    var raw = normalizeStr(value);
    if (!raw) return ['NC', 'nc'];

    var low = raw.toLowerCase();
    var base = raw.toUpperCase();
    var sizeMap = {
      'xs': 'XS', 'extra small': 'XS', 'x-small': 'XS',
      'small': 'S', 's': 'S',
      'medium': 'M', 'm': 'M',
      'large': 'L', 'l': 'L',
      'x-large': 'XL', 'xl': 'XL',
      'xxl': 'XXL', '2xl': 'XXL',
      'xxxl': 'XXXL', '3xl': 'XXXL'
    };

    for (var marker in sizeMap) {
      if (low.indexOf(marker) !== -1) {
        base = sizeMap[marker];
        break;
      }
    }

    var token = base.toLowerCase().replace(/\s/g, '') || 'nc';
    return [base, token];
  }

  function classifyRiseFromCm(riseCm) {
    if (riseCm == null) return null;
    var v;
    try { v = parseFloat(riseCm); } catch (e) { return null; }
    if (isNaN(v)) return null;

    if (v < 20) return 'ultra_low';
    if (v < 23) return 'low';
    if (v < 26) return 'mid';
    return 'high';
  }

  return {
    SKU_PREFIX: SKU_PREFIX,
    normalizeStr: normalizeStr,
    normalizeFit: normalizeFit,
    sanitizeModelLabel: sanitizeModelLabel,
    normalizeGender: normalizeGender,
    safeJoin: safeJoin,
    normalizeGarmentType: normalizeGarmentType,
    formatColorsSegment: formatColorsSegment,
    formatMaterialSegment: formatMaterialSegment,
    formatNeckline: formatNeckline,
    normalizePullSize: normalizePullSize,
    normalizeCarharttSize: normalizeCarharttSize,
    classifyRiseFromCm: classifyRiseFromCm
  };

})();
