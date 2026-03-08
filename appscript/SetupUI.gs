/**
 * SetupUI.gs - Backend pour la phase de parametrage utilisateur
 *
 * Fonctions appelees depuis WebApp.html via google.script.run
 * pour la gestion des profils et des preferences utilisateur.
 */

// Note : les fonctions principales (getCurrentUserInfo, saveUserSettings,
// getUserProfilesList, getUserProfileDetail, saveUserProfile,
// deleteUserProfile, duplicateUserProfile) sont definies dans Code.gs
// car elles sont exposees directement a google.script.run.
//
// Ce fichier contient des helpers supplementaires.

/**
 * Retourne les champs (PROFILE_FIELDS) pour un profil donne.
 * Utilise le profil utilisateur si disponible, sinon le built-in.
 */
function getProfileFields(profileName) {
  var email = Session.getActiveUser().getEmail();

  // D'abord, chercher dans les profils utilisateur
  if (email) {
    var userProfile = UserStore.getProfile(email, profileName);
    if (userProfile && userProfile.fields && userProfile.fields.length > 0) {
      return userProfile.fields;
    }
  }

  // Fallback : profils par defaut
  var defaultProfile = DefaultProfiles.getByName(profileName);
  if (defaultProfile) return defaultProfile.fields;

  return [];
}

/**
 * Retourne un template de profil vierge pour la creation.
 */
function getBlankProfileTemplate() {
  return {
    profileName: '',
    label: '',
    isBuiltIn: false,
    fields: [
      {key: 'brand', label: 'Marque', type: 'text'},
      {key: 'color', label: 'Couleur', type: 'text'},
      {key: 'size', label: 'Taille', type: 'text'},
      {key: 'gender', label: 'Genre', type: 'select', options: [['', 'Auto'], ['femme', 'Femme'], ['homme', 'Homme']]},
      {key: 'condition', label: 'Etat', type: 'select', options: [['', '(non defini)'], ['tres bon etat', 'Tres bon etat'], ['bon etat', 'Bon etat'], ['neuf', 'Neuf'], ['satisfaisant', 'Satisfaisant']]},
      {key: 'sku', label: 'SKU', type: 'text'}
    ],
    titleTemplate: '{brand} {size} {color} {gender} #{sku}',
    descriptionTemplate: '{ai_description}\n\nEtat : {condition_label}\n\n📦 Envoi rapide et soigne.\n💡 Pensez a faire un lot !\n\n{hashtags}',
    promptSuffix: '',
    skuFormat: '',
    skuPrefix: '',
    hashtags: {core: [], account: ''},
    accountTag: '',
    compositionMaterials: [],
    conditionOptions: [['', '(non defini)'], ['tres bon etat', 'Tres bon etat'], ['bon etat', 'Bon etat'], ['neuf', 'Neuf'], ['satisfaisant', 'Satisfaisant']]
  };
}
