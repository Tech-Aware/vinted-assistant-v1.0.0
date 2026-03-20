/**
 * Vinted Assistant - Extension Popup
 * Interface principale pour générer et remplir les annonces Vinted.
 * Extrait automatiquement les photos du brouillon Vinted.
 */

const API_BASE = 'http://localhost:8765';

// State
let images = []; // [{data: "base64...", filename: "name.jpg", objectUrl: "blob:..."}]
let lastResult = null;

// DOM elements
const statusDot = document.getElementById('status-dot');
const profileSelect = document.getElementById('profile-select');
const fieldsSection = document.getElementById('fields-section');
const btnGenerate = document.getElementById('btn-generate');
const btnGenerateText = document.getElementById('btn-generate-text');
const btnGenerateSpinner = document.getElementById('btn-generate-spinner');
const statusMessage = document.getElementById('status-message');
const resultsSection = document.getElementById('results-section');
const resultTitle = document.getElementById('result-title');
const resultDescription = document.getElementById('result-description');
const btnFill = document.getElementById('btn-fill');
const btnCopyTitle = document.getElementById('btn-copy-title');
const btnCopyDesc = document.getElementById('btn-copy-desc');

// Correction fields
const editBrand = document.getElementById('edit-brand');
const editSize = document.getElementById('edit-size');
const editCondition = document.getElementById('edit-condition');
const editColor = document.getElementById('edit-color');
const editMaterials = document.getElementById('edit-materials');

// Manual upload fallback
const toggleManualUpload = document.getElementById('toggle-manual-upload');
const manualUploadSection = document.getElementById('manual-upload-section');
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const thumbnails = document.getElementById('thumbnails');

// ----------------------------------------------------------------
// Initialization
// ----------------------------------------------------------------

document.addEventListener('DOMContentLoaded', async () => {
  await checkConnection();
  await loadProfiles();
  setupEventListeners();
});

async function checkConnection() {
  try {
    const resp = await fetch(`${API_BASE}/status`, { signal: AbortSignal.timeout(3000) });
    if (resp.ok) {
      statusDot.classList.remove('offline');
      statusDot.classList.add('online');
      statusDot.title = 'Connecté au serveur Python';
      return true;
    }
  } catch (e) { /* ignore */ }
  statusDot.classList.remove('online');
  statusDot.classList.add('offline');
  statusDot.title = 'Serveur Python non détecté (python main.py --headless)';
  setStatus('Serveur Python non détecté. Lancez: python main.py --headless', 'error');
  return false;
}

async function loadProfiles() {
  try {
    const resp = await fetch(`${API_BASE}/profiles`, { signal: AbortSignal.timeout(3000) });
    if (!resp.ok) return;
    const data = await resp.json();
    for (const p of data.profiles) {
      const opt = document.createElement('option');
      opt.value = p.name;
      opt.textContent = p.label;
      profileSelect.appendChild(opt);
    }
  } catch (e) {
    console.warn('Impossible de charger les profils:', e);
  }
}

// ----------------------------------------------------------------
// Event Listeners
// ----------------------------------------------------------------

function setupEventListeners() {
  // Profile change
  profileSelect.addEventListener('change', onProfileChange);

  // Manual upload toggle
  toggleManualUpload.addEventListener('click', (e) => {
    e.preventDefault();
    const isHidden = manualUploadSection.hidden;
    manualUploadSection.hidden = !isHidden;
    toggleManualUpload.textContent = isHidden
      ? 'masquer l\'upload manuel'
      : 'ou charger des photos manuellement';
  });

  // Image upload (fallback)
  document.getElementById('btn-add-images').addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', (e) => addFiles(e.target.files));

  // Drag & drop (fallback)
  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
  });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    addFiles(e.dataTransfer.files);
  });

  // Generate
  btnGenerate.addEventListener('click', onGenerate);

  // Apply corrections
  btnFill.addEventListener('click', onFillVinted);

  // Copy buttons
  btnCopyTitle.addEventListener('click', () => copyToClipboard(resultTitle.value, 'Titre copié'));
  btnCopyDesc.addEventListener('click', () => copyToClipboard(resultDescription.value, 'Description copiée'));
}

// ----------------------------------------------------------------
// Profile handling
// ----------------------------------------------------------------

function onProfileChange() {
  const profile = profileSelect.value;

  // Hide all profile fields
  document.querySelectorAll('.profile-fields').forEach(el => el.hidden = true);

  if (!profile) {
    fieldsSection.hidden = true;
    updateGenerateButton();
    return;
  }

  fieldsSection.hidden = false;

  // Show relevant profile fields
  const fieldDiv = document.getElementById(`fields-${profile}`);
  if (fieldDiv) fieldDiv.hidden = false;

  updateGenerateButton();
}

// ----------------------------------------------------------------
// Image handling (fallback manuel)
// ----------------------------------------------------------------

