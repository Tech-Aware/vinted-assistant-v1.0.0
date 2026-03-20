/**
 * Vinted Assistant - Background Service Worker
 * Gère la communication entre le popup, l'app Python et les content scripts
 */

console.log('Vinted Assistant - Service Worker démarré');

// Écouter les messages du popup et des content scripts
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log('Message reçu:', request.action);

  if (request.action === 'fill_vinted') {
    // Transmettre au content script de l'onglet Vinted actif
    chrome.tabs.query({
      url: [
        '*://www.vinted.fr/items/*/edit*',
        '*://www.vinted.com/items/*/edit*'
      ]
    }, (tabs) => {
      if (tabs.length > 0) {
        console.log('Envoi vers onglet Vinted:', tabs[0].id);

        chrome.tabs.sendMessage(tabs[0].id, {
          action: 'fill_form',
          data: request.data
        }, (response) => {
          if (chrome.runtime.lastError) {
            console.error('Erreur envoi content script:', chrome.runtime.lastError.message);
            sendResponse({
              status: 'error',
              message: 'Le content script ne répond pas. Rechargez la page Vinted.'
            });
            return;
          }
          console.log('Réponse du content script:', response);
          sendResponse(response);
        });
      } else {
        console.warn('Aucun onglet Vinted trouvé');
        sendResponse({
          status: 'error',
          message: 'Aucun brouillon Vinted ouvert. Ouvrez un brouillon dans Vinted.'
        });
      }
    });

    return true; // Indique une réponse asynchrone
  }

  if (request.action === 'check_vinted_tab') {
    // Vérifier si un onglet brouillon Vinted est ouvert
    chrome.tabs.query({
      url: [
        '*://www.vinted.fr/items/*/edit*',
        '*://www.vinted.com/items/*/edit*'
      ]
    }, (tabs) => {
      sendResponse({
        found: tabs.length > 0,
        count: tabs.length,
        tabId: tabs.length > 0 ? tabs[0].id : null,
      });
    });

    return true; // Async
  }
});

// Log quand l'extension est installée/mise à jour
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install') {
    console.log('Vinted Assistant installé avec succès');
  } else if (details.reason === 'update') {
    console.log('Vinted Assistant mis à jour vers v2.0');
  }
});
