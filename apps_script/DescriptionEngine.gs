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
      var measuresLine = '🔎 Mesures précises et composition détaillée en photo.';
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
      var logisticsLine = '📏 Mesures détaillées visibles en photo pour plus de précisions.';
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
  /**
   * Point d'entree unique pour construire les descriptions.
   */
  function buildDescription(profileName, features, aiDescription, aiDefects) {
    try {
      if (profileName === 'jean_levis') return buildDescriptionJeanLevis(features, aiDescription, aiDefects);
      if (profileName === 'pull') return buildDescriptionPull(features, aiDescription, aiDefects);
      if (profileName === 'jacket_carhart') return buildDescriptionJacketCarhart(features, aiDescription, aiDefects);
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