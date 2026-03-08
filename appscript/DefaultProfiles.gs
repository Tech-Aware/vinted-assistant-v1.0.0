/**
 * DefaultProfiles.gs - Profils par defaut sous forme de donnees structurees
 *
 * Contient les 3 profils built-in (jean_levis, pull, jacket_carhart)
 * au format UserStore, prets a etre copies pour un nouvel utilisateur.
 */

var DefaultProfiles = (function() {

  var JEAN_LEVIS = {
    profileName: 'jean_levis',
    label: "Jean Levi's",
    isBuiltIn: true,
    fields: [
      {key: 'brand', label: 'Marque', type: 'text'},
      {key: 'model', label: 'Modele', type: 'text'},
      {key: 'fit', label: 'Coupe', type: 'select', options: [['', 'Auto'], ['Skinny', 'Skinny'], ['Straight/Droit', 'Droite'], ['Bootcut/\u00c9vas\u00e9', 'Evasee']]},
      {key: 'color', label: 'Couleur', type: 'text'},
      {key: 'size_fr', label: 'Taille FR', type: 'text'},
      {key: 'size_us', label: 'Taille US', type: 'text'},
      {key: 'length', label: 'Longueur', type: 'text'},
      {key: 'gender', label: 'Genre', type: 'select', options: [['', 'Auto'], ['femme', 'Femme'], ['homme', 'Homme']]},
      {key: 'rise_type', label: 'Taille (rise)', type: 'select', options: [['', 'Auto'], ['low', 'Basse'], ['mid', 'Moyenne'], ['high', 'Haute']]},
      {key: 'composition_materials', label: 'Composition', type: 'multicheck', options: ['Coton', '\u00c9lasthanne', 'Viscose', 'Lyocell', 'Polyester', 'Lin', 'Spandex', 'Nylon']},
      {key: 'is_stretch', label: 'Stretch', type: 'checkbox'},
      {key: 'is_premium', label: 'Premium', type: 'checkbox'},
      {key: 'condition', label: 'Etat', type: 'select', options: [['', '(non defini)'], ['tres bon etat', 'Tres bon etat'], ['bon etat', 'Bon etat'], ['neuf', 'Neuf'], ['satisfaisant', 'Satisfaisant']]},
      {key: 'sku', label: 'SKU', type: 'text'},
      {key: 'order_id', label: 'Order ID', type: 'text'}
    ],
    titleTemplate: 'Jean {brand} {premium} {model} {size_fr} {size_us} {length} {fit} {rise} {cotton_info} {stretch} {gender} {color} #{sku}',
    descriptionTemplate: '',
    promptSuffix: '\nSelected analysis profile: "jean_levis"\nYou MUST include the "features" object as defined in the EXTENDED OUTPUT section for jean_levis.\n\nJSON ONLY.',
    skuFormat: '[A-Z]{2,3}\\d{1,8}',
    skuPrefix: 'JLF/JLH',
    hashtags: {core: ['#vintage', '#levis', '#jeanlevis', '#jeandenim'], account: '#ladies_and_gentlemen'},
    accountTag: '#ladies_and_gentlemen',
    compositionMaterials: ['Coton', '\u00c9lasthanne', 'Viscose', 'Lyocell', 'Polyester', 'Lin', 'Spandex', 'Nylon'],
    conditionOptions: [['', '(non defini)'], ['tres bon etat', 'Tres bon etat'], ['bon etat', 'Bon etat'], ['neuf', 'Neuf'], ['satisfaisant', 'Satisfaisant']]
  };

  var PULL = {
    profileName: 'pull',
    label: 'Pull / Gilet',
    isBuiltIn: true,
    fields: [
      {key: 'brand', label: 'Marque', type: 'text'},
      {key: 'garment_type', label: 'Type', type: 'select', options: [['Pull', 'Pull'], ['Gilet', 'Gilet']]},
      {key: 'neckline', label: 'Col', type: 'text'},
      {key: 'pattern', label: 'Motif', type: 'text'},
      {key: 'material', label: 'Matiere', type: 'text'},
      {key: 'main_colors', label: 'Couleurs', type: 'text', isArray: true},
      {key: 'gender', label: 'Genre', type: 'select', options: [['', 'Auto'], ['femme', 'Femme'], ['homme', 'Homme']]},
      {key: 'size', label: 'Taille', type: 'text'},
      {key: 'cotton_percent', label: 'Coton %', type: 'number'},
      {key: 'wool_percent', label: 'Laine %', type: 'number'},
      {key: 'is_premium', label: 'Premium', type: 'checkbox'},
      {key: 'condition', label: 'Etat', type: 'select', options: [['', '(non defini)'], ['tres bon etat', 'Tres bon etat'], ['bon etat', 'Bon etat'], ['neuf', 'Neuf'], ['satisfaisant', 'Satisfaisant']]},
      {key: 'sku', label: 'SKU', type: 'text'},
      {key: 'order_id', label: 'Order ID', type: 'text'}
    ],
    titleTemplate: '{garment_type} {vintage} {brand} {premium} {gender} taille {size} {material} {colors} {pattern} {neckline} #{sku}',
    descriptionTemplate: '',
    promptSuffix: '\nSelected analysis profile: "pull"\nYou MUST include the "features" object as defined in the EXTENDED OUTPUT section for pull.\n\nJSON ONLY.',
    skuFormat: '[A-Z]{2,4}\\d{1,8}',
    skuPrefix: 'PTF/PTH',
    hashtags: {core: ['#tommyhilfiger', '#pulltommy', '#tommy', '#mode', '#preloved'], account: '#durin31tf'},
    accountTag: '#durin31tf',
    compositionMaterials: [],
    conditionOptions: [['', '(non defini)'], ['tres bon etat', 'Tres bon etat'], ['bon etat', 'Bon etat'], ['neuf', 'Neuf'], ['satisfaisant', 'Satisfaisant']]
  };

  var JACKET_CARHART = {
    profileName: 'jacket_carhart',
    label: 'Veste Carhartt',
    isBuiltIn: true,
    fields: [
      {key: 'brand', label: 'Marque', type: 'text'},
      {key: 'model', label: 'Modele', type: 'text'},
      {key: 'size', label: 'Taille', type: 'text'},
      {key: 'color', label: 'Couleur', type: 'text'},
      {key: 'gender', label: 'Genre', type: 'select', options: [['', 'Auto'], ['femme', 'Femme'], ['homme', 'Homme']]},
      {key: 'has_hood', label: 'Capuche', type: 'checkbox'},
      {key: 'lining', label: 'Doublure', type: 'text'},
      {key: 'pattern', label: 'Motif', type: 'text'},
      {key: 'is_premium', label: 'Premium', type: 'checkbox'},
      {key: 'condition', label: 'Etat', type: 'select', options: [['', '(non defini)'], ['tres bon etat', 'Tres bon etat'], ['bon etat', 'Bon etat'], ['neuf', 'Neuf'], ['satisfaisant', 'Satisfaisant']]},
      {key: 'sku', label: 'SKU', type: 'text'},
      {key: 'order_id', label: 'Order ID', type: 'text'}
    ],
    titleTemplate: 'Veste {hood} Carhartt {premium} {brand} {model} taille {size} couleur {color} {camo} {gender} #{sku}',
    descriptionTemplate: '',
    promptSuffix: '\nSelected analysis profile: "jacket_carhart"\nYou MUST include the "features" object as defined in the EXTENDED OUTPUT section for jacket_carhart.\n\nJSON ONLY.',
    skuFormat: 'JCR\\d{1,8}',
    skuPrefix: 'JCR',
    hashtags: {core: ['#carhartt', '#jacket', '#workwear', '#durin31'], account: '#durin31jc'},
    accountTag: '#durin31jc',
    compositionMaterials: [],
    conditionOptions: [['', '(non defini)'], ['tres bon etat', 'Tres bon etat'], ['bon etat', 'Bon etat'], ['neuf', 'Neuf'], ['satisfaisant', 'Satisfaisant']]
  };

  return {
    JEAN_LEVIS: JEAN_LEVIS,
    PULL: PULL,
    JACKET_CARHART: JACKET_CARHART,

    getAll: function() {
      return [
        JSON.parse(JSON.stringify(JEAN_LEVIS)),
        JSON.parse(JSON.stringify(PULL)),
        JSON.parse(JSON.stringify(JACKET_CARHART))
      ];
    },

    getByName: function(name) {
      if (name === 'jean_levis') return JSON.parse(JSON.stringify(JEAN_LEVIS));
      if (name === 'pull') return JSON.parse(JSON.stringify(PULL));
      if (name === 'jacket_carhart') return JSON.parse(JSON.stringify(JACKET_CARHART));
      return null;
    }
  };

})();
