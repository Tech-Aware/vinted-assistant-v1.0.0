/**
 * Vinted Assistant - Background Service Worker
 * Gère la communication entre le popup, l'app Python et les content scripts
 */

console.log('Vinted Assistant - Service Worker démarré');

// Utilitaires pour la conversion d'images
async function blobToBase64(blob) {
  const buffer = await blob.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

function extractFilename(url, index) {
  try {
    const pathname = new URL(url).pathname;
    const parts = pathname.split('/');
    const last = parts[parts.length - 1];
    if (last && last.includes('.')) return last;
  } catch (e) { /* ignore */ }
  return `draft_photo_${index + 1}.jpg`;
}

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

  if (request.action === 'extract_photos') {
    // Extraire les photos du brouillon Vinted
    chrome.tabs.query({
      url: [
        '*://www.vinted.fr/items/*/edit*',
        '*://www.vinted.com/items/*/edit*'
      ]
    }, (tabs) => {
      if (tabs.length === 0) {
        sendResponse({
          status: 'error',
          message: 'Aucun brouillon Vinted ouvert.'
        });
        return;
      }

      chrome.tabs.sendMessage(tabs[0].id, { action: 'extract_photos' }, async (response) => {
        if (chrome.runtime.lastError) {
          sendResponse({
            status: 'error',
            message: 'Content script ne répond pas. Rechargez la page Vinted.'
          });
          return;
        }

        if (!response || response.status !== 'success' || !response.photos || response.photos.length === 0) {
          sendResponse({
            status: 'error',
            message: 'Aucune photo trouvée dans le brouillon.'
          });
          return;
        }

        try {
          const images = await Promise.all(
            response.photos.map(async (url, i) => {
              const resp = await fetch(url);
              if (!resp.ok) throw new Error(`HTTP ${resp.status} pour ${url}`);
              const blob = await resp.blob();
              const base64 = await blobToBase64(blob);
              const filename = extractFilename(url, i);
              return { data: base64, filename: filename };
            })
          );

          sendResponse({ status: 'success', images: images });
        } catch (err) {
          console.error('Erreur fetch photos brouillon:', err);
          sendResponse({
            status: 'error',
            message: 'Erreur lors du téléchargement des photos: ' + err.message
          });
        }
      });
    });

    return true; // Async response
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
