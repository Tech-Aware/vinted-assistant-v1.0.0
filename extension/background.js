/**
 * Vinted Assistant - Background Service Worker
 * Gère la communication entre l'app Python et les content scripts
 */

console.log('🟢 Vinted Assistant - Service Worker démarré');

// Écouter les messages (pour communication future si nécessaire)
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log('📨 Message reçu:', request);

  if (request.action === 'fill_vinted') {
    // Transmettre au content script de l'onglet Vinted actif
    chrome.tabs.query({
      url: [
        '*://www.vinted.fr/items/*/edit*',
        '*://www.vinted.com/items/*/edit*'
      ]
    }, (tabs) => {
      if (tabs.length > 0) {
        console.log('📤 Envoi vers onglet Vinted:', tabs[0].id);

        chrome.tabs.sendMessage(tabs[0].id, {
          action: 'fill_form',
          data: request.data
        }, (response) => {
          console.log('📥 Réponse du content script:', response);
          sendResponse(response);
        });
      } else {
        console.warn('⚠️ Aucun onglet Vinted trouvé');
        sendResponse({
          status: 'error',
          message: 'Aucun brouillon Vinted ouvert. Ouvrez un brouillon dans Vinted.'
        });
      }
    });

    return true; // Indique une réponse asynchrone
  }
});

// Log quand l'extension est installée/mise à jour
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install') {
    console.log('✅ Vinted Assistant installé avec succès');
  } else if (details.reason === 'update') {
    console.log('🔄 Vinted Assistant mis à jour');
  }
});
