/**
 * TitleEngine.gs - Moteur de construction des titres
 *
 * Port de domain/title_engine.py
 */

var TitleEngine = (function() {

  var TB = TitleBuilder;

  function buildTitleJeanLevis(features) {
    try {
      var brand = TB.normalizeStr(features.brand);
      var rawModel = TB.normalizeStr(features.model);
      var model = TB.sanitizeModelLabel(rawModel);
      var sizeFr = TB.normalizeStr(features.size_fr);
      var sizeUsRaw = TB.normalizeStr(features.size_us);
      var lengthRaw = TB.normalizeStr(features.length);
      var fitSource = TB.normalizeStr(features.fit);
      var fit = TB.normalizeFit(fitSource);

      if (!fit) {
        fit = TB.normalizeFit(rawModel);
      } else {
        var rawModelLow = (rawModel || '').toLowerCase();
        if (fit === 'Skinny' && rawModelLow && ['boot', 'flare', 'évas', 'evase', 'curve', 'curvy'].some(function(m) { return rawModelLow.indexOf(m) !== -1; })) {
          fit = 'Bootcut/Évasé';
        }
      }

      var color = TB.normalizeStr(features.color);
      var gender = TB.normalizeGender(TB.normalizeStr(features.gender));
      var sku = TB.normalizeStr(features.sku);
      var orderId = TB.normalizeStr(features.order_id);

      var cottonPercent = null;
      try { cottonPercent = features.cotton_percent != null ? parseInt(features.cotton_percent) : null; } catch (e) {}
      var elasPercent = null;
      try { elasPercent = features.elasthane_percent != null ? parseFloat(features.elasthane_percent) : null; } catch (e) {}

      // Rise
      var riseType = features.rise_type;
      if (!riseType) {
        riseType = TB.classifyRiseFromCm(features.rise_cm);
      } else {
        var normalized = riseType.trim().toLowerCase();
        if (normalized.indexOf('basse') !== -1 || normalized.indexOf('low') !== -1) riseType = 'low';
        else if (normalized.indexOf('haute') !== -1 || normalized.indexOf('high') !== -1) riseType = 'high';
        else if (normalized.indexOf('moy') !== -1 || normalized.indexOf('mid') !== -1) riseType = 'mid';
      }

      function getRiseLabel(raw) {
        if (!raw) return null;
        var n = String(raw).trim().toLowerCase();
        if (n.indexOf('low') !== -1 || n.indexOf('basse') !== -1 || n.indexOf('ultra') !== -1) return 'taille basse';
        if (n.indexOf('high') !== -1 || n.indexOf('haute') !== -1) return 'taille haute';
        if (n.indexOf('mid') !== -1 || n.indexOf('moy') !== -1) return 'taille moyenne';
        return null;
      }

      var riseLabel = getRiseLabel(riseType);
      if (!riseLabel) {
        riseLabel = getRiseLabel(TB.classifyRiseFromCm(features.rise_cm));
      }

      var sizeUsDisplay = null;
      if (sizeUsRaw) {
        var s = sizeUsRaw.trim().toUpperCase();
        sizeUsDisplay = s.indexOf('W') === 0 ? s : 'W' + s;
      }

      var lengthDisplay = null;
      if (lengthRaw) {
        var l = lengthRaw.trim().toUpperCase().replace('L', '');
        lengthDisplay = 'L' + l;
      }

      // Coherence FR/US
      function isFrUsCoherent(fr, us) {
        try {
          if (!fr || !us) return true;
          var frNum = parseInt(String(fr).replace(/\D/g, ''));
          var usClean = String(us).toUpperCase().replace('W', '');
          var usNum = parseInt(usClean.replace(/\D/g, ''));
          return Math.abs(frNum - (usNum + 10)) <= 1;
        } catch (e) { return true; }
      }

      var showFrInTitle = isFrUsCoherent(sizeFr, sizeUsRaw);

      var parts = ['Jean'];
      if (brand) {
        parts.push(brand.toLowerCase().split(' ').map(function(w) { return w.charAt(0).toUpperCase() + w.slice(1); }).join(' '));
      }
      if (model) parts.push(model);
      if (sizeFr && showFrInTitle) parts.push('FR' + sizeFr);
      if (sizeUsDisplay) parts.push(sizeUsDisplay);
      if (lengthDisplay) parts.push(lengthDisplay);

      if (fit && riseLabel) parts.push(fit + ' ' + riseLabel);
      else if (fit) parts.push(fit);
      else if (riseLabel) parts.push(riseLabel);

      if (cottonPercent != null && cottonPercent >= 60) parts.push(cottonPercent + '% coton');
      if (elasPercent != null && elasPercent > 2) parts.push('stretch');
      if (gender) parts.push(gender);
      if (color) parts.push(color);

      if (sku && Validator.isValidInternalSku('jean_levis', sku)) {
        var skuDisplay = orderId ? orderId + sku : sku;
        parts.push(TB.SKU_PREFIX + skuDisplay);
      }

      return TB.safeJoin(parts);
    } catch (e) {
      Logger.log('buildTitleJeanLevis error: ' + e.message);
      return 'Jean Levi\'s';
    }
  }

  function buildTitlePull(features) {
    try {
      var brand = TB.normalizeStr(features.brand);
      var isVintage = features.is_vintage || false;
      if (!brand && !isVintage) isVintage = true;

      var garmentType = TB.normalizeGarmentType(features.garment_type) || 'Pull';
      var rawGender = TB.normalizeGender(TB.normalizeStr(features.gender));
      var gender = 'femme';
      if (rawGender && rawGender.toLowerCase() !== 'femme') {
        // force femme
      } else if (rawGender) {
        gender = rawGender;
      }

      var size = TB.normalizePullSize(TB.normalizeStr(features.size));
      var neckline = TB.formatNeckline(TB.normalizeStr(features.neckline));
      var pattern = TB.normalizeStr(features.pattern);
      var material = TB.formatMaterialSegment(
        TB.normalizeStr(features.material),
        features.cotton_percent,
        features.wool_percent
      );

      var colorsInput = features.main_colors || features.colors;
      var colorsSegment = TB.formatColorsSegment(colorsInput);

      var sku = TB.normalizeStr(features.sku);
      var skuStatus = TB.normalizeStr(features.sku_status);

      var parts = [garmentType];

      if (isVintage) {
        parts.push('Vintage');
      } else if (brand) {
        var brandFormatted = brand.toLowerCase().split(' ').map(function(w) { return w.charAt(0).toUpperCase() + w.slice(1); }).join(' ');
        parts.push(brandFormatted);
        if (features.is_pima && brand.toLowerCase() === 'tommy hilfiger') {
          parts.push('Premium');
        }
      }

      if (gender) parts.push(gender);
      if (size) parts.push('taille ' + size);
      if (material) parts.push(material);
      if (colorsSegment) parts.push(colorsSegment);
      if (pattern) parts.push(pattern);
      if (neckline) parts.push(neckline);

      if (sku && skuStatus && skuStatus.toLowerCase() === 'ok') {
        parts.push(TB.SKU_PREFIX + sku);
      }

      return TB.safeJoin(parts);
    } catch (e) {
      Logger.log('buildTitlePull error: ' + e.message);
      return 'Pull Vintage';
    }
  }

  function buildTitleJacketCarhart(features) {
    try {
      var brand = TB.normalizeStr(features.brand) || 'Carhartt';
      var model = TB.normalizeStr(features.model);
      var rawSize = TB.normalizeStr(features.size);
      var sizeResult = TB.normalizeCarharttSize(rawSize);
      var size = sizeResult[0];
      var color = TB.normalizeStr(features.color);
      var gender = TB.normalizeStr(features.gender) || 'homme';
      var hasHood = features.has_hood;
      var isCamouflage = features.is_camouflage;
      var isRealtree = features.is_realtree;
      var isNewYork = features.is_new_york;
      var pattern = TB.normalizeStr(features.pattern);
      var sku = TB.normalizeStr(features.sku);
      var skuStatus = TB.normalizeStr(features.sku_status);

      var prefix = hasHood ? 'Veste à capuche Carhartt' : 'Veste Carhartt';
      var parts = [prefix];

      if (brand && brand.toLowerCase() !== 'carhartt') parts.push(brand);

      if (model) {
        var modelClean = model.trim();
        var modelLower = modelClean.toLowerCase();
        var modelSegment = modelLower.indexOf('jacket') !== -1 ? modelClean : modelClean + ' Jacket';
        if (isNewYork || modelLower.indexOf('new york') !== -1 || modelLower.endsWith(' ny')) {
          modelSegment = modelSegment.trim() + ' NY';
        }
        parts.push(modelSegment);
      } else if (isNewYork) {
        parts.push('modèle NY');
      }

      parts.push(size ? 'taille ' + size : 'taille NC');
      if (color) parts.push('couleur ' + color);
      if (isCamouflage) parts.push(isRealtree ? 'Realtree' : 'camouflage');
      else if (pattern && pattern.toLowerCase() === 'camouflage') parts.push('camouflage');
      if (gender) parts.push(gender);

      if (sku && skuStatus && skuStatus.toLowerCase() === 'ok') {
        parts.push(TB.SKU_PREFIX + sku);
      }

      return TB.safeJoin(parts);
    } catch (e) {
      Logger.log('buildTitleJacketCarhart error: ' + e.message);
      return 'Veste Carhartt';
    }
  }

  /**
   * Point d'entree unique pour construire les titres.
   */
  function buildTitle(profileName, features) {
    try {
      if (profileName === 'jean_levis') return buildTitleJeanLevis(features);
      if (profileName === 'pull') return buildTitlePull(features);
      if (profileName === 'jacket_carhart') return buildTitleJacketCarhart(features);

      return String(features.title || '').trim();
    } catch (e) {
      Logger.log('buildTitle error: ' + e.message);
      return String(features.title || '').trim();
    }
  }

  return {
    buildTitle: buildTitle,
    buildTitleJeanLevis: buildTitleJeanLevis,
    buildTitlePull: buildTitlePull,
    buildTitleJacketCarhart: buildTitleJacketCarhart
  };

})();
