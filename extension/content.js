/**
 * Vinted Assistant - Content Script
 * Remplit automatiquement les champs titre/description et métadonnées sur Vinted
 */

class VintedFormFiller {

  constructor() {
    console.log('Vinted Assistant activé sur cette page');

    // Écouter les messages du background script
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
      if (request.action === 'fill_form') {
        this.fillAllFields(request.data)
          .then(() => sendResponse({ status: 'success' }))
          .catch((err) => sendResponse({ status: 'error', message: err.message }));
        return true; // Async response
      }
    });

    // Polling HTTP depuis l'app Python (fallback pour mode desktop)
    this.startPolling();
  }

  /**
   * Démarre le polling pour vérifier les données de l'app Python (mode desktop)
   */
  startPolling() {
    let lastErrorType = null;
    let errorCount = 0;
    let connectionVerified = false;

    setInterval(async () => {
      try {
        const response = await fetch('http://localhost:8765/check', {
          method: 'GET',
          headers: { 'Accept': 'application/json' }
        });

        if (response.ok) {
          const data = await response.json();

          if (!connectionVerified) {
            console.log('Connexion établie avec le serveur Python (localhost:8765)');
            connectionVerified = true;
            lastErrorType = null;
            errorCount = 0;
          }

          // Si des données sont présentes (mode desktop/polling)
          if (data.title || data.description) {
            console.log('Données reçues via polling');
            await this.fillAllFields(data);

            await fetch('http://localhost:8765/confirm', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' }
            });
          }
        }
      } catch (err) {
        if (lastErrorType !== 'network' || errorCount < 2) {
          errorCount = lastErrorType === 'network' ? errorCount + 1 : 1;
          lastErrorType = 'network';
        }
      }
    }, 2000);
  }

  // ----------------------------------------------------------------
  // Main fill orchestrator
  // ----------------------------------------------------------------

  /**
   * Remplit tous les champs disponibles dans le formulaire Vinted.
   */
  async fillAllFields(data) {
    console.log('Début du remplissage - champs:', Object.keys(data).filter(k => data[k]).join(', '));

    // Délai initial (simule temps de lecture)
    await this.sleep(this.randomDelay(300, 700));

    // Titre
    if (data.title) {
      const ok = await this.fillTextField([
        'input[name="title"]',
        '#title',
        'input[placeholder*="titre" i]',
        'input[placeholder*="title" i]',
      ], data.title);
      console.log(ok ? '  Titre rempli' : '  Champ titre non trouvé');
    }

    await this.sleep(this.randomDelay(800, 1500));

    // Description
    if (data.description) {
      const ok = await this.fillTextField([
        'textarea[name="description"]',
        '#description',
        'textarea[placeholder*="description" i]',
      ], data.description);
      console.log(ok ? '  Description remplie' : '  Champ description non trouvé');
    }

    await this.sleep(this.randomDelay(600, 1200));

    // Prix
    if (data.price) {
      const ok = await this.fillTextField([
        'input[name="price"]',
        'input[data-testid="price-input"]',
        'input[placeholder*="prix" i]',
        'input[placeholder*="price" i]',
        'input[type="number"][inputmode="decimal"]',
      ], String(data.price));
      console.log(ok ? `  Prix rempli: ${data.price}€` : '  Champ prix non trouvé');
    }

    await this.sleep(this.randomDelay(600, 1200));

    // Marque
    if (data.brand) {
      await this.fillBrandField(data.brand);
    }

    await this.sleep(this.randomDelay(600, 1200));

    // Taille
    if (data.size) {
      await this.fillSearchableField(data.size, [
        '[data-testid="size-input"]',
        'input[placeholder*="taille" i]',
        'input[placeholder*="size" i]',
      ], 'Taille');
    }

    await this.sleep(this.randomDelay(600, 1200));

    // État / Condition
    if (data.condition) {
      await this.fillConditionField(data.condition);
    }

    await this.sleep(this.randomDelay(600, 1200));

    // Couleur
    if (data.color) {
      await this.fillColorField(data.color);
    }

    await this.sleep(this.randomDelay(600, 1200));

    // Matériaux
    if (data.materials) {
      await this.fillSearchableField(data.materials, [
        'input[placeholder*="matière" i]',
        'input[placeholder*="material" i]',
        '[data-testid="material-input"]',
      ], 'Matériaux');
    }

    await this.sleep(this.randomDelay(400, 800));

    // Format du colis
    if (data.shipping_size) {
      await this.fillShippingField(data.shipping_size);
    }

    console.log('Remplissage terminé');
  }

  // ----------------------------------------------------------------
  // Text field filling (title, description, price)
  // ----------------------------------------------------------------

  async fillTextField(selectors, text) {
    const element = this.findElement(selectors);
    if (!element) return false;

    element.focus();
    await this.sleep(this.randomDelay(150, 300));

    await this.typeWithKeyboard(element, text);
    return true;
  }

  // ----------------------------------------------------------------
  // Brand field (autocomplete search)
  // ----------------------------------------------------------------

  async fillBrandField(brand) {
    const selectors = [
      'input[placeholder*="marque" i]',
      'input[placeholder*="brand" i]',
      '[data-testid="brand-input"]',
      '[data-testid="brand-search-input"]',
    ];

    const input = this.findElement(selectors);
    if (!input) {
      console.log('  Champ marque non trouvé');
      return;
    }

    input.focus();
    await this.sleep(this.randomDelay(200, 400));

    // Taper le nom de la marque
    await this.typeWithKeyboard(input, brand);

    // Attendre que le dropdown autocomplete apparaisse
    await this.sleep(this.randomDelay(800, 1500));

    // Essayer de cliquer la première suggestion
    const suggestion = this.findElement([
      '[data-testid="brand-suggestion"]',
      '.suggestions-list li',
      '[role="option"]',
      '[class*="suggestion"] [class*="item"]',
      'ul[class*="dropdown"] li',
      'div[class*="dropdown"] div[class*="item"]',
    ]);

    if (suggestion) {
      suggestion.click();
      console.log(`  Marque remplie: ${brand}`);
    } else {
      // Simuler Entrée pour valider
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
      console.log(`  Marque tapée: ${brand} (pas de suggestion trouvée)`);
    }
  }

  // ----------------------------------------------------------------
  // Searchable fields (size, materials)
  // ----------------------------------------------------------------

  async fillSearchableField(value, selectors, fieldName) {
    const input = this.findElement(selectors);
    if (!input) {
      console.log(`  Champ ${fieldName} non trouvé`);
      return;
    }

    input.focus();
    await this.sleep(this.randomDelay(200, 400));
    await this.typeWithKeyboard(input, value);

    // Attendre suggestions
    await this.sleep(this.randomDelay(800, 1500));

    // Cliquer la première suggestion si disponible
    const suggestion = this.findElement([
      '[role="option"]',
      'ul[class*="dropdown"] li',
      'div[class*="dropdown"] div[class*="item"]',
    ]);

    if (suggestion) {
      suggestion.click();
      console.log(`  ${fieldName} rempli: ${value}`);
    } else {
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
      console.log(`  ${fieldName} tapé: ${value} (validation par Entrée)`);
    }
  }

  // ----------------------------------------------------------------
  // Condition field (radio buttons or dropdown)
  // ----------------------------------------------------------------

  async fillConditionField(condition) {
    // Mapper les conditions vers les labels Vinted
    const conditionMap = {
      'neuf': ['neuf avec étiquette', 'neuf sans étiquette', 'neuf'],
      'très bon état': ['très bon état'],
      'bon état': ['bon état'],
      'satisfaisant': ['satisfaisant'],
    };

    const targets = conditionMap[condition.toLowerCase()] || [condition.toLowerCase()];

    // Chercher des boutons radio ou des éléments cliquables avec ce texte
    for (const target of targets) {
      // Essayer les boutons/labels qui contiennent le texte
      const allClickables = document.querySelectorAll(
        'label, button, [role="radio"], [role="option"], [data-testid*="condition"]'
      );

      for (const el of allClickables) {
        const text = (el.textContent || '').toLowerCase().trim();
        if (text.includes(target)) {
          el.click();
          await this.sleep(this.randomDelay(200, 400));
          console.log(`  État rempli: ${condition}`);
          return;
        }
      }
    }

    console.log(`  Champ état non trouvé pour: ${condition}`);
  }

  // ----------------------------------------------------------------
  // Color field (swatches or dropdown)
  // ----------------------------------------------------------------

  async fillColorField(color) {
    const colorLower = color.toLowerCase();

    // Essayer de trouver un sélecteur de couleur ou des swatches
    const allColorElements = document.querySelectorAll(
      '[data-testid*="color"], [class*="color"] label, [class*="color"] button, [role="option"]'
    );

    for (const el of allColorElements) {
      const text = (el.textContent || '').toLowerCase().trim();
      const ariaLabel = (el.getAttribute('aria-label') || '').toLowerCase();
      const title = (el.getAttribute('title') || '').toLowerCase();

      if (text.includes(colorLower) || ariaLabel.includes(colorLower) || title.includes(colorLower)) {
        el.click();
        await this.sleep(this.randomDelay(200, 400));
        console.log(`  Couleur remplie: ${color}`);
        return;
      }
    }

    // Fallback: chercher un input text pour la couleur
    const colorInput = this.findElement([
      'input[placeholder*="couleur" i]',
      'input[placeholder*="color" i]',
    ]);

    if (colorInput) {
      colorInput.focus();
      await this.sleep(this.randomDelay(150, 300));
      await this.typeWithKeyboard(colorInput, color);

      await this.sleep(this.randomDelay(500, 1000));
      const suggestion = this.findElement(['[role="option"]', 'ul[class*="dropdown"] li']);
      if (suggestion) suggestion.click();
      console.log(`  Couleur tapée: ${color}`);
    } else {
      console.log(`  Champ couleur non trouvé pour: ${color}`);
    }
  }

  // ----------------------------------------------------------------
  // Shipping / Package size field
  // ----------------------------------------------------------------

  async fillShippingField(size) {
    const sizeLower = size.toLowerCase();

    // Chercher les options de format de colis
    const allElements = document.querySelectorAll(
      'label, button, [role="radio"], [role="option"], [data-testid*="package"], [data-testid*="shipping"]'
    );

    for (const el of allElements) {
      const text = (el.textContent || '').toLowerCase().trim();
      if (text.includes(sizeLower) || text.includes('petit')) {
        el.click();
        await this.sleep(this.randomDelay(200, 400));
        console.log(`  Format colis rempli: ${size}`);
        return;
      }
    }

    console.log(`  Champ format colis non trouvé pour: ${size}`);
  }

  // ----------------------------------------------------------------
  // DOM helpers
  // ----------------------------------------------------------------

  /**
   * Trouve le premier élément visible et non-disabled parmi les sélecteurs.
   */
  findElement(selectors) {
    for (const selector of selectors) {
      try {
        const el = document.querySelector(selector);
        if (el && el.offsetParent !== null && !el.disabled) {
          return el;
        }
      } catch (e) {
        // Invalid selector, skip
      }
    }
    return null;
  }

  // ----------------------------------------------------------------
  // Keyboard simulation
  // ----------------------------------------------------------------

  /**
   * Simule la frappe au clavier avec événements natifs
   */
  async typeWithKeyboard(element, text) {
    // Clear le champ d'abord
    element.value = '';
    element.dispatchEvent(new InputEvent('input', {
      data: '',
      bubbles: true,
      cancelable: true,
      composed: true,
      inputType: 'deleteContent'
    }));

    // Taper caractère par caractère
    for (let i = 0; i < text.length; i++) {
      const char = text[i];

      element.dispatchEvent(new KeyboardEvent('keydown', {
        key: char, bubbles: true, cancelable: true, composed: true
      }));

      element.value += char;

      element.dispatchEvent(new KeyboardEvent('keypress', {
        key: char, bubbles: true, cancelable: true, composed: true
      }));

      element.dispatchEvent(new InputEvent('input', {
        data: char, bubbles: true, cancelable: true, composed: true,
        inputType: 'insertText'
      }));

      element.dispatchEvent(new KeyboardEvent('keyup', {
        key: char, bubbles: true, cancelable: true, composed: true
      }));

      // Délai entre frappes (50-120ms = vitesse humaine)
      await this.sleep(this.randomDelay(50, 120));
    }

    // Événements finaux
    element.dispatchEvent(new Event('change', { bubbles: true, cancelable: true }));
    element.dispatchEvent(new FocusEvent('blur', { bubbles: true }));
  }

  // ----------------------------------------------------------------
  // Utilities
  // ----------------------------------------------------------------

  /**
   * Génère un délai aléatoire avec distribution gaussienne
   */
  randomDelay(min, max) {
    const mean = (min + max) / 2;
    const stdDev = (max - min) / 6;

    let u = 0, v = 0;
    while (u === 0) u = Math.random();
    while (v === 0) v = Math.random();

    let num = Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
    num = num * stdDev + mean;

    return Math.max(min, Math.min(max, Math.round(num)));
  }

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// Initialiser sur les pages d'édition Vinted
if (window.location.href.match(/vinted\.(fr|com)\/items\/\d+\/edit/)) {
  console.log('Page Vinted brouillon détectée - Initialisation de l\'extension');
  new VintedFormFiller();
} else {
  console.log('Page Vinted non-brouillon - Extension en veille');
}
