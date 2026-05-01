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
    var allowed = ['jean_levis', 'pull', 'jacket_carhart', 'short_carhart', 'short_adidas'];
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
   * Un préfixe "0" seul (étiquette imprimée avec le chiffre manquant) est
   * traité comme le premier lot et donne "01".
   */
  function zeroPadOrderId(orderId) {
    if (!orderId) return '';
    var num = String(orderId).replace(/\D/g, '');
    if (!num) return '';
    // "0" seul = premier lot dont le "1" a été omis à l'impression → "01"
    if (num === '0') num = '1';
    return ('00' + num).slice(-2);
  }
  /**
   * Zero-pad la partie numérique d'un SKU interne sur 4 chiffres.
   * Ex : "HJL01" → "HJL0001", "HJL175" → "HJL0175", "HJL1234" → "HJL1234".
   * Si le SKU ne correspond pas au format lettres+chiffres, retourne la valeur telle quelle.
   *
   * @param {string} sku  SKU brut (ex: "HJL01", "FJL175").
   * @returns {string}    SKU avec partie numérique sur 4 chiffres.
   */
  function zeroPadSkuNumber(sku) {
    if (!sku) return sku || '';
    var s = String(sku).trim().toUpperCase();
    var match = s.match(/^([A-Z]+)(\d+)$/);
    if (!match) return s;
    return match[1] + ('0000' + match[2]).slice(-4);
  }
  // =====================================================
  // Premium Levi's detection
  // =====================================================
  var LEVIS_NUMBERED_MODELS = ['501', '505', '517', '550', '560', '569'];
  var PREMIUM_LEVIS_MODELS = LEVIS_NUMBERED_MODELS.concat([
    'vintage', 'big e', 'orange tab', 'red tab',
    'made in usa', 'selvedge', 'lvc', 'levis vintage clothing'
  ]);
  function isPremiumLevisModel(model) {
    if (!model) return false;
    var low = String(model).toLowerCase().trim();
    for (var i = 0; i < PREMIUM_LEVIS_MODELS.length; i++) {
      if (low.indexOf(PREMIUM_LEVIS_MODELS[i]) !== -1) return true;
    }
    return false;
  }
  // =====================================================
  // Normalisation niveau d'état jean Levi's
  // =====================================================
  /**
   * Normalise une valeur brute de condition (venant de l'IA ou de l'UI)
   * vers exactement l'une des 3 valeurs françaises officielles :
   *   "très bon état" | "bon état général" | "satisfaisant"
   * Fallback : "très bon état" si la valeur est vide ou inconnue.
   *
   * @param {*} value  Valeur brute à normaliser.
   * @returns {string} Valeur normalisée.
   */
  function normalizeJeanConditionLabel_(value) {
    if (!value) return 'très bon état';
    var v = String(value).trim().toLowerCase()
      .replace(/[_-]+/g, ' ')
      .replace(/\s+/g, ' ');
    // Très bon état
    if (v === 'très bon état' || v === 'tres bon etat' ||
        v === 'very good' || v === 'very_good' ||
        v === 'very good condition' || v === 'très bon' ||
        v === 'tres bon') {
      return 'très bon état';
    }
    // Bon état général
    if (v === 'bon état général' || v === 'bon etat general' ||
        v === 'good general' || v === 'good_general' ||
        v === 'general good condition' || v === 'bon état' ||
        v === 'bon etat' || v === 'good condition' || v === 'good') {
      return 'bon état général';
    }
    // Satisfaisant
    if (v === 'satisfaisant' || v === 'satisfactory' ||
        v === 'fair' || v === 'fair condition') {
      return 'satisfaisant';
    }
    // Fallback
    return 'très bon état';
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
    var fitOriginal = null; // Coupe brute Gemini (avant normalisation)
    var uiFit = uiData.fit;
    if (uiFit) {
      var uiFitLow = uiFit.toLowerCase();
      if (uiFitLow === 'droite') fit = 'Droit';
      else if (uiFitLow === 'evasee') fit = 'Évasé';
      else if (uiFitLow === 'skinny') fit = 'Skinny';
      else fit = TextExtractors.normalizeFitLabel(uiFit);
      // Pas de fitOriginal quand c'est un override UI
    } else {
      var rawFit = rawFeatures.fit || aiData.fit;
      if (rawFit) {
        var rawFitStr = String(rawFit).trim();
        if (rawFitStr) fitOriginal = rawFitStr.charAt(0).toUpperCase() + rawFitStr.slice(1);
      }
      fit = TextExtractors.normalizeFitLabel(rawFit);
      if (!fit) fit = TextExtractors.extractFitFromText(fullText);
    }
    var color = rawFeatures.color || aiData.color;
    if (!color) color = TextExtractors.extractColorFromText(fullText);
    var sizeUs = uiData.size_us || rawFeatures.size_us || aiData.size_us;
    var length = uiData.length || rawFeatures.length || aiData.length || null;
    // Text extraction uniquement pour sizeUs (pas pour length)
    if (!sizeUs) {
      var inferred = TextExtractors.extractSizesFromText(fullText);
      if (inferred[0]) sizeUs = inferred[0];
    }
    // Taille FR = toujours US + 10
    var sizeFr = null;
    if (sizeUs) {
      var usNum = parseInt(String(sizeUs).replace(/\D/g, ''), 10);
      if (!isNaN(usNum)) sizeFr = String(usNum + 10);
    }
    // Permettre override manuel
    if (uiData.size_fr) sizeFr = uiData.size_fr;
    var cottonPercent = rawFeatures.cotton_percent || aiData.cotton_percent;
    var elasthanePercent = rawFeatures.elasthane_percent || aiData.elasthane_percent;
    // Composition : depuis l'IA, noms reels de l'etiquette (pas de normalisation)
    var compositionMaterials = rawFeatures.composition_materials || aiData.composition_materials;
    if (compositionMaterials && Array.isArray(compositionMaterials)) {
      compositionMaterials = compositionMaterials.map(capitalizeMaterial).filter(Boolean);
    }
    // Fallback: Coton par defaut si aucune composition detectee
    if (!compositionMaterials || compositionMaterials.length === 0) {
      compositionMaterials = ['Coton'];
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
    // SKU — accepte le format d'étiquette complet "#0HJLXXXX" / "01HJL0001"
    var rawSku = uiData.sku || rawFeatures.sku || aiData.sku;
    var skuParsed = TextExtractors.parseFullSkuLabel(rawSku);
    var sku = skuParsed.sku ? zeroPadSkuNumber(TextExtractors.normalizeSkuValue(skuParsed.sku)) : null;
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
    // Order ID : priorité au préfixe extrait de l'étiquette > saisie UI
    var orderId = skuParsed.orderId
      ? zeroPadOrderId(skuParsed.orderId)
      : zeroPadOrderId(uiData.order_id) || null;
    // Condition : normalisée vers exactement 3 valeurs françaises
    var condition = normalizeJeanConditionLabel_(uiData.condition || rawFeatures.condition || aiData.condition);
    // Premium: IA > detection par modele
    var isPremium = rawFeatures.is_premium || false;
    if (!isPremium && model) {
      isPremium = isPremiumLevisModel(model);
    }
    var features = {
      brand: brand,
      model: model,
      fit: fit,
      fit_original: fitOriginal,
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
      condition: condition,
      labels_cut: uiData.labels_cut || false
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
      sku = zeroPadSkuNumber(skuFromUi);
      if (!skuStatus || skuStatus !== 'ok') skuStatus = 'ok';
    } else if (skuFromAi && skuStatus === 'ok' && /^[A-Za-z]{2,}\s*[0-9]+$/.test(skuFromAi.replace(/\s+/g, ''))) {
      sku = zeroPadSkuNumber(skuFromAi.replace(/\s+/g, ''));
    } else {
      sku = null;
      skuStatus = skuFromAi ? 'invalid' : 'missing';
    }
    // Normalisation marque
    var normalizedBrand = normalizePullBrand(brand);
    var isVintage = normalizedBrand == null;
    var orderId = zeroPadOrderId(uiData.order_id) || null;
    var condition = uiData.condition || rawFeatures.condition || 'tres bon etat';
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
      condition: condition,
      labels_cut: uiData.labels_cut || false
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
      sku = zeroPadSkuNumber(TextExtractors.normalizeJcrSku(skuFromUi));
      skuStatus = sku ? 'ok' : 'low_confidence';
    } else {
      var normalizedAiSku = zeroPadSkuNumber(TextExtractors.normalizeJcrSku(skuFromAi));
      if (normalizedAiSku) { sku = normalizedAiSku; skuStatus = 'ok'; }
      else { sku = null; skuStatus = 'missing'; }
    }
    var orderId = zeroPadOrderId(uiData.order_id) || null;
    var condition = uiData.condition || rawFeatures.condition || 'tres bon etat';
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
      condition: condition,
      labels_cut: uiData.labels_cut || false
    };
  }
  function buildFeaturesForShortCarhart(aiData, uiData) {
    uiData = uiData || {};
    var rawFeatures = aiData.features || {};
    var title = aiData.title || '';
    var description = aiData.description || '';
    var fullText = (title + ' ' + description).trim();
    var brand = rawFeatures.brand || aiData.brand || 'Carhartt';
    var model = rawFeatures.model || aiData.model;
    var size = uiData.size || rawFeatures.size || aiData.size;
    var color = rawFeatures.color || aiData.color;
    if (!color) color = TextExtractors.extractColorFromText(fullText);
    var gender = uiData.gender || rawFeatures.gender || aiData.gender;
    var material = rawFeatures.material || aiData.material;
    var closure = rawFeatures.closure || aiData.closure;
    var pattern = rawFeatures.pattern || aiData.pattern;
    var originCountry = rawFeatures.origin_country || aiData.origin_country;
    if (!originCountry) originCountry = TextExtractors.extractOriginCountryFromText(fullText);
    var hasCargoPockets = rawFeatures.has_cargo_pockets;
    if (hasCargoPockets == null) hasCargoPockets = TextExtractors.detectFlagFromText(fullText, ['cargo', 'rabat', 'poche latérale', 'poche laterale']);
    var hasBeltLoops = rawFeatures.has_belt_loops;
    if (hasBeltLoops == null) hasBeltLoops = TextExtractors.detectFlagFromText(fullText, ['passant', 'belt loop', 'ceinture']);
    // SKU HSC
    var skuFromUi = uiData.sku;
    var skuFromAi = rawFeatures.sku || aiData.sku;
    var sku = null;
    var skuStatus;
    if (skuFromUi) {
      sku = zeroPadSkuNumber(TextExtractors.normalizeHscSku(skuFromUi));
      skuStatus = sku ? 'ok' : 'low_confidence';
    } else {
      var normalizedAiSku = zeroPadSkuNumber(TextExtractors.normalizeHscSku(skuFromAi));
      if (normalizedAiSku) { sku = normalizedAiSku; skuStatus = 'ok'; }
      else { sku = null; skuStatus = 'missing'; }
    }
    var orderId = zeroPadOrderId(uiData.order_id) || null;
    var condition = uiData.condition || rawFeatures.condition || 'tres bon etat';
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
      material: material,
      closure: closure,
      has_cargo_pockets: hasCargoPockets,
      has_belt_loops: hasBeltLoops,
      pattern: pattern,
      origin_country: originCountry,
      is_premium: isPremium,
      sku: sku,
      sku_status: skuStatus,
      order_id: orderId,
      condition: condition,
      labels_cut: uiData.labels_cut || false
    };
  }
  function buildFeaturesForShortAdidas(aiData, uiData) {
    uiData = uiData || {};
    var rawFeatures = aiData.features || {};
    var title = aiData.title || '';
    var description = aiData.description || '';
    var fullText = (title + ' ' + description).trim();
    var brand = rawFeatures.brand || aiData.brand || 'Adidas';
    var model = rawFeatures.model || aiData.model;
    var size = uiData.size || rawFeatures.size || aiData.size;
    var color = rawFeatures.color || aiData.color;
    if (!color) color = TextExtractors.extractColorFromText(fullText);
    var gender = uiData.gender || rawFeatures.gender || aiData.gender;
    var material = rawFeatures.material || aiData.material;
    var technology = rawFeatures.technology || aiData.technology;
    var pattern = rawFeatures.pattern || aiData.pattern;
    var originCountry = rawFeatures.origin_country || aiData.origin_country;
    if (!originCountry) originCountry = TextExtractors.extractOriginCountryFromText(fullText);
    // Logo distinct du logo Adidas (écusson / patch club / sélection / compétition…)
    var secondaryLogo = rawFeatures.secondary_logo || aiData.secondary_logo || null;
    var secondaryLogoMeaning = rawFeatures.secondary_logo_meaning || aiData.secondary_logo_meaning || null;
    if (typeof secondaryLogo === 'string') {
      secondaryLogo = secondaryLogo.trim();
      if (!secondaryLogo) secondaryLogo = null;
    }
    if (typeof secondaryLogoMeaning === 'string') {
      secondaryLogoMeaning = secondaryLogoMeaning.trim();
      if (!secondaryLogoMeaning) secondaryLogoMeaning = null;
    }
    // Pas de signification utile si on n'a pas pu identifier le logo.
    if (!secondaryLogo) secondaryLogoMeaning = null;
    var hasSidePockets = rawFeatures.has_side_pockets;
    if (hasSidePockets == null) hasSidePockets = TextExtractors.detectFlagFromText(fullText, ['poche', 'pocket', 'zip']);
    var hasDrawstring = rawFeatures.has_drawstring;
    if (hasDrawstring == null) hasDrawstring = TextExtractors.detectFlagFromText(fullText, ['cordon', 'drawstring', 'lacet', 'lien']);
    // SKU HSA
    var skuFromUi = uiData.sku;
    var skuFromAi = rawFeatures.sku || aiData.sku;
    var sku = null;
    var skuStatus;
    if (skuFromUi) {
      sku = zeroPadSkuNumber(TextExtractors.normalizeHsaSku(skuFromUi));
      skuStatus = sku ? 'ok' : 'low_confidence';
    } else {
      var normalizedAiSku = zeroPadSkuNumber(TextExtractors.normalizeHsaSku(skuFromAi));
      if (normalizedAiSku) { sku = normalizedAiSku; skuStatus = 'ok'; }
      else { sku = null; skuStatus = 'missing'; }
    }
    var orderId = zeroPadOrderId(uiData.order_id) || null;
    var condition = uiData.condition || rawFeatures.condition || 'tres bon etat';
    var isPremium = rawFeatures.is_premium || false;
    if (!isPremium) {
      isPremium = TextExtractors.detectFlagFromText(fullText, ['adidas originals', 'originals', 'y-3', 'stella mccartney', 'collaboration', 'limited edition']);
    }
    return {
      brand: brand,
      model: model,
      size: size,
      color: color,
      gender: gender || 'homme',
      material: material,
      technology: technology,
      has_side_pockets: hasSidePockets,
      has_drawstring: hasDrawstring,
      pattern: pattern,
      origin_country: originCountry,
      secondary_logo: secondaryLogo,
      secondary_logo_meaning: secondaryLogoMeaning,
      is_premium: isPremium,
      sku: sku,
      sku_status: skuStatus,
      order_id: orderId,
      condition: condition,
      labels_cut: uiData.labels_cut || false
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
    else if (profile === 'short_carhart') features = buildFeaturesForShortCarhart(aiData, uiData);
    else if (profile === 'short_adidas') features = buildFeaturesForShortAdidas(aiData, uiData);
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
    buildFeaturesForShortCarhart: buildFeaturesForShortCarhart,
    buildFeaturesForShortAdidas: buildFeaturesForShortAdidas,
    normalizePullBrand: normalizePullBrand,
    coerceProfileName: coerceProfileName,
    normalizeSizes: normalizeSizes,
    zeroPadOrderId: zeroPadOrderId,
    zeroPadSkuNumber: zeroPadSkuNumber,
    capitalizeMaterial: capitalizeMaterial,
    isElasticMaterial: isElasticMaterial,
    normalizeJeanConditionLabel: normalizeJeanConditionLabel_,
    levisNumberedModels: LEVIS_NUMBERED_MODELS
  };
})();