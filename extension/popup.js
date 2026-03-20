/**
 * Vinted Assistant - Extension Popup
 * Interface principale pour générer et remplir les annonces Vinted.
 */

const API_BASE = 'http://localhost:8765';

// State
let images = []; // [{data: "base64...", filename: "name.jpg", objectUrl: "blob:..."}]
let lastResult = null;

// DOM elements
const statusDot = document.getElementById('status-dot');
const profileSelect = document.getElementById('profile-select');
const fieldsSection = document.getElementById('fields-section');
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const thumbnails = document.getElementById('thumbnails');
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

  // Image upload
  document.getElementById('btn-add-images').addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', (e) => addFiles(e.target.files));

  // Drag & drop
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

  // Fill Vinted
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
// Image handling
// ----------------------------------------------------------------

function addFiles(fileList) {
  for (const file of fileList) {
    if (!file.type.startsWith('image/')) continue;

    const reader = new FileReader();
    reader.onload = (e) => {
      const dataUrl = e.target.result;
      // Strip data URI prefix to get pure base64
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
  // Reset file input so same file can be re-added
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
// Generate
// ----------------------------------------------------------------

function updateGenerateButton() {
  const hasImages = images.length > 0;
  const hasProfile = profileSelect.value !== '';
  btnGenerate.disabled = !(hasImages && hasProfile);
}

function collectUiData() {
  const profile = profileSelect.value;
  const data = {};

  data.order_id = document.getElementById('order_id').value.trim() || null;
  data.has_defect = document.getElementById('has_defect').checked;
  data.price = parseInt(document.getElementById('price').value) || 24;

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
  // Validate
  if (images.length === 0) {
    setStatus('Ajoutez au moins une image.', 'error');
    return;
  }

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

  // Build request
  const uiData = collectUiData();
  const body = {
    images: images.map(img => ({ data: img.data, filename: img.filename })),
    profile: profile,
    ui_data: uiData,
  };

  // UI loading state
  btnGenerate.disabled = true;
  btnGenerateText.textContent = 'Analyse en cours...';
  btnGenerateSpinner.hidden = false;
  resultsSection.hidden = true;
  setStatus('Analyse IA en cours... (10-30 secondes)', '');

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 120000); // 2 min timeout

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
    setStatus(`Terminé en ${lastResult.generation_time_s || '?'}s`, 'success');

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
// Results display
// ----------------------------------------------------------------

function displayResults(data) {
  resultTitle.value = data.title || '';
  resultDescription.value = data.description || '';

  // Meta tags
  setMetaTag('meta-brand', data.brand);
  setMetaTag('meta-size', data.size);
  setMetaTag('meta-condition', data.condition);
  setMetaTag('meta-color', data.color);
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
// Fill Vinted form
// ----------------------------------------------------------------

async function onFillVinted() {
  if (!lastResult) {
    setStatus('Aucun résultat à envoyer.', 'error');
    return;
  }

  // Use the editable text (user may have modified)
  const data = {
    title: resultTitle.value,
    description: resultDescription.value,
    brand: lastResult.brand,
    size: lastResult.size,
    condition: lastResult.condition,
    color: lastResult.color,
    materials: lastResult.materials,
    price: lastResult.price || parseInt(document.getElementById('price').value) || 24,
    shipping_size: lastResult.shipping_size || 'Petit',
  };

  try {
    chrome.runtime.sendMessage({ action: 'fill_vinted', data: data }, (response) => {
      if (chrome.runtime.lastError) {
        setStatus('Erreur: ' + chrome.runtime.lastError.message, 'error');
        return;
      }
      if (response && response.status === 'success') {
        setStatus('Brouillon Vinted rempli !', 'success');
        btnFill.textContent = 'Rempli !';
        btnFill.style.background = '#22c55e';
        setTimeout(() => {
          btnFill.textContent = 'Remplir le brouillon Vinted';
          btnFill.style.background = '';
        }, 3000);
      } else if (response && response.status === 'error') {
        setStatus('Erreur: ' + (response.message || 'Aucun brouillon Vinted ouvert.'), 'error');
      }
    });
  } catch (err) {
    setStatus('Erreur extension: ' + err.message, 'error');
  }
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
