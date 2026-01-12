/**
 * Vinted Assistant - Content Script
 * Remplit automatiquement les champs titre/description sur Vinted
 */

class VintedFormFiller {

  constructor() {
    console.log('🟢 Vinted Assistant activé sur cette page');

    // Écouter les messages du background script
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
      if (request.action === 'fill_form') {
        this.fillFormSafely(request.data)
          .then(() => sendResponse({ status: 'success' }))
          .catch((err) => sendResponse({ status: 'error', message: err.message }));
        return true; // Async response
      }
    });

    // Polling HTTP depuis l'app Python (méthode principale pour Chromebook)
    this.startPolling();
  }

  /**
   * Démarre le polling pour vérifier les données de l'app Python
   */
  startPolling() {
    console.log('🔄 Polling démarré - vérification toutes les 2 secondes');

    // Variable pour tracer les erreurs (éviter spam mais afficher les erreurs importantes)
    let lastErrorType = null;
    let errorCount = 0;
    let connectionVerified = false;

    setInterval(async () => {
      try {
        const response = await fetch('http://localhost:8765/check', {
          method: 'GET',
          headers: {
            'Accept': 'application/json'
          }
        });

        if (response.ok) {
          const data = await response.json();

          // Première connexion réussie
          if (!connectionVerified) {
            console.log('✅ Connexion établie avec le serveur Python (localhost:8765)');
            connectionVerified = true;
            lastErrorType = null;
            errorCount = 0;
          }

          // Si des données sont présentes
          if (data.title || data.description) {
            console.log('📥 Données reçues de l\'app Python');
            await this.fillFormSafely(data);

            // Confirmer à l'app Python que le remplissage est terminé
            await fetch('http://localhost:8765/confirm', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json'
              }
            });

            console.log('✅ Confirmation envoyée à l\'app Python');
          }
        } else {
          // Erreur HTTP (4xx, 5xx)
          if (lastErrorType !== 'http' || errorCount < 3) {
            console.error(`❌ Erreur HTTP ${response.status}: ${response.statusText}`);
            console.error('   Vérifiez que le serveur Python est démarré sur le port 8765');
            errorCount = lastErrorType === 'http' ? errorCount + 1 : 1;
            lastErrorType = 'http';
          }
        }
      } catch (err) {
        // Erreur réseau (serveur non accessible, CORS, etc.)
        if (lastErrorType !== 'network' || errorCount < 3) {
          console.error('❌ Erreur de connexion au serveur Python:', err.message);
          console.error('   → Type d\'erreur:', err.name);

          // Messages d'aide selon le type d'erreur
          if (err.name === 'TypeError' && err.message.includes('Failed to fetch')) {
            console.error('   ⚠️  CAUSES POSSIBLES:');
            console.error('      1. Le serveur Python n\'est PAS démarré');
            console.error('      2. Le port forwarding n\'est PAS configuré (ChromeOS → Linux → Port 8765)');
            console.error('      3. Le serveur écoute sur un AUTRE port que 8765');
            console.error('   📋 ACTIONS À FAIRE:');
            console.error('      → Vérifiez la console Python: doit afficher "Serveur HTTP démarré"');
            console.error('      → Chromebook: Paramètres → Linux → Port forwarding → Ajouter port 8765 (TCP)');
            console.error('      → Testez dans un autre onglet: http://localhost:8765/status');
          } else if (err.message.includes('NetworkError') || err.message.includes('blocked')) {
            console.error('   ⚠️  L\'extension est peut-être bloquée par le navigateur');
            console.error('      → Vérifiez chrome://extensions/ - l\'extension doit être ACTIVÉE');
          }

          errorCount = lastErrorType === 'network' ? errorCount + 1 : 1;
          lastErrorType = 'network';
        }
      }
    }, 2000); // Vérifier toutes les 2 secondes
  }

  /**
   * Remplit le formulaire Vinted de manière sécurisée
   */
  async fillFormSafely(data) {
    console.log('🔵 Début du remplissage sécurisé');
    console.log('   Titre:', data.title?.substring(0, 50) + '...');
    console.log('   Description:', data.description?.substring(0, 50) + '...');

    // Délai initial aléatoire (simule temps de lecture)
    await this.sleep(this.randomDelay(500, 1000));

    // Remplir titre
    if (data.title) {
      const titleFilled = await this.fillField([
        'input[name="title"]',
        '#title',
        'input[placeholder*="titre" i]',
        'input[placeholder*="title" i]'
      ], data.title);

      if (titleFilled) {
        console.log('   ✅ Titre rempli');
      } else {
        console.warn('   ⚠️ Champ titre non trouvé');
      }
    }

    // Délai entre titre et description (simule comportement humain)
    await this.sleep(this.randomDelay(1500, 3000));

    // Remplir description
    if (data.description) {
      const descriptionFilled = await this.fillField([
        'textarea[name="description"]',
        '#description',
        'textarea[placeholder*="description" i]'
      ], data.description);

      if (descriptionFilled) {
        console.log('   ✅ Description remplie');
      } else {
        console.warn('   ⚠️ Champ description non trouvé');
      }
    }

    console.log('✅ Remplissage terminé');
  }

  /**
   * Remplit un champ avec simulation de frappe naturelle
   * @param {string|string[]} selectors - Un ou plusieurs sélecteurs CSS
   * @param {string} text - Texte à insérer
   * @returns {boolean} - True si le champ a été trouvé et rempli
   */
  async fillField(selectors, text) {
    // Supporter un seul sélecteur ou un tableau
    const selectorArray = Array.isArray(selectors) ? selectors : [selectors];

    // Essayer chaque sélecteur jusqu'à trouver l'élément
    let element = null;
    let usedSelector = null;
    for (const selector of selectorArray) {
      const el = document.querySelector(selector);
      // Vérifier que l'élément existe ET est visible
      if (el && el.offsetParent !== null && !el.disabled) {
        element = el;
        usedSelector = selector;
        break;
      }
    }

    if (!element) {
      console.error('❌ ERREUR CRITIQUE: Champ non trouvé ou invisible');
      console.error('   Les sélecteurs Vinted ont peut-être changé');
      console.error('   Sélecteurs testés:', selectorArray);
      console.error('   💡 SOLUTION: Vérifiez la console et signalez le problème');
      return false;
    }

    console.log('   ✓ Champ trouvé avec sélecteur:', usedSelector);

    // Focus avec délai naturel
    element.focus();
    await this.sleep(this.randomDelay(200, 400));

    // Simulation de frappe au clavier caractère par caractère
    await this.typeWithKeyboard(element, text);

    return true;
  }

  /**
   * Simule la frappe au clavier avec événements natifs
   */
  async typeWithKeyboard(element, text) {
    // Clear le champ d'abord
    element.value = '';

    // Taper caractère par caractère
    for (let i = 0; i < text.length; i++) {
      const char = text[i];

      // Événement keydown
      element.dispatchEvent(new KeyboardEvent('keydown', {
        key: char,
        bubbles: true,
        cancelable: true,
        composed: true
      }));

      // Ajouter le caractère
      element.value += char;

      // Événement keypress
      element.dispatchEvent(new KeyboardEvent('keypress', {
        key: char,
        bubbles: true,
        cancelable: true,
        composed: true
      }));

      // Événement input (le plus important pour les frameworks modernes)
      element.dispatchEvent(new InputEvent('input', {
        data: char,
        bubbles: true,
        cancelable: true,
        composed: true,
        inputType: 'insertText'
      }));

      // Événement keyup
      element.dispatchEvent(new KeyboardEvent('keyup', {
        key: char,
        bubbles: true,
        cancelable: true,
        composed: true
      }));

      // Délai entre frappes (50-120ms = vitesse humaine réaliste)
      await this.sleep(this.randomDelay(50, 120));
    }

    // Événements finaux
    element.dispatchEvent(new Event('change', {
      bubbles: true,
      cancelable: true
    }));

    element.dispatchEvent(new FocusEvent('blur', {
      bubbles: true
    }));
  }

  /**
   * Génère un délai aléatoire avec distribution gaussienne (plus naturel)
   */
  randomDelay(min, max) {
    const mean = (min + max) / 2;
    const stdDev = (max - min) / 6;

    // Box-Muller transform pour distribution normale
    let u = 0, v = 0;
    while(u === 0) u = Math.random();
    while(v === 0) v = Math.random();

    let num = Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
    num = num * stdDev + mean;

    // Contraindre dans l'intervalle [min, max]
    return Math.max(min, Math.min(max, Math.round(num)));
  }

  /**
   * Utilitaire sleep
   */
  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// Initialiser uniquement sur les pages d'édition Vinted
// Vérification stricte du pattern d'édition de brouillon: /items/{id}/edit
if (window.location.href.match(/vinted\.(fr|com)\/items\/\d+\/edit/)) {
  console.log('✅ Page Vinted brouillon détectée - Initialisation de l\'extension');
  new VintedFormFiller();
} else {
  console.log('⏸️ Page Vinted non-brouillon - Extension en veille');
}