function addFiles(fileList) {
  for (const file of fileList) {
    if (!file.type.startsWith('image/')) continue;

    const reader = new FileReader();
    reader.onload = (e) => {
      const dataUrl = e.target.result;
      const base64 = dataUrl.split(',')[1];
      const objectUrl = URL.createObjectURL(file);

      images.push({
        data: base64,
        filename: file.name,
        objectUrl: objectUrl,
      });

      renderThumbnails();
      updateGenerateButton();
    };
    reader.readAsDataURL(file);
  }
  fileInput.value = '';
}

function removeImage(index) {
  const img = images[index];
  if (img.objectUrl) URL.revokeObjectURL(img.objectUrl);
  images.splice(index, 1);
  renderThumbnails();
  updateGenerateButton();
}

function renderThumbnails() {
  thumbnails.innerHTML = '';
  images.forEach((img, i) => {
    const div = document.createElement('div');
    div.className = 'thumb';

    const imgEl = document.createElement('img');
    imgEl.src = img.objectUrl;
    imgEl.alt = img.filename;

    const btn = document.createElement('button');
    btn.className = 'thumb__remove';
    btn.textContent = '\u00d7';
    btn.addEventListener('click', () => removeImage(i));

    div.appendChild(imgEl);
    div.appendChild(btn);
    thumbnails.appendChild(div);
  });
}

// ----------------------------------------------------------------
// Photo extraction from draft
// ----------------------------------------------------------------

async function extractPhotosFromDraft() {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ action: 'extract_photos' }, (response) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
        return;
      }
      if (!response || response.status !== 'success') {
        reject(new Error(response?.message || 'Erreur lors de l\'extraction des photos.'));
        return;
      }
      resolve(response.images);
    });
  });
}

// ----------------------------------------------------------------
// Generate
// ----------------------------------------------------------------

function updateGenerateButton() {
  const hasProfile = profileSelect.value !== '';
  // On n'exige plus d'images : elles seront extraites automatiquement du brouillon
  btnGenerate.disabled = !hasProfile;
}

function collectUiData() {
  const profile = profileSelect.value;
  const data = {};

  data.order_id = document.getElementById('order_id').value.trim() || null;
  data.has_defect = document.getElementById('has_defect').checked;

  if (profile === 'jean_levis') {
    data.size_fr = document.getElementById('size_fr').value.trim() || null;
    data.size_us = document.getElementById('size_us').value.trim() || null;
    data.length = document.getElementById('length').value.trim() || null;
    data.fit = document.getElementById('fit').value || null;
    data.rise_type = document.getElementById('rise_type').value || null;
    data.composition = document.getElementById('composition').value.trim() || null;
  } else if (profile === 'pull') {
    data.measurement_mode = document.getElementById('measurement_mode_pull').value;
  } else if (profile === 'jacket_carhart') {
    data.size_fr = document.getElementById('jk_size_fr').value.trim() || null;
    data.size_us = document.getElementById('jk_size_us').value.trim() || null;
    data.length = document.getElementById('jk_length').value.trim() || null;
    data.composition = document.getElementById('jk_composition').value.trim() || null;
  } else if (profile === 'polaire_outdoor') {
    data.measurement_mode = document.getElementById('measurement_mode_polaire').value;
  }

  return data;
}

