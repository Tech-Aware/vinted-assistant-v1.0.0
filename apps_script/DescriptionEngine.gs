/**
 * DescriptionEngine.gs - Moteur de construction des descriptions
 *
 * Port de domain/description_engine.py
 */
var DescriptionEngine = (function() {
  function buildDescriptionJeanLevis(features, aiDescription, aiDefects) {
    try {
      var sizeFr = DescriptionBuilder.safeClean(features.size_fr);
      var sizeUs = DescriptionBuilder.safeClean(features.size_us);
      var sku = DescriptionBuilder.safeClean(features.sku);
      var orderId = DescriptionBuilder.safeClean(features.order_id);
      var color = DescriptionBuilder.safeClean(features.color);
      var rawFit = DescriptionBuilder.safeClean(features.fit);
      var model = DescriptionBuilder.safeClean(features.model);
      var fit = DescriptionBuilder.normalizeFitDisplay(rawFit, model);
      // Genre : fallback via SKU (HJL = homme, JLF = femme)
      var skuUpper = (sku || '').toUpperCase();
      var isHomme = skuUpper.indexOf('HJL') !== -1;
      var gender = DescriptionBuilder.safeClean(features.gender) || (isHomme ? 'homme' : 'femme');
      // Première ligne = titre final généré (SKU retiré pour ne le garder qu'en bas)
      var titleLine = '';
      try {
        titleLine = TitleEngine.buildTitle('jean_levis', features) || '';
      } catch (eTitle) {
        titleLine = '';
      }
      titleLine = DescriptionBuilder.stripSkuFromTitleLine(titleLine);
      // Ligne taille
      var sizeLine;
      if (sizeFr && sizeUs) sizeLine = '👖 Taille FR' + sizeFr + ' / US' + sizeUs;
      else if (sizeFr) sizeLine = '👖 Taille FR' + sizeFr;
      else if (sizeUs) sizeLine = '👖 Taille US' + sizeUs;
      else sizeLine = '👖 Taille : voir photos';
      // Mention écart taille étiquette / mesures à plat
      var sizeNote = '📏 La taille indiquée correspond à l\'étiquette. '
        + 'Les mesures à plat visibles en photo peuvent différer selon la coupe, '
        + 'l\'élasticité du tissu ou le tombé du jean.';
      // État + défauts
      var defectsRaw = aiDefects || features.defects;
      var defectsClean = DescriptionBuilder.normalizeDefects(defectsRaw);
      var conditionLabel = DescriptionBuilder.safeClean(features.condition).toLowerCase();
      var defectSentence = defectsClean ? defectsClean.replace(/[.\s]+$/, '') + '.' : '';
      var stateBlock;
      if (conditionLabel === 'bon état général') {
        stateBlock = '👍 Bon état général';
        if (defectSentence) {
          stateBlock += '\nDéfauts à noter : ' + defectSentence;
        }
      } else if (conditionLabel === 'satisfaisant') {
        stateBlock = '👍 Satisfaisant';
        if (defectSentence) {
          stateBlock += '\nDéfauts à noter : ' + defectSentence;
        }
      } else {
        stateBlock = '👍 Très bon état';
        if (defectSentence) {
          stateBlock += '\nÀ noter : ' + defectSentence;
        }
      }
      var measuresLine = features.labels_cut
        ? '🔎 Mesures précises en photo. Étiquettes coupées pour plus de confort.'
        : '🔎 Mesures précises et composition détaillée en photo.';
      var shippingLine = '📦 Envoi rapide et soigné';
      var lotLine = '💡 Réduction possible sur lot';
      // Bloc navigation dressing (2 à 3 hashtags)
      var navTags = DescriptionBuilder.buildJeanNavigationTags({
        sizeFr: sizeFr,
        gender: gender,
        fit: fit,
        color: color
      });
      var primaryNavTag = navTags.length > 0 ? navTags[0] : '';
      var remainingNavTags = navTags.slice(1);
      // Ligne de navigation taille (deuxième ligne, juste après le titre)
      var navigationLine = primaryNavTag
        ? '👖 Retrouvez tous mes jeans à votre taille → ' + primaryNavTag
        : '';
      // Bloc navigation dressing final (sans le premier tag)
      var navBlock = '';
      if (remainingNavTags.length > 0) {
        navBlock = 'Navigation dressing :\n' + remainingNavTags.join('\n');
      }
      // Hashtag SKU seul, en MAJUSCULES, sur la dernière ligne
      var skuTag = DescriptionBuilder.buildJeanSkuTag({ sku: sku, orderId: orderId });
      // Assemblage
      var sections = [];
      if (titleLine) sections.push(titleLine);
      if (navigationLine) sections.push(navigationLine);
      sections.push(sizeLine);
      sections.push(sizeNote);
      sections.push(stateBlock);
      sections.push([measuresLine, shippingLine, lotLine].join('\n'));
      if (navBlock) sections.push(navBlock);
      if (skuTag) sections.push(skuTag);
      return sections.join('\n\n');
    } catch (e) {
      Logger.log('buildDescriptionJeanLevis error: ' + e.message);
      return DescriptionBuilder.safeClean(aiDescription);
    }
  }
  function buildDescriptionPull(features, aiDescription, aiDefects) {
    try {
      var brand = DescriptionBuilder.safeClean(features.brand);
      var isVintage = features.is_vintage || false;
      if (!brand) { isVintage = true; brand = 'Vintage'; }
      var garmentType = DescriptionBuilder.safeClean(features.garment_type) || 'pull';
      var gender = DescriptionBuilder.safeClean(features.gender) || 'femme';
      var neckline = DescriptionBuilder.safeClean(features.neckline);
      var pattern = DescriptionBuilder.safeClean(features.pattern);
      var material = DescriptionBuilder.safeClean(features.material);
      var cottonPercent = features.cotton_percent;
      var woolPercent = features.wool_percent;
      var colorsRaw = features.main_colors;
      var size = DescriptionBuilder.normalizePullSize(features.size);
      var sizeSource = (DescriptionBuilder.safeClean(features.size_source) || '').toLowerCase();
      var measurementMode = (DescriptionBuilder.safeClean(features.measurement_mode) || '').toLowerCase();
      var defects = aiDefects || features.defects;
      var colors = '';
      if (Array.isArray(colorsRaw)) {
        colors = colorsRaw.map(function(c) { return DescriptionBuilder.safeClean(c); }).filter(Boolean).join(', ');
      } else {
        colors = DescriptionBuilder.safeClean(colorsRaw);
      }
      // Neckline
      var necklineText = '';
      if (neckline) {
        necklineText = neckline.toLowerCase().indexOf('col') === 0 ? neckline : 'col ' + neckline;
      }
      // Headline
      var isPremium = features.is_premium || false;
      var brandLabel = brand + (isPremium ? ' Premium' : '');
      var headlineMain = [garmentType.charAt(0).toUpperCase() + garmentType.slice(1) + ' ' + brandLabel];
      if (gender) headlineMain.push(gender.toLowerCase());
      var headlineLine1 = headlineMain.filter(Boolean).join(' ').trim();
      var sizePart = '';
      if (size) {
        sizePart = (sizeSource === 'estimated' || measurementMode === 'mesures')
          ? 'taille ' + size + ' (estimée via mesures)'
          : 'taille ' + size;
      }
      if (sizePart) headlineLine1 += ' - ' + sizePart;
      headlineLine1 = headlineLine1.replace(/\.$/, '') + '.';
      // Style bits
      var styleBits = [];
      if (pattern) styleBits.push('maille ' + pattern);
      if (necklineText) styleBits.push(necklineText);
      if (colors) styleBits.push(colors);
      var headlineLine2 = styleBits.filter(Boolean).join(', ').trim();
      if (headlineLine2) headlineLine2 = headlineLine2.replace(/\.$/, '') + '.';
      var headline = [headlineLine1, headlineLine2].filter(Boolean).join('\n');
      // Sensation
      var cottonVal = DescriptionBuilder.formatPercent(cottonPercent);
      var woolVal = DescriptionBuilder.formatPercent(woolPercent);
      var sensationSentence = null;
      if (woolVal != null) sensationSentence = 'Maille chaude et confortable, agréable à porter par temps frais.';
      else if (cottonVal != null) sensationSentence = 'Maille douce et respirante, confortable pour un usage quotidien.';
      // Composition
      var compTokens = [];
      if (cottonVal != null) compTokens.push(cottonVal + '% coton');
      if (woolVal != null) compTokens.push(woolVal + '% laine');
      var compositionSentence;
      if (compTokens.length > 0) {
        compositionSentence = 'Composition : ' + compTokens.join(' / ') + '.';
      } else if (material) {
        compositionSentence = 'Composition (étiquette) : ' + material.replace(/\.$/, '') + '.';
      } else if (features.labels_cut) {
        compositionSentence = 'Étiquettes coupées pour plus de confort.';
      } else {
        compositionSentence = 'Composition non lisible (voir photos).';
      }
      // Etat
      var stateSentence;
      if (defects) {
        var d = DescriptionBuilder.safeClean(defects).replace(/\.$/, '');
        if (d.charAt(0) === d.charAt(0).toUpperCase()) d = d.charAt(0).toLowerCase() + d.slice(1);
        stateSentence = 'Bon état : ' + d + ' (voir photos).';
      } else {
        stateSentence = 'État : très bon état (voir photos).';
      }
      // Footer
      var sizeToken = (size || 'NC').replace(/\s/g, '').toUpperCase();
      var durinTag = '#durin31tf' + sizeToken;
      var hashtagTokens = [];
      function addTag(t) { if (t && hashtagTokens.indexOf(t) === -1) hashtagTokens.push(t); }
      addTag('#tommyhilfiger'); addTag('#pulltommy'); addTag('#tommy');
      addTag(gender.toLowerCase() === 'femme' ? '#pullfemme' : '#pullhomme');
      addTag('#mode'); addTag('#preloved'); addTag(durinTag); addTag('#ptf');
      if (colors) {
        colors.split(',').forEach(function(c) {
          var cc = c.trim().toLowerCase().replace(/\s/g, '');
          if (cc) addTag('#' + cc);
        });
      }
      var footer = [
        '📏 Mesures detaillees visibles en photo pour plus de precisions.',
        '📦 Envoi rapide et soigne.',
        '✨ Retrouvez tous mes pulls ici 👉 ' + durinTag,
        "💡 Pensez a faire un lot pour profiter d'une reduction supplementaire et economiser des frais d'envoi !",
        '',
        hashtagTokens.join(' ')
      ].join('\n');
      var paragraphs = [headline, sensationSentence, compositionSentence, stateSentence, footer];
      return paragraphs.filter(Boolean).join('\n\n');
    } catch (e) {
      Logger.log('buildDescriptionPull error: ' + e.message);
      return DescriptionBuilder.safeClean(aiDescription);
    }
  }
  function buildDescriptionJacketCarhart(features, aiDescription, aiDefects) {
    try {
      var brand = DescriptionBuilder.safeClean(features.brand) || 'Carhartt';
      brand = brand.charAt(0).toUpperCase() + brand.slice(1);
      var model = DescriptionBuilder.safeClean(features.model);
      var rawSize = DescriptionBuilder.safeClean(features.size) || 'NC';
      var sizeResult = TitleBuilder.normalizeCarharttSize(rawSize);
      var sizeDisplay = sizeResult[0];
      var sizeToken = sizeResult[1];
      var color = DescriptionBuilder.safeClean(features.color);
      var gender = DescriptionBuilder.safeClean(features.gender) || 'homme';
      var lining = DescriptionBuilder.safeClean(features.lining);
      var patchMaterial = DescriptionBuilder.safeClean(features.patch_material);
      var originCountry = DescriptionBuilder.safeClean(features.origin_country);
      // Product sentence
      var isPremium = features.is_premium || false;
      var productParts = [isPremium ? 'Veste ' + brand + ' Premium' : 'Veste ' + brand];
      if (model && /^\d+$/.test(model)) productParts.push(model);
      if (gender) productParts.push('pour ' + gender);
      productParts.push('taille ' + sizeDisplay);
      if (color) productParts.push('coloris ' + color);
      if (originCountry) productParts.push('Made in ' + originCountry);
      var productSentence = productParts.filter(Boolean).join(' ').replace(/\.$/, '') + '.';
      // Style
      var patchLabel = (patchMaterial || 'simili-cuir').toLowerCase();
      var colorIntro = color
        ? 'Le coloris ' + color.toLowerCase() + " sobre s'associe facilement avec toutes les tenues."
        : 'Coloris à confirmer sur les photos.';
      var styleSentence = 'Modèle iconique du workwear Carhartt, coupe droite intemporelle, écusson Carhartt en ' + patchLabel + ", facile à porter au quotidien. " + colorIntro;
      // Warmth
      var liningLabel = '';
      if (lining) {
        var low = lining.toLowerCase();
        if (low.indexOf('matelass') !== -1) liningLabel = 'doublure matelassée';
        else if (low.indexOf('sherpa') !== -1) liningLabel = 'doublure sherpa';
        else if (low.indexOf('blanket') !== -1 || low.indexOf('laine') !== -1) liningLabel = 'doublure type blanket';
      }
      var warmthSentence = '';
      if (liningLabel) {
        warmthSentence = 'La ' + liningLabel + " apporte une bonne chaleur, idéale pour la mi-saison comme pour l'hiver.";
      }
      // State
      var defects = DescriptionBuilder.safeClean(features.defects || aiDefects);
      var normalizedDefects = DescriptionBuilder.normalizeDefects(defects);
      var stateSentence = !normalizedDefects
        ? 'Très bon état, aucun défaut majeur visible. Veste propre et bien conservée (voir photos).'
        : 'Très bon état, ' + normalizedDefects + '. Veste propre et bien conservée (voir photos).';
      // Footer
      var generalTag = '#durin31jc';
      var sTag = sizeToken ? generalTag + sizeToken : '#durin31jcnc';
      var colorTag = color ? '#' + color.toLowerCase().replace(/\s/g, '') : '';
      var logisticsLine = features.labels_cut
        ? '📏 Mesures détaillées visibles en photo pour plus de précisions. Étiquettes coupées pour plus de confort.'
        : '📏 Mesures détaillées visibles en photo pour plus de précisions.';
      var shippingLine = '📦 Envoi rapide et soigné.';
      var ctaLine = '✨ Retrouvez toutes mes vestes Carhartt ici 👉 ' + generalTag + ' et à votre taille 👉 ' + sTag;
      var bundleLine = "💡 Pensez à faire un lot pour bénéficier d'une réduction et économiser sur les frais d'envoi.";
      var hashtagCore = '#carhartt #jacket #workwear #durin31';
      var hashtags = [hashtagCore, sTag, colorTag].filter(Boolean).join(' ');
      var paragraphs = [productSentence, styleSentence, warmthSentence, stateSentence, logisticsLine, shippingLine, ctaLine, bundleLine, hashtags];
      return paragraphs.filter(Boolean).join('\n\n');
    } catch (e) {
      Logger.log('buildDescriptionJacketCarhart error: ' + e.message);
      return DescriptionBuilder.safeClean(aiDescription);
    }
  }
  function buildDescriptionShortCarhart(features, aiDescription, aiDefects) {
    try {
      var brand = DescriptionBuilder.safeClean(features.brand) || 'Carhartt';
      brand = brand.charAt(0).toUpperCase() + brand.slice(1);
      var model = DescriptionBuilder.safeClean(features.model);
      var rawSize = DescriptionBuilder.safeClean(features.size) || 'NC';
      var sizeResult = TitleBuilder.normalizeCarharttSize(rawSize);
      var sizeDisplay = sizeResult[0];
      var sizeToken = sizeResult[1];
      var color = DescriptionBuilder.safeClean(features.color);
      var gender = DescriptionBuilder.safeClean(features.gender) || 'homme';
      var material = DescriptionBuilder.safeClean(features.material);
      var closure = DescriptionBuilder.safeClean(features.closure);
      var pattern = DescriptionBuilder.safeClean(features.pattern);
      var originCountry = DescriptionBuilder.safeClean(features.origin_country);
      var hasCargoPockets = features.has_cargo_pockets;
      var hasBeltLoops = features.has_belt_loops;
      // Product sentence
      var isPremium = features.is_premium || false;
      var productParts = [isPremium ? 'Short ' + brand + ' Premium' : 'Short ' + brand];
      if (model && /^\d+$/.test(model)) productParts.push(model);
      if (gender) productParts.push('pour ' + gender);
      productParts.push('taille ' + sizeDisplay);
      if (color) productParts.push('coloris ' + color);
      if (originCountry) productParts.push('Made in ' + originCountry);
      var productSentence = productParts.filter(Boolean).join(' ').replace(/\.$/, '') + '.';
      // Style sentence
      var styleDetails = [];
      if (material) styleDetails.push('tissu ' + material.toLowerCase());
      if (hasCargoPockets) styleDetails.push('poches cargo latérales');
      if (hasBeltLoops) styleDetails.push('passants de ceinture');
      if (closure) styleDetails.push('fermeture ' + closure.toLowerCase());
      if (pattern && pattern.toLowerCase() !== 'uni') styleDetails.push('motif ' + pattern.toLowerCase());
      var colorIntro = color
        ? 'Le coloris ' + color.toLowerCase() + " sobre s'associe facilement avec toutes les tenues."
        : 'Coloris à confirmer sur les photos.';
      var styleBase = 'Short iconique Carhartt, coupe workwear décontractée, idéal pour la saison chaude.';
      var styleSentence = styleDetails.length > 0
        ? styleBase + ' ' + styleDetails.join(', ').replace(/^\w/, function(c) { return c.toUpperCase(); }) + '. ' + colorIntro
        : styleBase + ' ' + colorIntro;
      // State
      var defects = DescriptionBuilder.safeClean(features.defects || aiDefects);
      var normalizedDefects = DescriptionBuilder.normalizeDefects(defects);
      var stateSentence = !normalizedDefects
        ? 'Très bon état, aucun défaut majeur visible. Short propre et bien conservé (voir photos).'
        : 'Très bon état, ' + normalizedDefects + '. Short propre et bien conservé (voir photos).';
      // Footer
      var generalTag = '#durin31hsc';
      var sTag = sizeToken ? generalTag + sizeToken : '#durin31hscnc';
      var colorTag = color ? '#' + color.toLowerCase().replace(/\s/g, '') : '';
      var logisticsLine = features.labels_cut
        ? '📏 Mesures détaillées visibles en photo pour plus de précisions. Étiquettes coupées pour plus de confort.'
        : '📏 Mesures détaillées visibles en photo pour plus de précisions.';
      var shippingLine = '📦 Envoi rapide et soigné.';
      var ctaLine = '✨ Retrouvez tous mes shorts Carhartt ici 👉 ' + generalTag + ' et à votre taille 👉 ' + sTag;
      var bundleLine = "💡 Pensez à faire un lot pour bénéficier d'une réduction et économiser sur les frais d'envoi.";
      var hashtagCore = '#carhartt #short #workwear #durin31';
      var hashtags = [hashtagCore, sTag, colorTag].filter(Boolean).join(' ');
      var paragraphs = [productSentence, styleSentence, stateSentence, logisticsLine, shippingLine, ctaLine, bundleLine, hashtags];
      return paragraphs.filter(Boolean).join('\n\n');
    } catch (e) {
      Logger.log('buildDescriptionShortCarhart error: ' + e.message);
      return DescriptionBuilder.safeClean(aiDescription);
    }
  }
  function buildDescriptionShortAdidas(features, aiDescription, aiDefects) {
    try {
      var brand = DescriptionBuilder.safeClean(features.brand) || 'Adidas';
      brand = brand.charAt(0).toUpperCase() + brand.slice(1);
      var rawSize = DescriptionBuilder.safeClean(features.size) || 'NC';
      var sizeResult = TitleBuilder.normalizeCarharttSize(rawSize);
      var sizeDisplay = sizeResult[0];
      var color = DescriptionBuilder.safeClean(features.color);
      var gender = DescriptionBuilder.safeClean(features.gender) || 'homme';
      var sportType = DescriptionBuilder.safeClean(features.sport_type);
      var hasThreeStripes = features.has_three_stripes === true;
      var fitOrCut = DescriptionBuilder.safeClean(features.fit_or_cut);
      var technology = DescriptionBuilder.safeClean(features.technology);
      // Logo additionnel (hors logo Adidas) : on ne mentionne le logo que si l'IA
      // a su l'identifier ; sinon on évite toute supposition hasardeuse.
      var secondaryLogo = DescriptionBuilder.safeClean(features.secondary_logo);
      var secondaryLogoMeaning = DescriptionBuilder.safeClean(features.secondary_logo_meaning);
      var secondaryLogoLow = (secondaryLogo || '').toLowerCase();
      var hasUsableSecondaryLogo = !!(secondaryLogo
        && secondaryLogoLow !== 'logo non identifié'
        && secondaryLogoLow !== 'logo non identifie');
      var sku = DescriptionBuilder.safeClean(features.sku);
      var orderId = DescriptionBuilder.safeClean(features.order_id);
      // ----- Première ligne : titre généré (SKU retiré, repris en bas) -----
      var titleLine = '';
      try {
        titleLine = TitleEngine.buildTitle('short_adidas', features) || '';
      } catch (eTitle) {
        titleLine = '';
      }
      titleLine = DescriptionBuilder.stripSkuFromTitleLine(titleLine);
      // ----- Bloc navigation dressing (#FP_Homme_Sport_<taille>) -----
      var navTags = DescriptionBuilder.buildShortAdidasNavigationTags({
        size: sizeDisplay,
        gender: gender,
        color: color
      });
      var primaryNavTag = navTags.length > 0 ? navTags[0] : '#FP_Homme_Sport_NC';
      var remainingNavTags = navTags.slice(1);
      var navigationLine = '🩳 Retrouvez tous mes shorts à votre taille → ' + primaryNavTag;
      // ----- Ligne taille -----
      var sizeLine = '🩳 Taille ' + sizeDisplay;
      var sizeNote = '📏 La taille indiquée correspond à l\'étiquette (voir photo).';
      // ----- État + défauts (modèle Levi's : 3 niveaux) -----
      var defectsRaw = aiDefects || features.defects;
      var defectsClean = DescriptionBuilder.normalizeDefects(defectsRaw);
      var conditionLabel = DescriptionBuilder.safeClean(features.condition).toLowerCase();
      var defectSentence = defectsClean ? defectsClean.replace(/[.\s]+$/, '') + '.' : '';
      // Pour le très bon état, on ne mentionne les défauts que s'ils sont vraiment
      // apparents (tâche, trou, déchirure, accroc, etc.) — l'usure normale ne se mentionne pas.
      var apparentDefectKeywords = ['tâche', 'tache', 'trou', 'déchirure', 'dechirure',
        'accroc', 'brûlure', 'brulure', 'effiloch', 'décousu', 'decousu', 'couture'];
      function isApparentDefect(text) {
        if (!text) return false;
        var low = text.toLowerCase();
        for (var k = 0; k < apparentDefectKeywords.length; k++) {
          if (low.indexOf(apparentDefectKeywords[k]) !== -1) return true;
        }
        return false;
      }
      var stateBlock;
      if (conditionLabel === 'bon état général' || conditionLabel === 'bon etat general') {
        stateBlock = '👍 Bon état général';
        if (defectSentence) stateBlock += '\nDéfauts à noter : ' + defectSentence;
      } else if (conditionLabel === 'satisfaisant') {
        stateBlock = '👍 Satisfaisant';
        if (defectSentence) stateBlock += '\nDéfauts à noter : ' + defectSentence;
      } else {
        stateBlock = '👍 Très bon état';
        if (defectSentence && isApparentDefect(defectSentence)) {
          stateBlock += '\nÀ noter : ' + defectSentence;
        }
      }
      // Phrase dédiée au logo additionnel (écusson de club, sélection, compétition…)
      // Ex. : "🏷️ Logo FC Bayern Munich apposé sur le short — club de football allemand basé à Munich."
      var logoSentence = '';
      if (hasUsableSecondaryLogo) {
        logoSentence = '🏷️ Logo ' + secondaryLogo + ' apposé sur le short';
        if (secondaryLogoMeaning) {
          logoSentence += ' — ' + secondaryLogoMeaning.replace(/[.\s]+$/, '');
        }
        logoSentence += '.';
      }
      // ----- Composition -----
      var compositionMaterials = features.composition_materials || [];
      var compositionLine;
      if (compositionMaterials.length > 0) {
        compositionLine = '🔎 Composition : ' + compositionMaterials.join(' / ') + '.';
      } else if (features.labels_cut) {
        compositionLine = '🔎 Étiquettes coupées — composition non disponible.';
      } else {
        compositionLine = '🔎 Composition détaillée en photo.';
      }
      // ----- Logistique / envoi / lot -----
      var shippingLine = '📦 Envoi rapide et soigné';
      var lotLine = '💡 Réduction possible sur lot';
      // ----- Hashtag SKU final (en MAJUSCULES, seul, dernière ligne) -----
      var skuTag = '';
      if (sku) {
        var clean = Normalizer.zeroPadSkuNumber(sku.replace(/\s/g, '').toUpperCase());
        if (orderId) {
          var pad = Normalizer.zeroPadOrderId(orderId);
          if (pad) clean = pad + clean;
        }
        skuTag = '#' + clean;
      }
      // ----- Bloc usage (sport_type, fit_or_cut, has_three_stripes, technology) -----
      var usageLines = [];
      if (sportType) {
        var st = sportType.toLowerCase();
        if (st === 'basketball') {
          usageLines.push('Short Adidas esprit basketball, avec une coupe confortable, adapt\u00e9 au sport comme aux tenues sportswear du quotidien.');
        } else if (st === 'training') {
          usageLines.push('Short Adidas orient\u00e9 training, l\u00e9ger et pratique pour l\u2019entra\u00eenement, la marche ou une tenue d\u00e9contract\u00e9e.');
        } else if (st === 'running') {
          usageLines.push('Short Adidas orient\u00e9 running, l\u00e9ger et facile \u00e0 porter pour le sport, la marche ou les journ\u00e9es actives.');
        } else if (st === 'football') {
          usageLines.push('Short Adidas esprit football, pratique pour le sport, l\u2019entra\u00eenement ou une tenue sportswear simple.');
        } else if (st === 'tennis') {
          usageLines.push('Short Adidas esprit tennis, sobre et confortable, adapt\u00e9 au sport comme \u00e0 une tenue estivale d\u00e9contract\u00e9e.');
        } else if (st === 'lifestyle') {
          usageLines.push('Short Adidas sportswear, simple et confortable, facile \u00e0 porter au quotidien.');
        } else {
          usageLines.push('Short Adidas sportswear, confortable et facile \u00e0 porter pour le sport, la d\u00e9tente ou le quotidien.');
        }
      } else {
        usageLines.push('Short Adidas sportswear, confortable et facile \u00e0 porter pour le sport, la d\u00e9tente ou le quotidien.');
      }
      if (fitOrCut) {
        usageLines.push('Coupe ' + fitOrCut.toLowerCase() + ', facile \u00e0 porter.');
      }
      if (hasThreeStripes) {
        usageLines.push('Mod\u00e8le avec les 3 bandes Adidas visibles sur les c\u00f4t\u00e9s.');
      }
      if (technology) {
        usageLines.push('Technologie Adidas indiqu\u00e9e sur l\u2019\u00e9tiquette\u00a0: ' + technology + '.');
      }
      var usageBlock = usageLines.join('\n');
      // ----- Assemblage -----
      var sections = [];
      if (titleLine) sections.push(titleLine);
      sections.push(navigationLine);
      sections.push(usageBlock);
      if (logoSentence) sections.push(logoSentence);
      sections.push(sizeLine);
      sections.push(sizeNote);
      sections.push(stateBlock);
      sections.push([compositionLine, shippingLine, lotLine].join('\n'));
      // Bloc navigation dressing final (tags supplémentaires)
      var navBlock = '';
      if (remainingNavTags.length > 0) {
        navBlock = 'Navigation dressing :\n' + remainingNavTags.join('\n');
      }
      if (navBlock) sections.push(navBlock);
      if (skuTag) sections.push(skuTag);
      return sections.join('\n\n');
    } catch (e) {
      Logger.log('buildDescriptionShortAdidas error: ' + e.message);
      return DescriptionBuilder.safeClean(aiDescription);
    }
  }
  /**
   * Point d'entree unique pour construire les descriptions.
   */
  function buildDescription(profileName, features, aiDescription, aiDefects) {
    try {
      if (profileName === 'jean_levis') return buildDescriptionJeanLevis(features, aiDescription, aiDefects);
      if (profileName === 'pull') return buildDescriptionPull(features, aiDescription, aiDefects);
      if (profileName === 'jacket_carhart') return buildDescriptionJacketCarhart(features, aiDescription, aiDefects);
      if (profileName === 'short_carhart') return buildDescriptionShortCarhart(features, aiDescription, aiDefects);
      if (profileName === 'short_adidas') return buildDescriptionShortAdidas(features, aiDescription, aiDefects);
      return (aiDescription || '').trim();
    } catch (e) {
      Logger.log('buildDescription error: ' + e.message);
      return (aiDescription || '').trim();
    }
  }
  return {
    buildDescription: buildDescription
  };
})();