// ============================================================
// Tests Apps Script — barème jean Levi's / Denizen / Signature
// ============================================================
//
// Lancer dans l'éditeur Apps Script :
//   testPricingJeanLevis_()
//
// La fonction écrit un résumé dans les logs (View > Logs) et lève
// une exception au premier cas non conforme.
//
// Les cas couvrent les critères d'acceptation de la mission :
//   - Denizen / Signature plafonné à 19 €, sans prime grande taille
//   - Levi's standard femme à partir de 24 € ; +1 € si FR ≥ 42
//   - Levi's standard homme cohérent autour de 26–29 €
//   - Premium uniquement si features.is_premium === true
//   - Modèles 501 / 505 / etc. ne déclenchent pas seuls le premium
//   - Le budget Denizen / Signature prime sur features.is_premium
//   - Plafonds : femme 26 € standard / 29 € premium, homme 32 € standard / 35 € premium
//   - acceptable_price ≤ price, floor_price ≤ acceptable_price
//
function testPricingJeanLevis_() {
  var cases = [
    // --- Denizen / Signature femme ---
    {
      name: 'Denizen femme sans défaut',
      features: { gender: 'femme', brand: 'Denizen from Levi\'s', model: '', fit: 'Droit' },
      expected: 19
    },
    {
      name: 'Denizen femme avec défaut',
      features: { gender: 'femme', brand: 'Denizen from Levi\'s', model: '', fit: 'Droit', condition: 'satisfaisant' },
      expected: 16
    },
    {
      name: 'Denizen femme FR42 sans défaut (pas de prime grande taille)',
      features: { gender: 'femme', brand: 'Denizen from Levi\'s', model: '', fit: 'Droit', size_fr: '42' },
      expected: 19
    },
    // --- Denizen / Signature homme ---
    {
      name: 'Denizen homme sans défaut',
      features: { gender: 'homme', brand: 'Denizen from Levi\'s', model: '', fit: 'Droit' },
      expected: 19
    },
    {
      name: 'Denizen homme avec défaut',
      features: { gender: 'homme', brand: 'Denizen from Levi\'s', model: '', fit: 'Droit', condition: 'satisfaisant' },
      expected: 17
    },
    {
      name: 'Denizen homme W38 sans défaut (pas de prime grande taille)',
      features: { gender: 'homme', brand: 'Denizen from Levi\'s', model: '', fit: 'Droit', size_us: 'W38' },
      expected: 19
    },
    // --- Levi's standard femme ---
    {
      name: 'Levi\'s femme standard skinny sans défaut',
      features: { gender: 'femme', brand: 'Levi\'s', model: '', fit: 'Skinny' },
      expected: 24
    },
    {
      name: 'Levi\'s femme standard droit sans défaut',
      features: { gender: 'femme', brand: 'Levi\'s', model: '', fit: 'Droit' },
      expected: 24
    },
    {
      name: 'Levi\'s femme standard évasé sans défaut',
      features: { gender: 'femme', brand: 'Levi\'s', model: '', fit: 'Évasé' },
      expected: 25
    },
    {
      name: 'Levi\'s femme standard droit FR42 sans défaut',
      features: { gender: 'femme', brand: 'Levi\'s', model: '', fit: 'Droit', size_fr: '42' },
      expected: 25
    },
    {
      name: 'Levi\'s femme standard évasé FR42 sans défaut',
      features: { gender: 'femme', brand: 'Levi\'s', model: '', fit: 'Évasé', size_fr: '42' },
      expected: 26
    },
    // --- Levi's premium femme ---
    {
      name: 'Levi\'s femme premium droit sans défaut',
      features: { gender: 'femme', brand: 'Levi\'s', model: '', fit: 'Droit', is_premium: true },
      expected: 27
    },
    {
      name: 'Levi\'s femme premium FR42 sans défaut',
      features: { gender: 'femme', brand: 'Levi\'s', model: '', fit: 'Droit', size_fr: '42', is_premium: true },
      expected: 29
    },
    // --- Levi's standard homme ---
    {
      name: 'Levi\'s homme standard skinny sans défaut',
      features: { gender: 'homme', brand: 'Levi\'s', model: '', fit: 'Skinny' },
      expected: 26
    },
    {
      name: 'Levi\'s homme standard droit sans défaut',
      features: { gender: 'homme', brand: 'Levi\'s', model: '', fit: 'Droit' },
      expected: 29
    },
    {
      name: 'Levi\'s homme standard évasé sans défaut',
      features: { gender: 'homme', brand: 'Levi\'s', model: '', fit: 'Évasé' },
      expected: 29
    },
    {
      name: 'Levi\'s homme standard W38 droit sans défaut',
      features: { gender: 'homme', brand: 'Levi\'s', model: '', fit: 'Droit', size_us: 'W38' },
      expected: 32
    },
    // --- Levi's premium homme ---
    {
      name: 'Levi\'s homme premium skinny sans défaut',
      features: { gender: 'homme', brand: 'Levi\'s', model: '', fit: 'Skinny', is_premium: true },
      expected: 29
    },
    {
      name: 'Levi\'s homme premium droit sans défaut',
      features: { gender: 'homme', brand: 'Levi\'s', model: '', fit: 'Droit', is_premium: true },
      expected: 32
    },
    {
      name: 'Levi\'s homme premium W38 droit sans défaut',
      features: { gender: 'homme', brand: 'Levi\'s', model: '', fit: 'Droit', size_us: 'W38', is_premium: true },
      expected: 35
    },
    // --- Cas critique 501 ---
    {
      name: '501 homme droit non premium → standard 29 €',
      features: { gender: 'homme', brand: 'Levi\'s', model: '501', fit: 'Droit', is_premium: false },
      expected: 29
    },
    {
      name: '501 homme droit premium explicite → 32 €',
      features: { gender: 'homme', brand: 'Levi\'s', model: '501', fit: 'Droit', is_premium: true },
      expected: 32
    },
    // --- Cas critique : Denizen + is_premium = true → budget prime ---
    {
      name: 'Denizen femme is_premium=true sans défaut → budget prime 19 €',
      features: { gender: 'femme', brand: 'Denizen from Levi\'s', model: '', fit: 'Droit', is_premium: true },
      expected: 19
    },
    {
      name: 'Denizen femme is_premium=true avec défaut → budget prime 16 €',
      features: { gender: 'femme', brand: 'Denizen from Levi\'s', model: '', fit: 'Droit', is_premium: true, condition: 'satisfaisant' },
      expected: 16
    },
    {
      name: 'Denizen homme is_premium=true avec défaut → budget prime 17 €',
      features: { gender: 'homme', brand: 'Denizen from Levi\'s', model: '', fit: 'Droit', is_premium: true, condition: 'satisfaisant' },
      expected: 17
    },
    {
      name: 'Signature homme is_premium=true sans défaut → budget prime 19 €',
      features: { gender: 'homme', brand: 'Levi\'s Signature', model: '', fit: 'Droit', is_premium: true },
      expected: 19
    },
    // --- Nouveau niveau "bon état général" : -2 € sur le prix sans défaut ---
    {
      name: 'Levi\'s homme standard droit bon état général → 27 €',
      features: { gender: 'homme', brand: 'Levi\'s', model: '', fit: 'Droit', condition: 'bon état général' },
      expected: 27
    },
    {
      name: 'Levi\'s femme standard droit bon état général → 22 €',
      features: { gender: 'femme', brand: 'Levi\'s', model: '', fit: 'Droit', condition: 'bon état général' },
      expected: 22
    },
    {
      name: 'Levi\'s femme standard évasé bon état général → 23 €',
      features: { gender: 'femme', brand: 'Levi\'s', model: '', fit: 'Évasé', condition: 'bon état général' },
      expected: 23
    },
    {
      name: 'Denizen homme bon état général → 17 € (toujours < très bon)',
      features: { gender: 'homme', brand: 'Denizen from Levi\'s', model: '', fit: 'Droit', condition: 'bon état général' },
      expected: 17
    },
    {
      name: 'Denizen femme bon état général → 17 € (toujours < très bon)',
      features: { gender: 'femme', brand: 'Denizen from Levi\'s', model: '', fit: 'Droit', condition: 'bon état général' },
      expected: 17
    },
    {
      name: 'Levi\'s homme premium droit bon état général → 30 €',
      features: { gender: 'homme', brand: 'Levi\'s', model: '', fit: 'Droit', is_premium: true, condition: 'bon état général' },
      expected: 30
    }
  ];
  var failures = [];
  for (var i = 0; i < cases.length; i++) {
    var c = cases[i];
    var result = calculateRecommendedPrice_(c.features);
    var ok = (result.price === c.expected);
    // Garde-fous : prix entier, acceptable ≤ price, floor ≤ acceptable
    var integerOk = (result.price === Math.round(result.price));
    var acceptableOk = (result.acceptable_price <= result.price);
    var floorOk = (result.floor_price <= result.acceptable_price);
    var line = '[' + (ok && integerOk && acceptableOk && floorOk ? 'OK ' : 'KO ') + '] ' +
      c.name + ' → price=' + result.price + ' (attendu ' + c.expected + ')' +
      ' acceptable=' + result.acceptable_price +
      ' floor=' + result.floor_price;
    Logger.log(line);
    if (!ok || !integerOk || !acceptableOk || !floorOk) {
      failures.push(line);
    }
  }
  Logger.log('--- Résumé ---');
  Logger.log('Total : ' + cases.length + ' / OK : ' + (cases.length - failures.length) + ' / KO : ' + failures.length);
  if (failures.length > 0) {
    throw new Error('testPricingJeanLevis_ : ' + failures.length + ' cas en échec :\n' + failures.join('\n'));
  }
  return { total: cases.length, passed: cases.length, failed: 0 };
}