async function onGenerate() {
  const profile = profileSelect.value;
  if (!profile) {
    setStatus('Sélectionnez un profil.', 'error');
    return;
  }

  // Jean Levi's requires size_fr
  if (profile === 'jean_levis') {
    const sizeFr = document.getElementById('size_fr').value.trim();
    if (!sizeFr) {
      setStatus('Taille FR requise pour un jean Levi\'s.', 'error');
      return;
    }
  }

  // Check connection first
  const connected = await checkConnection();
  if (!connected) return;

  // UI loading state
  btnGenerate.disabled = true;
  btnGenerateText.textContent = 'Analyse en cours...';
  btnGenerateSpinner.hidden = false;
  resultsSection.hidden = true;
  setStatus('', '');

  try {
    // Step 1: Get images (manual or auto-extract from draft)
    let imageList;
    if (images.length > 0) {
      // Utiliser les images chargées manuellement
      imageList = images.map(img => ({ data: img.data, filename: img.filename }));
      setStatus('Utilisation des photos chargées manuellement...', '');
    } else {
      // Extraire automatiquement les photos du brouillon
      setStatus('Extraction des photos du brouillon...', '');
      try {
        const extractedImages = await extractPhotosFromDraft();
        if (!extractedImages || extractedImages.length === 0) {
          setStatus('Aucune photo trouvée dans le brouillon Vinted.', 'error');
          return;
        }
        imageList = extractedImages;
        setStatus(`${imageList.length} photo(s) extraite(s). Analyse IA en cours...`, '');
      } catch (extractErr) {
        setStatus('Erreur: ' + extractErr.message, 'error');
        return;
      }
    }

    // Step 2: Send to backend for analysis
    setStatus('Analyse IA en cours... (10-30 secondes)', '');
    const uiData = collectUiData();
    const body = {
      images: imageList,
      profile: profile,
      ui_data: uiData,
    };

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 120000);

    const resp = await fetch(`${API_BASE}/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    clearTimeout(timeout);

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ error: `HTTP ${resp.status}` }));
      throw new Error(err.error || `Erreur serveur (${resp.status})`);
    }

    lastResult = await resp.json();
    displayResults(lastResult);
    setStatus(`Terminé en ${lastResult.generation_time_s || '?'}s — remplissage auto...`, 'success');

    // Step 3: Auto-fill the Vinted draft
    await autoFillVinted();

  } catch (err) {
    if (err.name === 'AbortError') {
      setStatus('Timeout: la génération a pris trop de temps.', 'error');
    } else {
      setStatus(`Erreur: ${err.message}`, 'error');
    }
    console.error('Generate error:', err);
  } finally {
    btnGenerate.disabled = false;
    btnGenerateText.textContent = 'Générer';
    btnGenerateSpinner.hidden = true;
  }
}

// ----------------------------------------------------------------
// Results display (correction panel)
// ----------------------------------------------------------------

function displayResults(data) {
  resultTitle.value = data.title || '';
  resultDescription.value = data.description || '';

  // Remplir les champs de correction éditables
  editBrand.value = data.brand || '';
  editSize.value = data.size || '';
  editColor.value = data.color || '';
  editMaterials.value = data.materials || '';

  // Mapper la condition vers la valeur du select
  if (data.condition) {
    const conditionLower = data.condition.toLowerCase();
    const options = editCondition.options;
    for (let i = 0; i < options.length; i++) {
      if (options[i].value.toLowerCase() === conditionLower) {
        editCondition.selectedIndex = i;
        break;
      }
    }
  }

  // Prix conseillé et prix neuf
  const priceInfo = document.getElementById('price-info');
  const recommendedPrice = document.getElementById('recommended-price');
  const retailPrice = document.getElementById('retail-price');
  if (data.recommended_price) {
    recommendedPrice.textContent = `${data.recommended_price}€`;
    retailPrice.textContent = data.retail_price_range || '';
    priceInfo.hidden = false;
  } else {
    priceInfo.hidden = true;
  }

  // Meta tags
  setMetaTag('meta-time', data.generation_time_s ? `${data.generation_time_s}s` : null);

  resultsSection.hidden = false;
}

function setMetaTag(id, value) {
  const el = document.getElementById(id);
  if (value) {
    el.textContent = value;
    el.hidden = false;
  } else {
    el.hidden = true;
  }
}

// ----------------------------------------------------------------
// Fill / Apply corrections to Vinted form
// ----------------------------------------------------------------

function collectCorrectionData() {
  return {
    title: resultTitle.value,
    description: resultDescription.value,
    brand: editBrand.value,
    size: editSize.value,
    condition: editCondition.value,
    color: editColor.value,
    materials: editMaterials.value,
    price: lastResult?.price || parseInt(document.getElementById('price').value) || 24,
    shipping_size: lastResult?.shipping_size || 'Petit',
  };
}

async function autoFillVinted() {
  if (!lastResult) return;

  const data = collectCorrectionData();

  try {
    await sendFillMessage(data);
    setStatus(`Terminé en ${lastResult.generation_time_s || '?'}s — brouillon rempli !`, 'success');
  } catch (err) {
    setStatus(`Analyse terminée. Erreur remplissage: ${err.message}`, 'error');
  }
}

async function onFillVinted() {
  const data = collectCorrectionData();

  try {
    btnFill.disabled = true;
    btnFill.textContent = 'Application...';
    await sendFillMessage(data);
    setStatus('Corrections appliquées !', 'success');
    btnFill.textContent = 'Appliqué !';
    btnFill.style.background = '#22c55e';
    setTimeout(() => {
      btnFill.textContent = 'Appliquer les corrections';
      btnFill.style.background = '';
    }, 3000);
  } catch (err) {
    setStatus('Erreur: ' + err.message, 'error');
  } finally {
    btnFill.disabled = false;
  }
}

function sendFillMessage(data) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ action: 'fill_vinted', data: data }, (response) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
        return;
      }
      if (response && response.status === 'success') {
        resolve();
      } else {
        reject(new Error(response?.message || 'Aucun brouillon Vinted ouvert.'));
      }
    });
  });
}

// ----------------------------------------------------------------
// Utilities
// ----------------------------------------------------------------

function setStatus(text, type) {
  statusMessage.textContent = text;
  statusMessage.className = 'status-message' + (type ? ` ${type}` : '');
}

function copyToClipboard(text, successMsg) {
  navigator.clipboard.writeText(text).then(() => {
    setStatus(successMsg, 'success');
    setTimeout(() => setStatus('', ''), 2000);
  }).catch(() => {
    setStatus('Erreur de copie.', 'error');
  });
}
