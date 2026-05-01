/**
 * TitleEngine.gs - Moteur de construction des titres
 *
 * Port de domain/title_engine.py
 */
var TitleEngine = (function() {
  function buildTitleJeanLevis(features) {
    try {
      var brand = TitleBuilder.normalizeStr(features.brand);
      var rawModel = TitleBuilder.normalizeStr(features.model);
      var model = TitleBuilder.sanitizeModelLabel(rawModel);
      var sizeFr = TitleBuilder.normalizeStr(features.size_fr);
      var sizeUsRaw = TitleBuilder.normalizeStr(features.size_us);
      var lengthRaw = TitleBuilder.normalizeStr(features.length);
      var fitSource = TitleBuilder.normalizeStr(features.fit);
      var fit = TitleBuilder.normalizeFit(fitSource);
      if (!fit) {
        fit = TitleBuilder.normalizeFit(rawModel);
      } else {
        var rawModelLow = (rawModel || '').toLowerCase();
        if (fit === 'Skinny' && rawModelLow && ['boot', 'flare', 'évas', 'evase', 'curve', 'curvy', 'wide', 'baggy', 'loose', 'relaxed', 'barrel'].some(function(m) { return rawModelLow.indexOf(m) !== -1; })) {
          fit = 'Évasé';
        }
      }
      var color = TitleBuilder.normalizeStr(features.color);
      var gender = TitleBuilder.normalizeGender(TitleBuilder.normalizeStr(features.gender));
      var sku = TitleBuilder.normalizeStr(features.sku);
      var orderId = TitleBuilder.normalizeStr(features.order_id);
      var cottonPercent = null;
      try { cottonPercent = features.cotton_percent != null ? parseInt(features.cotton_percent) : null; } catch (e) {}
      var elasPercent = null;
      try { elasPercent = features.elasthane_percent != null ? parseFloat(features.elasthane_percent) : null; } catch (e) {}
      // Stretch: si correction manuelle fournie, on la respecte ;
      // sinon auto : elasthane >= 3% OU viscose presente dans la composition
      var compositionMaterials = features.composition_materials || [];
      var hasViscose = compositionMaterials.some(function(m) {
        return m && m.toLowerCase() === 'viscose';
      });
      var isStretch;
      if (features.is_stretch === true || features.is_stretch === 'true' || features.is_stretch === '1') {
        isStretch = true;
      } else if (features.is_stretch === false || features.is_stretch === 'false' || features.is_stretch === '0') {
        isStretch = false;
      } else {
        isStretch = hasViscose || (elasPercent != null && elasPercent >= 3);
      }
      // Rise (centralise via TitleBuilder.normalizeRiseType)
      var riseNorm = TitleBuilder.normalizeRiseType(features.rise_type, features.rise_cm);
      var riseLabel = null;
      if (riseNorm === 'low') riseLabel = 'taille basse';
      else if (riseNorm === 'high') riseLabel = 'taille haute';
      else if (riseNorm === 'mid') riseLabel = 'taille moyenne';
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
      var isPremium = features.is_premium || false;
      var parts = ['Jean'];
      if (brand) {
        parts.push(brand.toLowerCase().split(' ').map(function(w) { return w.charAt(0).toUpperCase() + w.slice(1); }).join(' '));
      }
      if (isPremium) parts.push('Premium');
      if (model && /^\d+$/.test(model)) parts.push(model);
      if (sizeFr && showFrInTitle) parts.push('FR' + sizeFr);
      if (sizeUsDisplay) parts.push(sizeUsDisplay);
      if (lengthDisplay) parts.push(lengthDisplay);
      var fitOriginal = TitleBuilder.normalizeStr(features.fit_original);
      var fitDisplay = TitleBuilder.formatFitDisplay(fitOriginal, fit);
      if (fitDisplay && riseLabel) parts.push(fitDisplay + ' ' + riseLabel);
      else if (fitDisplay) parts.push(fitDisplay);
      else if (riseLabel) parts.push(riseLabel);
      if (cottonPercent != null && cottonPercent >= 60) parts.push(cottonPercent + '% coton');
      if (isStretch) parts.push('stretch');
      if (gender) parts.push(gender);
      if (color) parts.push(color);
      if (sku && Validator.isValidInternalSku('jean_levis', sku)) {
        var skuPad = orderId ? Normalizer.zeroPadOrderId(orderId) : '';
        var skuDisplay = skuPad ? skuPad + sku : sku;
        parts.push(TitleBuilder.SKU_PREFIX + skuDisplay);
      }
      return TitleBuilder.safeJoin(parts);
    } catch (e) {
      Logger.log('buildTitleJeanLevis error: ' + e.message);
      return 'Jean Levi\'s';
    }
  }
  function buildTitlePull(features) {
    try {
      var brand = TitleBuilder.normalizeStr(features.brand);
      var isVintage = features.is_vintage || false;
      if (!brand && !isVintage) isVintage = true;
      var garmentType = TitleBuilder.normalizeGarmentType(features.garment_type) || 'Pull';
      var rawGender = TitleBuilder.normalizeGender(TitleBuilder.normalizeStr(features.gender));
      var gender = 'femme';
      if (rawGender && rawGender.toLowerCase() !== 'femme') {
        // force femme
      } else if (rawGender) {
        gender = rawGender;
      }
      var size = TitleBuilder.normalizePullSize(TitleBuilder.normalizeStr(features.size));
      var neckline = TitleBuilder.formatNeckline(TitleBuilder.normalizeStr(features.neckline));
      var pattern = TitleBuilder.normalizeStr(features.pattern);
      var material = TitleBuilder.formatMaterialSegment(
        TitleBuilder.normalizeStr(features.material),
        features.cotton_percent,
        features.wool_percent
      );
      var colorsInput = features.main_colors || features.colors;
      var colorsSegment = TitleBuilder.formatColorsSegment(colorsInput);
      var sku = TitleBuilder.normalizeStr(features.sku);
      var skuStatus = TitleBuilder.normalizeStr(features.sku_status);
      var parts = [garmentType];
      var isPremium = features.is_premium || false;
      if (isVintage) {
        parts.push('Vintage');
      } else if (brand) {
        var brandFormatted = brand.toLowerCase().split(' ').map(function(w) { return w.charAt(0).toUpperCase() + w.slice(1); }).join(' ');
        parts.push(brandFormatted);
        if (isPremium) parts.push('Premium');
      }
      if (gender) parts.push(gender);
      if (size) parts.push('taille ' + size);
      if (material) parts.push(material);
      if (colorsSegment) parts.push(colorsSegment);
      if (pattern) parts.push(pattern);
      if (neckline) parts.push(neckline);
      if (sku && skuStatus && skuStatus.toLowerCase() === 'ok') {
        parts.push(TitleBuilder.SKU_PREFIX + sku);
      }
      return TitleBuilder.safeJoin(parts);
    } catch (e) {
      Logger.log('buildTitlePull error: ' + e.message);
      return 'Pull Vintage';
    }
  }
  function buildTitleJacketCarhart(features) {
    try {
      var brand = TitleBuilder.normalizeStr(features.brand) || 'Carhartt';
      var model = TitleBuilder.normalizeStr(features.model);
      var rawSize = TitleBuilder.normalizeStr(features.size);
      var sizeResult = TitleBuilder.normalizeCarharttSize(rawSize);
      var size = sizeResult[0];
      var color = TitleBuilder.normalizeStr(features.color);
      var gender = TitleBuilder.normalizeStr(features.gender) || 'homme';
      var hasHood = features.has_hood;
      var isCamouflage = features.is_camouflage;
      var isRealtree = features.is_realtree;
      var isNewYork = features.is_new_york;
      var pattern = TitleBuilder.normalizeStr(features.pattern);
      var sku = TitleBuilder.normalizeStr(features.sku);
      var skuStatus = TitleBuilder.normalizeStr(features.sku_status);
      var isPremium = features.is_premium || false;
      var prefix = hasHood ? 'Veste à capuche Carhartt' : 'Veste Carhartt';
      var parts = [prefix];
      if (isPremium) parts.push('Premium');
      if (brand && brand.toLowerCase() !== 'carhartt') parts.push(brand);
      if (model && /^\d+$/.test(model)) {
        parts.push(model);
      } else if (isNewYork) {
        parts.push('modèle NY');
      }
      parts.push(size ? 'taille ' + size : 'taille NC');
      if (color) parts.push('couleur ' + color);
      if (isCamouflage) parts.push(isRealtree ? 'Realtree' : 'camouflage');
      else if (pattern && pattern.toLowerCase() === 'camouflage') parts.push('camouflage');
      if (gender) parts.push(gender);
      if (sku && skuStatus && skuStatus.toLowerCase() === 'ok') {
        parts.push(TitleBuilder.SKU_PREFIX + sku);
      }
      return TitleBuilder.safeJoin(parts);
    } catch (e) {
      Logger.log('buildTitleJacketCarhart error: ' + e.message);
      return 'Veste Carhartt';
    }
  }
  function buildTitleShortCarhart(features) {
    try {
      var brand = TitleBuilder.normalizeStr(features.brand) || 'Carhartt';
      var rawSize = TitleBuilder.normalizeStr(features.size);
      var sizeResult = TitleBuilder.normalizeCarharttSize(rawSize);
      var size = sizeResult[0];
      var color = TitleBuilder.normalizeStr(features.color);
      var gender = TitleBuilder.normalizeStr(features.gender) || 'homme';
      var pattern = TitleBuilder.normalizeStr(features.pattern);
      var sku = TitleBuilder.normalizeStr(features.sku);
      var skuStatus = TitleBuilder.normalizeStr(features.sku_status);
      var isPremium = features.is_premium || false;
      var parts = ['Short Carhartt'];
      if (isPremium) parts.push('Premium');
      if (brand && brand.toLowerCase() !== 'carhartt') parts.push(brand);
      parts.push(size ? 'taille ' + size : 'taille NC');
      if (color) parts.push('couleur ' + color);
      if (pattern && pattern.toLowerCase() === 'camouflage') parts.push('camouflage');
      if (gender) parts.push(gender);
      if (sku && skuStatus && skuStatus.toLowerCase() === 'ok') {
        parts.push(TitleBuilder.SKU_PREFIX + sku);
      }
      return TitleBuilder.safeJoin(parts);
    } catch (e) {
      Logger.log('buildTitleShortCarhart error: ' + e.message);
      return 'Short Carhartt';
    }
  }
  function buildTitleShortAdidas(features) {
    try {
      var brand = TitleBuilder.normalizeStr(features.brand) || 'Adidas';
      var model = TitleBuilder.normalizeStr(features.model);
      var rawSize = TitleBuilder.normalizeStr(features.size);
      var sizeResult = TitleBuilder.normalizeCarharttSize(rawSize);
      var size = sizeResult[0];
      var color = TitleBuilder.normalizeStr(features.color);
      var gender = TitleBuilder.normalizeStr(features.gender) || 'homme';
      var technology = TitleBuilder.normalizeStr(features.technology);
      var pattern = TitleBuilder.normalizeStr(features.pattern);
      var sku = TitleBuilder.normalizeStr(features.sku);
      var skuStatus = TitleBuilder.normalizeStr(features.sku_status);
      var isPremium = features.is_premium || false;
      var brandLabel = isPremium ? brand + ' Originals' : brand;
      var parts = ['Short ' + brandLabel];
      if (model) parts.push(model);
      parts.push(size ? 'taille ' + size : 'taille NC');
      if (color) parts.push('couleur ' + color);
      if (technology) parts.push(technology);
      if (pattern && pattern.toLowerCase() !== 'uni') parts.push(pattern);
      if (gender) parts.push(gender);
      if (sku && skuStatus && skuStatus.toLowerCase() === 'ok') {
        parts.push(TitleBuilder.SKU_PREFIX + sku);
      }
      return TitleBuilder.safeJoin(parts);
    } catch (e) {
      Logger.log('buildTitleShortAdidas error: ' + e.message);
      return 'Short Adidas';
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
      if (profileName === 'short_carhart') return buildTitleShortCarhart(features);
      if (profileName === 'short_adidas') return buildTitleShortAdidas(features);
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
    buildTitleJacketCarhart: buildTitleJacketCarhart,
    buildTitleShortCarhart: buildTitleShortCarhart,
    buildTitleShortAdidas: buildTitleShortAdidas
  };
})();