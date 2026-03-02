/**
 * Normalizer.gs - Normalisation et post-traitement
 *
 * Port de domain/normalizer.py + domain/normalizers/
 */

var Normalizer = (function() {

  // =====================================================
  // Normalisation de base
  // =====================================================

  function coerceProfileName(name) {
    if (!name) return null;
    var value = String(name).trim().toLowerCase();
    var allowed = ['jean_levis', 'pull', 'jacket_carhart'];
    return allowed.indexOf(value) !== -1 ? value : null;
  }

  function normalizeSizes(features) {
    var raw = features.size_us;
    if (!raw) return features;

    var text = String(raw).toUpperCase().replace(/\s/g, '');
    var wMatch = text.match(/W(\d+)/);
    var lMatch = text.match(/L(\d+)/);

    if (wMatch) features.size_us = 'W' + wMatch[1];
    if (lMatch && !features.length) features.length = 'L' + lMatch[1];

    return features;
  }

  /**
   * Capitalize un nom de matiere sans le normaliser.
   * Garde le terme reel de l'etiquette (ex: "spandex" -> "Spandex").
   */
  function capitalizeMaterial(raw) {
    if (!raw) return null;
    var trimmed = raw.trim();
    if (!trimmed) return null;
    return trimmed.charAt(0).toUpperCase() + trimmed.slice(1).toLowerCase();
  }

  /**
   * Verifie si un materiau est de type elastique (stretch).
   */
  function isElasticMaterial(name) {
    if (!name) return false;
    var low = name.toLowerCase();
    return low === 'spandex' || low === 'élasthanne' || low === 'elasthanne' ||
           low === 'elastane' || low === 'lycra';
  }

  /**
   * Zero-pad un orderId sur 2 chiffres.
   */
  function zeroPadOrderId(orderId) {
    if (!orderId) return '';
    var num = String(orderId).replace(/\D/g, '');
    if (!num) return '';
    return ('00' + num).slice(-2);
  }

  // =====================================================
  // Premium Levi's detection
  // =====================================================

  var PREMIUM_LEVIS_MODELS = [
    '501', '505', '517', '550', '560', '569',
    'vintage', 'big e', 'orange tab', 'red tab',
    'made in usa', 'selvedge', 'lvc', 'levis vintage clothing'
  ];

  function isPremiumLevisModel(model) {
    if (!model) return false;
    var low = String(model).toLowerCase().trim();
    for (var i = 0; i < PREMIUM_LEVIS_MODELS.length; i++) {
      if (low.indexOf(PREMIUM_LEVIS_MODELS[i]) !== -1) return true;
    }
    return false;
  }

  // =====================================================
  // Feature builders par profil
  // =====================================================

  function buildFeaturesForJeanLevis(aiData, uiData) {
    uiData = uiData || {};
    var rawFeatures = aiData.features || {};
    var title = aiData.title || '';
    var description = aiData.description || '';
    var fullText = title + ' ' + description;

    var brand = rawFeatures.brand || aiData.brand;
    var model = rawFeatures.model || aiData.model;
    if (!model) model = TextExtractors.extractModelFromText(fullText);

    // Fit : priorite UI > IA > texte
    var fit;
    var uiFit = uiData.fit;
    if (uiFit) {
      var uiFitLow = uiFit.toLowerCase();
      if (uiFitLow === 'droite') fit = 'Straight/Droit';
      else if (uiFitLow === 'evasee') fit = 'Bootcut/Évasé';
      else if (uiFitLow === 'skinny') fit = 'Skinny';
      else fit = TextExtractors.normalizeFitLabel(uiFit);
    } else {
      fit = rawFeatures.fit || aiData.fit;
      fit = TextExtractors.normalizeFitLabel(fit);
      if (!fit) fit = TextExtractors.extractFitFromText(fullText);
    }

    var color = rawFeatures.color || aiData.color;
    if (!color) color = TextExtractors.extractColorFromText(fullText);

    var sizeFr = uiData.size_fr || rawFeatures.size_fr || aiData.size_fr;
    var sizeUs = uiData.size_us || rawFeatures.size_us || aiData.size_us;
    var length = uiData.length || rawFeatures.length || aiData.length;

    if (!sizeUs || !length) {
      var inferred = TextExtractors.extractSizesFromText(fullText);
      if (!sizeUs && inferred[0]) sizeUs = inferred[0];
      if (!length && inferred[1]) length = inferred[1];
    }

    var cottonPercent = rawFeatures.cotton_percent || aiData.cotton_percent;
    var elasthanePercent = rawFeatures.elasthane_percent || aiData.elasthane_percent;

    // Composition : depuis l'IA, noms reels de l'etiquette (pas de normalisation)
    var compositionMaterials = rawFeatures.composition_materials || aiData.composition_materials;
    if (compositionMaterials && Array.isArray(compositionMaterials)) {
      compositionMaterials = compositionMaterials.map(capitalizeMaterial).filter(Boolean);
    }
    // Fallback: construire depuis les pourcentages si l'IA n'a pas detecte
    if (!compositionMaterials || compositionMaterials.length === 0) {
      compositionMaterials = [];
      if (cottonPercent) compositionMaterials.push('Coton');
      if (elasthanePercent) {
        // Utiliser le terme generique si on n'a que le %
        compositionMaterials.push('Élasthanne');
      }
    }

    // Material string pour le log
    var material = compositionMaterials.length > 0 ? compositionMaterials.join(', ') : null;

    // Rise
    var riseCm = rawFeatures.rise_cm || aiData.rise_cm;
    var riseType;
    var uiRise = uiData.rise_type;
    if (uiRise) {
      var uiRiseLow = uiRise.toLowerCase();
      if (uiRiseLow === 'haute') riseType = 'high';
      else if (uiRiseLow === 'moyenne') riseType = 'mid';
      else if (uiRiseLow === 'basse') riseType = 'low';
      else riseType = uiRise;
    } else {
      riseType = rawFeatures.rise_type || aiData.rise_type;
    }

    // SKU
    var rawSku = uiData.sku || rawFeatures.sku || aiData.sku;
    var sku = TextExtractors.normalizeSkuValue(rawSku);
    var skuStatus = sku ? 'ok' : (rawSku ? 'invalid' : 'missing');

    // Genre
    var aiGender = uiData.gender || rawFeatures.gender || aiData.gender;
    var skuGender = TextExtractors.extractGenderFromSkuPrefix(sku);
    var gender;
    if (skuGender && aiGender) {
      gender = (aiGender.trim().toLowerCase() !== skuGender) ? skuGender : aiGender;
    } else {
      gender = skuGender || aiGender || null;
    }

    var orderId = uiData.order_id;

    // Condition
    var condition = uiData.condition || rawFeatures.condition || aiData.condition || 'tres bon etat';

    // Premium: IA > detection par modele
    var isPremium = rawFeatures.is_premium || false;
    if (!isPremium && model) {
      isPremium = isPremiumLevisModel(model);
    }

    var features = {
      brand: brand,
      model: model,
      fit: fit,
      color: color,
      size_fr: sizeFr,
      size_us: sizeUs,
      length: length,
      cotton_percent: cottonPercent,
      elasthane_percent: elasthanePercent,
      composition_materials: compositionMaterials,
      rise_type: riseType,
      rise_cm: riseCm,
      gender: gender,
      is_premium: isPremium,
      sku: sku,
      sku_status: skuStatus,
      order_id: orderId,
      material: material,
      condition: condition
    };

    return normalizeSizes(features);
  }

  function buildFeaturesForPull(aiData, uiData) {
    uiData = uiData || {};
    var rawFeatures = aiData.features || {};

    var measurementMode = uiData.measurement_mode || 'etiquette';
    var brand = rawFeatures.brand || aiData.brand;
    var garmentType = rawFeatures.garment_type || aiData.style;
    var neckline = rawFeatures.neckline || aiData.neckline;
    var pattern = rawFeatures.pattern || aiData.pattern;
    var material = rawFeatures.material;
    var cottonPercent = rawFeatures.cotton_percent;
    var woolPercent = rawFeatures.wool_percent;
    var mainColors = rawFeatures.main_colors || rawFeatures.colors;
    var gender = uiData.gender || rawFeatures.gender;

    // Taille
    var sizeFromUi = uiData.size;
    var sizeLabel = rawFeatures.size || aiData.size;
    var sizeEstimated = rawFeatures.size_estimated;
    var sizeSource = rawFeatures.size_source;

    var size = null;
    var computedSizeSource = null;

    if (measurementMode === 'mesures') {
      if (sizeFromUi) { size = sizeFromUi; computedSizeSource = 'estimated'; }
      else if (sizeEstimated) { size = sizeEstimated; computedSizeSource = 'estimated'; }
      else if (sizeLabel) { size = sizeLabel; computedSizeSource = sizeSource || 'estimated'; }
    } else {
      size = sizeFromUi || sizeLabel;
      computedSizeSource = sizeSource || (size ? 'label' : null);
    }

    // SKU
    var skuFromUi = uiData.sku;
    var skuFromAi = rawFeatures.sku || aiData.sku;
    var skuStatusRaw = rawFeatures.sku_status || aiData.sku_status;
    var skuStatus = skuStatusRaw != null ? String(skuStatusRaw).trim().toLowerCase() : null;

    var sku;
    if (skuFromUi != null) {
      sku = skuFromUi;
      if (!skuStatus || skuStatus !== 'ok') skuStatus = 'ok';
    } else if (skuFromAi && skuStatus === 'ok' && /^[A-Za-z]{2,}\s*[0-9]+$/.test(skuFromAi.replace(/\s+/g, ''))) {
      sku = skuFromAi.replace(/\s+/g, '');
    } else {
      sku = null;
      skuStatus = skuFromAi ? 'invalid' : 'missing';
    }

    // Normalisation marque
    var normalizedBrand = normalizePullBrand(brand);
    var isVintage = normalizedBrand == null;

    var orderId = uiData.order_id;
    var condition = uiData.condition || rawFeatures.condition || 'tres bon etat';

    // Pima cotton detection
    var descText = (aiData.description || '').toLowerCase();
    var materialText = (rawFeatures.material || '').toLowerCase();
    var isPima = descText.indexOf('pima coton') !== -1 || descText.indexOf('pima cotton') !== -1 ||
                 materialText.indexOf('pima coton') !== -1 || materialText.indexOf('pima cotton') !== -1;

    // Premium: IA > is_pima
    var isPremium = rawFeatures.is_premium || isPima || false;

    return {
      brand: normalizedBrand,
      is_vintage: isVintage,
      garment_type: garmentType,
      neckline: neckline,
      pattern: pattern,
      material: material,
      cotton_percent: cottonPercent,
      wool_percent: woolPercent,
      main_colors: mainColors,
      gender: gender,
      size: size,
      size_estimated: sizeEstimated,
      size_source: computedSizeSource,
      measurement_mode: measurementMode,
      sku: sku,
      sku_status: skuStatus,
      order_id: orderId,
      is_pima: isPima,
      is_premium: isPremium,
      condition: condition
    };
  }

  function buildFeaturesForJacketCarhart(aiData, uiData) {
    uiData = uiData || {};
    var rawFeatures = aiData.features || {};
    var title = aiData.title || '';
    var description = aiData.description || '';
    var fullText = (title + ' ' + description).trim();

    var brand = rawFeatures.brand || aiData.brand || 'Carhartt';
    var model = rawFeatures.model || aiData.model;
    model = TextExtractors.normalizeCarharttModel(model, fullText);
    if (!model) model = TextExtractors.extractCarharttModelFromText(fullText);

    var size = uiData.size_fr || uiData.size || rawFeatures.size || aiData.size;
    var color = rawFeatures.color || aiData.color;
    if (!color) color = TextExtractors.extractColorFromText(fullText);

    var gender = uiData.gender || rawFeatures.gender || aiData.gender;
    var hasHood = rawFeatures.has_hood;
    if (hasHood == null) hasHood = TextExtractors.detectFlagFromText(fullText, ['capuche', 'hood']);
    var pattern = rawFeatures.pattern || aiData.pattern;

    var lining = rawFeatures.lining || aiData.lining;
    if (!lining) lining = TextExtractors.extractLiningFromText(fullText);
    var closure = rawFeatures.closure || aiData.closure;
    var patchMaterial = rawFeatures.patch_material || aiData.patch_material;
    var collar = rawFeatures.collar || aiData.collar;
    var zipMaterial = rawFeatures.zip_material || aiData.zip_material;
    var originCountry = rawFeatures.origin_country || aiData.origin_country;
    if (!originCountry) originCountry = TextExtractors.extractOriginCountryFromText(fullText);

    var exterior = rawFeatures.exterior || aiData.exterior;
    var sleeveLining = rawFeatures.sleeve_lining || aiData.sleeve_lining;

    var isCamouflage = rawFeatures.is_camouflage;
    if (isCamouflage == null && pattern) isCamouflage = pattern.toLowerCase() === 'camouflage';
    if (isCamouflage == null) isCamouflage = TextExtractors.detectFlagFromText(fullText, ['camouflage']);

    var isRealtree = rawFeatures.is_realtree;
    if (isRealtree == null) isRealtree = TextExtractors.detectFlagFromText(fullText, ['realtree']);

    var isNewYork = rawFeatures.is_new_york;
    if (isNewYork == null) isNewYork = TextExtractors.detectFlagFromText(fullText, ['new york', ' ny']);

    // SKU (Carhartt JCR)
    var skuFromUi = uiData.sku;
    var skuFromAi = rawFeatures.sku || aiData.sku;
    var skuStatusRaw = rawFeatures.sku_status || aiData.sku_status;
    var skuStatus = skuStatusRaw != null ? String(skuStatusRaw).trim().toLowerCase() : null;

    var sku = null;
    if (skuFromUi) {
      sku = TextExtractors.normalizeJcrSku(skuFromUi);
      skuStatus = sku ? 'ok' : 'low_confidence';
    } else {
      var normalizedAiSku = TextExtractors.normalizeJcrSku(skuFromAi);
      if (normalizedAiSku) { sku = normalizedAiSku; skuStatus = 'ok'; }
      else { sku = null; skuStatus = 'missing'; }
    }

    var orderId = uiData.order_id;
    var condition = uiData.condition || rawFeatures.condition || 'tres bon etat';

    // Premium: IA > detection WIP/vintage/Made in USA
    var isPremium = rawFeatures.is_premium || false;
    if (!isPremium) {
      isPremium = TextExtractors.detectFlagFromText(fullText, ['carhartt wip', 'work in progress', 'made in usa', 'made in u.s.a']);
    }

    return {
      brand: brand,
      model: model,
      size: size,
      color: color,
      gender: gender || 'homme',
      has_hood: hasHood,
      pattern: pattern,
      lining: lining,
      closure: closure,
      patch_material: patchMaterial,
      collar: collar,
      zip_material: zipMaterial,
      origin_country: originCountry,
      exterior: exterior,
      sleeve_lining: sleeveLining,
      is_camouflage: isCamouflage,
      is_realtree: isRealtree,
      is_new_york: isNewYork,
      is_premium: isPremium,
      sku: sku,
      sku_status: skuStatus,
      order_id: orderId,
      condition: condition
    };
  }

  // =====================================================
  // Normalisation marque pull
  // =====================================================

  function normalizePullBrand(rawBrand) {
    if (rawBrand == null) return null;
    var brandStr = String(rawBrand).trim();
    if (!brandStr) return null;
    var lowered = brandStr.toLowerCase();

    // Tommy Hilfiger
    var tommyAliases = ['hilfiger denim', 'tommy hilfiger denim', 'tommy jeans'];
    for (var i = 0; i < tommyAliases.length; i++) {
      if (lowered.indexOf(tommyAliases[i]) !== -1) return 'Tommy Hilfiger';
    }
    if (lowered.indexOf('tommy hilfiger') !== -1) return 'Tommy Hilfiger';

    // Ralph Lauren
    var ralphAliases = ['polo ralph lauren', 'polo by ralph lauren', 'ralph lauren polo', 'chaps ralph lauren'];
    for (var j = 0; j < ralphAliases.length; j++) {
      if (lowered.indexOf(ralphAliases[j]) !== -1) return 'Ralph Lauren';
    }
    if (lowered.indexOf('ralph lauren') !== -1) return 'Ralph Lauren';

    return brandStr;
  }

  // =====================================================
  // Point d'entree principal
  // =====================================================

  function normalizeAndPostprocess(aiData, profileName, uiData) {
    var profile = coerceProfileName(profileName);
    if (!profile) {
      Logger.log('Normalizer: profil inconnu: ' + profileName);
      return aiData;
    }

    // Construire les features
    var features;
    if (profile === 'jean_levis') features = buildFeaturesForJeanLevis(aiData, uiData);
    else if (profile === 'pull') features = buildFeaturesForPull(aiData, uiData);
    else if (profile === 'jacket_carhart') features = buildFeaturesForJacketCarhart(aiData, uiData);
    else features = aiData.features || {};

    // Construire titre
    var title = TitleEngine.buildTitle(profile, features);

    // Construire description
    var aiDescription = aiData.description || '';
    var aiDefects = aiData.defects || (features.defects || null);
    var description = DescriptionEngine.buildDescription(profile, features, aiDescription, aiDefects);

    // Resultat final
    return {
      title: title,
      description: description,
      brand: features.brand || aiData.brand || null,
      features: features,
      sku: features.sku || null,
      sku_status: features.sku_status || null,
      condition: aiData.condition || null,
      color: features.color || aiData.color || null
    };
  }

  return {
    normalizeAndPostprocess: normalizeAndPostprocess,
    buildFeaturesForJeanLevis: buildFeaturesForJeanLevis,
    buildFeaturesForPull: buildFeaturesForPull,
    buildFeaturesForJacketCarhart: buildFeaturesForJacketCarhart,
    normalizePullBrand: normalizePullBrand,
    coerceProfileName: coerceProfileName,
    normalizeSizes: normalizeSizes,
    zeroPadOrderId: zeroPadOrderId,
    capitalizeMaterial: capitalizeMaterial,
    isElasticMaterial: isElasticMaterial
  };

})();
