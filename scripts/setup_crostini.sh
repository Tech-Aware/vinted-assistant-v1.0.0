#!/usr/bin/env bash
# Script de préparation de l'application pour Linux Crostini (Chromebook).
# - Installe les dépendances système nécessaires (Tkinter, bibliothèques GUI)
# - Crée un environnement virtuel Python local
# - Installe les dépendances Python applicatives
#
# Journalisation détaillée et gestion d'erreurs incluse pour faciliter le support.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
VENV_PATH="${PROJECT_ROOT}/.venv"
REQUIREMENTS_FILE="${PROJECT_ROOT}/requirements.txt"

log() {
  local level="$1"; shift
  local msg="$*"
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] ${level}: ${msg}"
}

log_info() { log "INFO" "$@"; }
log_warn() { log "WARN" "$@"; }
log_error() { log "ERREUR" "$@"; }

trap 'log_error "Échec du script à la ligne ${LINENO}. Code retour: $?"' ERR

log_info "Détection de l'environnement Crostini/Chromebook."
if [[ "$(uname -s)" != "Linux" ]]; then
  log_warn "Système non Linux détecté. Ce script est optimisé pour Crostini (Debian)."
fi

if ! command -v apt-get >/dev/null 2>&1; then
  log_warn "apt-get introuvable : vérifie que tu exécutes ce script dans le conteneur Linux de ton Chromebook."
else
  SUDO_CMD=""
  if [[ $(id -u) -ne 0 ]]; then
    SUDO_CMD="sudo"
  fi

  log_info "Mise à jour des index APT..."
  ${SUDO_CMD} apt-get update -y

  log_info "Installation des paquets système essentiels (python, tk, dépendances graphiques)..."
  ${SUDO_CMD} apt-get install -y \
    python3 \
    python3-venv \
    python3-pip \
    python3-tk \
    build-essential \
    libnss3 \
    libasound2 \
    libxkbcommon-x11-0 \
    libxcb-cursor0 \
    libgl1
fi

log_info "Création de l'environnement virtuel local : ${VENV_PATH}"
python3 -m venv "${VENV_PATH}"

source "${VENV_PATH}/bin/activate"
log_info "Environnement virtuel activé. Version Python: $(python --version 2>&1)"

log_info "Mise à jour de pip..."
pip install --upgrade pip

if [[ ! -f "${REQUIREMENTS_FILE}" ]]; then
  log_error "requirements.txt introuvable dans ${PROJECT_ROOT}."
  exit 1
fi

log_info "Installation des dépendances Python de l'application..."
pip install -r "${REQUIREMENTS_FILE}"

log_info "Configuration terminée. Pense à lancer 'source ${VENV_PATH}/bin/activate' avant d'exécuter main.py."
log_info "Astuce Chromebook : garde la fenêtre Linux active pour afficher l'interface Tkinter."
