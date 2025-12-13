# presentation/ui_app.py

from __future__ import annotations

import logging
from pathlib import Path
import os
from typing import Dict, List, Optional

from PIL import Image  # encore utilisé pour l’aperçu plein écran si tu le gardes ailleurs

import customtkinter as ctk
from tkinter import filedialog, messagebox

from domain.ai_provider import AIProviderName, AIListingProvider
from domain.models import VintedListing
from domain.templates import AnalysisProfileName, AnalysisProfile, ALL_PROFILES
from domain.title_builder import SKU_PREFIX

from .image_preview import ImagePreview  # <- widget réutilisé depuis l’ancienne app

logger = logging.getLogger(__name__)


class VintedAIApp(ctk.CTk):
    """
    UI principale de l'assistant Vinted.

    ÉTAPE 1 :
    - choix provider IA
    - choix profil d'analyse
    - sélection d'images
    - inputs manuels size_fr + size_us
    - generate_listing() avec ui_data minimal

    Pas encore de SKU UI.
    Pas encore de missing/low-confidence.
    """

    def __init__(self, providers: Dict[AIProviderName, AIListingProvider]) -> None:
        super().__init__()

        self.title("Assistant Vinted - Analyse d'images multi-IA")
        self.geometry("900x600")
        self.minsize(720, 520)

        self.providers = providers
        self.provider_var = ctk.StringVar(value="")
        self.provider_var.trace_add("write", self._on_provider_change)
        self.profile_var = ctk.StringVar(value="")

        self.openai_key_var = ctk.StringVar(value=os.environ.get("OPENAI_API_KEY", ""))
        self.gemini_key_var = ctk.StringVar(value=os.environ.get("GEMINI_API_KEY", ""))

        self.size_fr_var = ctk.StringVar(value="")
        self.size_us_var = ctk.StringVar(value="")
        self.measure_mode_var = ctk.StringVar(value="etiquette")

        # Gestion des images
        self.selected_images: List[Path] = []
        self._image_directories: set[Path] = set()
        self.image_paths: Optional[List[Path]] = None  # compat avec le reste du code
        self.thumbnail_images: List[ctk.CTkImage] = []  # encore utilisé pour les aperçus plein écran

        self.size_inputs_frame: Optional[ctk.CTkFrame] = None
        self.measure_mode_frame: Optional[ctk.CTkFrame] = None

        self.profiles_by_name_value: Dict[str, AnalysisProfile] = {
            profile.name.value: profile for profile in ALL_PROFILES.values()
        }

        self.title_label: Optional[ctk.CTkLabel] = None
        self.gallery_info_label: Optional[ctk.CTkLabel] = None
        self.preview_frame: Optional[ImagePreview] = None
        self.current_listing: Optional[VintedListing] = None

        self._build_ui()

        logger.info("UI VintedAIApp initialisée.")

    # ------------------------------------------------------------------
    # Construction de l'UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        try:
            ctk.set_appearance_mode("system")
            ctk.set_default_color_theme("blue")

            # Barre du haut
            self._build_top_bar()

            # --- Galerie d'images (header + ImagePreview) ---
            gallery_wrapper = ctk.CTkFrame(self)
            gallery_wrapper.pack(fill="x", padx=0, pady=(0, 8))

            header = ctk.CTkFrame(gallery_wrapper)
            header.pack(fill="x")

            gallery_label = ctk.CTkLabel(header, text="Galerie d'images :")
            gallery_label.pack(side="left", anchor="w", padx=10)

            add_image_btn = ctk.CTkButton(
                header,
                text="+",
                width=30,
                command=self.select_images,
            )
            add_image_btn.pack(side="right", padx=10, pady=4)

            self.gallery_info_label = ctk.CTkLabel(header, text="")
            self.gallery_info_label.pack(side="right", padx=(0, 10))

            # Zone de preview réutilisée depuis l’ancienne app
            self.preview_frame = ImagePreview(
                gallery_wrapper,
                on_remove=self._remove_image,
            )
            self.preview_frame.pack(fill="both", expand=True, padx=8, pady=(4, 0))

            # --- Contenu principal (gauche = paramètres, droite = résultat) ---
            self.main_content_frame = ctk.CTkFrame(self)
            self.main_content_frame.pack(expand=True, fill="both", padx=10, pady=10)

            left_frame = ctk.CTkFrame(self.main_content_frame, width=280)
            left_frame.pack(side="left", fill="y", padx=(0, 10))

            right_scrollable = ctk.CTkScrollableFrame(self.main_content_frame)
            right_scrollable.pack(side="left", expand=True, fill="both")

            # --- Profil d'analyse ---
            profile_label = ctk.CTkLabel(left_frame, text="Profil d'analyse :")
            profile_label.pack(anchor="w", pady=(15, 0))

            profile_values = [name.value for name in AnalysisProfileName]
            if profile_values:
                self.profile_var.set(profile_values[0])

            profile_combo = ctk.CTkComboBox(
                left_frame,
                values=profile_values,
                variable=self.profile_var,
                command=self._on_profile_change,
                state="readonly",
                width=240,
            )
            profile_combo.pack(anchor="w", pady=5)

            # --- Inputs manuels (v1 simple) ---
            self.size_inputs_frame = ctk.CTkFrame(left_frame)
            self.size_inputs_frame.pack(anchor="w", fill="x", pady=(10, 0))

            fr_label = ctk.CTkLabel(self.size_inputs_frame, text="Taille FR (optionnel) :")
            fr_label.pack(anchor="w", pady=(5, 0))
            fr_entry = ctk.CTkEntry(self.size_inputs_frame, textvariable=self.size_fr_var, width=240)
            fr_entry.pack(anchor="w", pady=5)

            us_label = ctk.CTkLabel(self.size_inputs_frame, text="Taille US (optionnel) :")
            us_label.pack(anchor="w", pady=(5, 0))
            us_entry = ctk.CTkEntry(self.size_inputs_frame, textvariable=self.size_us_var, width=240)
            us_entry.pack(anchor="w", pady=5)

            # Méthode de relevé (profils polaire/pull)
            self.measure_mode_frame = ctk.CTkFrame(left_frame)
            measure_label = ctk.CTkLabel(
                self.measure_mode_frame,
                text="Méthode de relevé :",
            )
            measure_label.pack(anchor="w", pady=(5, 0))

            etiquette_radio = ctk.CTkRadioButton(
                self.measure_mode_frame,
                text="Étiquette visible",
                variable=self.measure_mode_var,
                value="etiquette",
            )
            etiquette_radio.pack(anchor="w", pady=2)

            measures_radio = ctk.CTkRadioButton(
                self.measure_mode_frame,
                text="Analyser les mesures",
                variable=self.measure_mode_var,
                value="mesures",
            )
            measures_radio.pack(anchor="w", pady=2)

            # --- Zone de résultat ---
            result_label = ctk.CTkLabel(right_scrollable, text="Résultat (titre + description) :")
            result_label.pack(anchor="w", pady=(10, 0), padx=10)

            self.result_text = ctk.CTkTextbox(right_scrollable, wrap="word")
            self.result_text.pack(expand=True, fill="both", padx=10, pady=(10, 6))

            self._build_generate_button(right_scrollable)

            self._update_profile_ui()

            logger.info("UI principale construite avec zone droite scrollable.")
        except Exception as exc:
            logger.error("Erreur lors de la construction de l'UI principale: %s", exc, exc_info=True)

    def _build_generate_button(self, parent: ctk.CTkFrame) -> None:
        try:
            generate_btn = ctk.CTkButton(
                parent,
                text="Générer",
                command=self.generate_listing,
                width=120,
            )
            generate_btn.pack(anchor="e", padx=10, pady=(0, 10))

            logger.info("Bouton de génération positionné sous la zone de résultat.")
        except Exception as exc:
            logger.error(
                "Erreur lors de l'initialisation du bouton de génération: %s", exc, exc_info=True
            )

    def _build_top_bar(self) -> None:
        try:
            top_bar = ctk.CTkFrame(self)
            top_bar.pack(fill="x", padx=0, pady=(5, 0))

            settings_btn = ctk.CTkButton(
                top_bar,
                text="⚙️",
                width=40,
                command=self.open_settings_menu,
            )
            settings_btn.pack(side="left", padx=(5, 10), pady=5)

            self.title_label = ctk.CTkLabel(
                top_bar,
                text="Assistant Vinted - Préférences adaptatives",
                font=ctk.CTkFont(size=16, weight="bold"),
            )
            self.title_label.pack(side="left", pady=5)

            provider_values = [p.value for p in self.providers.keys()]
            if provider_values and not self.provider_var.get():
                self.provider_var.set(provider_values[0])

            self._update_top_bar_title()

            logger.info("Barre supérieure initialisée avec bouton paramètres.")
        except Exception as exc:
            logger.error("Erreur lors de la construction de la barre supérieure: %s", exc, exc_info=True)

    def _on_provider_change(self, *_args: object) -> None:
        try:
            logger.info("Provider IA sélectionné: %s", self.provider_var.get())
            self._update_top_bar_title()
        except Exception as exc:
            logger.error("Erreur lors du changement de provider IA: %s", exc, exc_info=True)

    def _get_active_model_label(self) -> str:
        try:
            provider = self._get_selected_provider()
            if not provider:
                logger.warning("Aucun provider IA actif pour mettre à jour le titre.")
                return "Modèle non sélectionné"

            model_candidate = None
            for attr_name in ("model", "_model_name"):
                if hasattr(provider, attr_name):
                    model_candidate = getattr(provider, attr_name)
                    break

            if not model_candidate:
                model_candidate = provider.name.value

            model_label = str(model_candidate)
            logger.info("Modèle IA actif détecté pour le titre: %s", model_label)
            return model_label
        except Exception as exc:
            logger.error("Erreur lors de la récupération du modèle actif: %s", exc, exc_info=True)
            return "Modèle inconnu"

    def _update_top_bar_title(self) -> None:
        try:
            model_label = self._get_active_model_label()
            title_text = f"Assistant Vinted - {model_label}"

            if self.title_label:
                self.title_label.configure(text=title_text)

            self.title(title_text)
            logger.info("Titre de l'application mis à jour: %s", title_text)
        except Exception as exc:
            logger.error("Erreur lors de la mise à jour du titre de l'application: %s", exc, exc_info=True)

    # ------------------------------------------------------------------
    # Menu paramètres (provider + clés API)
    # ------------------------------------------------------------------

    def open_settings_menu(self) -> None:
        try:
            settings_window = ctk.CTkToplevel(self)
            settings_window.title("Paramètres avancés")
            settings_window.geometry("420x320")
            settings_window.transient(self)
            settings_window.grab_set()
            settings_window.lift()
            settings_window.focus_force()
            settings_window.attributes("-topmost", True)

            provider_values = [p.value for p in self.providers.keys()]

            provider_label = ctk.CTkLabel(settings_window, text="Modèle IA :")
            provider_label.pack(anchor="w", padx=20, pady=(15, 0))

            provider_combo = ctk.CTkComboBox(
                settings_window,
                values=provider_values,
                variable=self.provider_var,
                state="readonly",
                width=260,
            )
            provider_combo.pack(anchor="w", padx=20, pady=8)

            openai_label = ctk.CTkLabel(settings_window, text="OPENAI_API_KEY :")
            openai_label.pack(anchor="w", padx=20, pady=(20, 0))
            openai_entry = ctk.CTkEntry(settings_window, textvariable=self.openai_key_var, width=360, show="*")
            openai_entry.pack(anchor="w", padx=20, pady=5)

            gemini_label = ctk.CTkLabel(settings_window, text="GEMINI_API_KEY :")
            gemini_label.pack(anchor="w", padx=20, pady=(10, 0))
            gemini_entry = ctk.CTkEntry(settings_window, textvariable=self.gemini_key_var, width=360, show="*")
            gemini_entry.pack(anchor="w", padx=20, pady=5)

            def save_settings() -> None:
                try:
                    os.environ["OPENAI_API_KEY"] = self.openai_key_var.get()
                    os.environ["GEMINI_API_KEY"] = self.gemini_key_var.get()
                    logger.info(
                        "Paramètres mis à jour (provider=%s, openai_key=%s, gemini_key=%s)",
                        self.provider_var.get(),
                        "***" if self.openai_key_var.get() else "(vide)",
                        "***" if self.gemini_key_var.get() else "(vide)",
                    )
                    messagebox.showinfo("Paramètres", "Préférences enregistrées.")
                    close_settings()
                except Exception as exc_save:
                    logger.error("Erreur lors de l'enregistrement des paramètres: %s", exc_save, exc_info=True)
                    messagebox.showerror(
                        "Erreur paramètres",
                        f"Impossible d'enregistrer les paramètres :\n{exc_save}",
                    )

            def close_settings() -> None:
                try:
                    logger.info("Fermeture de la fenêtre des paramètres.")
                    settings_window.grab_release()
                    settings_window.destroy()
                    self.focus_force()
                except Exception as exc_close:
                    logger.error("Erreur lors de la fermeture des paramètres: %s", exc_close, exc_info=True)

            save_btn = ctk.CTkButton(
                settings_window,
                text="Enregistrer",
                command=save_settings,
                width=140,
            )
            save_btn.pack(pady=20)

            settings_window.protocol("WM_DELETE_WINDOW", close_settings)

            logger.info("Fenêtre des paramètres ouverte.")
        except Exception as exc:
            logger.error("Erreur lors de l'ouverture du menu paramètres: %s", exc, exc_info=True)
            messagebox.showerror(
                "Erreur UI",
                f"Impossible d'ouvrir les paramètres :\n{exc}",
            )

    # ------------------------------------------------------------------
    # sélection images (nouvelle logique, réutilise ImagePreview)
    # ------------------------------------------------------------------

    def select_images(self) -> None:
        try:
            logger.info("Ouverture de la boîte de dialogue de sélection d'images")
            file_paths = filedialog.askopenfilenames(
                title="Sélectionnez les photos de l'article",
                filetypes=[("Images", "*.png *.jpg *.jpeg *.webp")],
            )
            if not file_paths:
                logger.info("Aucune image sélectionnée")
                return

            for path in file_paths:
                path_obj = Path(path)
                if path_obj not in self.selected_images:
                    self.selected_images.append(path_obj)
                    self._image_directories.add(path_obj.parent)
                    logger.info("Image ajoutée: %s", path_obj)

            # Garder image_paths cohérent pour le reste du code
            self.image_paths = list(self.selected_images)

            if self.preview_frame:
                self.preview_frame.update_images(self.selected_images)

            self._update_gallery_info()
            logger.info("%d image(s) actuellement sélectionnée(s)", len(self.selected_images))
        except Exception as exc:
            logger.error("Erreur lors de la sélection des images: %s", exc, exc_info=True)
            messagebox.showerror(
                "Erreur sélection",
                f"Impossible de charger les images sélectionnées :\n{exc}",
            )

    def _remove_image(self, image_path: Path) -> None:
        try:
            if image_path in self.selected_images:
                self.selected_images.remove(image_path)
            else:
                logger.warning("Impossible de supprimer %s: image inconnue", image_path)
                return

            logger.info("Image supprimée de la galerie: %s", image_path)

            remaining_directories = {p.parent for p in self.selected_images}
            self._image_directories.intersection_update(remaining_directories)

            self.image_paths = list(self.selected_images)

            if self.preview_frame:
                self.preview_frame.update_images(self.selected_images)

            self._update_gallery_info()
        except Exception as exc:
            logger.error("Erreur lors de la suppression d'une image: %s", exc, exc_info=True)
            messagebox.showerror(
                "Suppression image",
                f"Impossible de retirer cette image :\n{exc}",
            )

    def _update_gallery_info(self) -> None:
        try:
            if not self.gallery_info_label:
                return

            count = len(self.selected_images)
            if not count:
                self.gallery_info_label.configure(text="")
                logger.info("Compteur de galerie vidé (aucune image affichée).")
                return

            plural = "s" if count > 1 else ""
            self.gallery_info_label.configure(text=f"{count} image{plural} sélectionnée{plural}")
            logger.info("Mise à jour du compteur de galerie: %s", count)
        except Exception as exc:
            logger.error("Erreur lors de la mise à jour des informations de galerie: %s", exc, exc_info=True)

    # ------------------------------------------------------------------
    # Provider & profil
    # ------------------------------------------------------------------

    def _profile_requires_measure_mode(self, profile_key: str) -> bool:
        return profile_key in {
            AnalysisProfileName.POLAIRE_OUTDOOR.value,
            AnalysisProfileName.PULL_TOMMY.value,
        }

    def _update_profile_ui(self) -> None:
        try:
            profile_key = self.profile_var.get()
            uses_measure_mode = self._profile_requires_measure_mode(profile_key)

            if uses_measure_mode:
                if self.size_inputs_frame:
                    self.size_inputs_frame.pack_forget()
                if self.measure_mode_frame and not self.measure_mode_frame.winfo_manager():
                    self.measure_mode_frame.pack(anchor="w", fill="x", pady=(10, 0))
                logger.info(
                    "Profil %s détecté : affichage des options de méthode de relevé.",
                    profile_key,
                )
            else:
                if self.measure_mode_frame:
                    self.measure_mode_frame.pack_forget()
                if self.size_inputs_frame and not self.size_inputs_frame.winfo_manager():
                    self.size_inputs_frame.pack(anchor="w", fill="x", pady=(10, 0))
                logger.info(
                    "Profil %s détecté : affichage des tailles FR/US.",
                    profile_key,
                )
        except Exception as exc:
            logger.error("Erreur lors de la mise à jour de l'UI du profil: %s", exc, exc_info=True)

    def _on_profile_change(self, _choice: Optional[str] = None) -> None:
        try:
            logger.info("Profil d'analyse sélectionné: %s", self.profile_var.get())
            self._update_profile_ui()
        except Exception as exc:
            logger.error("Erreur lors du changement de profil: %s", exc, exc_info=True)

    def _get_selected_provider(self) -> Optional[AIListingProvider]:
        provider_key = self.provider_var.get()
        if not provider_key:
            return None

        try:
            provider_name = AIProviderName(provider_key)
        except ValueError:
            logger.error("Provider IA inconnu: %s", provider_key)
            return None

        return self.providers.get(provider_name)

    def _get_selected_profile(self) -> Optional[AnalysisProfile]:
        profile_key = self.profile_var.get()
        if not profile_key:
            return None

        return self.profiles_by_name_value.get(profile_key)

    # ------------------------------------------------------------------
    # Génération
    # ------------------------------------------------------------------

    def generate_listing(self) -> None:
        if not self.selected_images:
            messagebox.showwarning(
                "Images manquantes",
                "Merci de sélectionner au moins une image de l'article.",
            )
            return

        provider = self._get_selected_provider()
        if not provider:
            messagebox.showerror(
                "Provider IA manquant",
                "Provider IA inconnu ou non configuré.",
            )
            return

        profile = self._get_selected_profile()
        if not profile:
            messagebox.showerror(
                "Profil manquant",
                "Profil d'analyse inconnu ou non configuré.",
            )
            return

        logger.info(
            "Lancement analyse IA (provider=%s, profile=%s, images=%s)",
            provider.name.value,
            profile.name.value,
            [str(p) for p in self.selected_images],
        )

        self.result_text.delete("1.0", "end")

        # ---- UI DATA (v1 simple) ----
        profile_requires_measure = self._profile_requires_measure_mode(profile.name.value)

        if profile_requires_measure:
            measurement_mode = self.measure_mode_var.get()
            ui_data = {"measurement_mode": measurement_mode}
            logger.info(
                "Mode de relevé sélectionné pour le profil %s: %s",
                profile.name.value,
                measurement_mode,
            )
        else:
            size_fr = self.size_fr_var.get().strip() or None
            size_us = self.size_us_var.get().strip() or None

            ui_data = {
                "size_fr": size_fr,
                "size_us": size_us,
            }
            logger.info(
                "Tailles fournies (FR=%s, US=%s) pour le profil %s",
                size_fr,
                size_us,
                profile.name.value,
            )

        try:
            listing: VintedListing = provider.generate_listing(
                self.selected_images,
                profile,
                ui_data=ui_data,
            )

            self.current_listing = listing

            self._prompt_composition_if_needed(listing)

            output = self._format_listing(listing)
            self.result_text.insert("1.0", output)

            if self._needs_manual_sku(listing):
                self._prompt_for_sku(listing)

        except Exception as exc:
            logger.error("Erreur provider IA: %s", exc, exc_info=True)
            messagebox.showerror(
                "Erreur IA",
                f"Une erreur est survenue pendant l'analyse IA :\n{exc}",
            )

    def _prompt_composition_if_needed(self, listing: VintedListing) -> None:
        try:
            placeholder = "Composition non lisible (voir photos)."
            if placeholder not in (listing.description or ""):
                logger.info("_prompt_composition_if_needed: composition déjà renseignée.")
                return

            logger.info("_prompt_composition_if_needed: ouverture de la saisie composition manuelle.")
            self._open_composition_modal(listing, placeholder)
        except Exception as exc:
            logger.error("_prompt_composition_if_needed: erreur %s", exc, exc_info=True)

    def _open_composition_modal(self, listing: VintedListing, placeholder: str) -> None:
        try:
            modal = ctk.CTkToplevel(self)
            modal.title("Composition illisible")
            modal.geometry("720x640")
            modal.transient(self)
            modal.grab_set()
            modal.lift()
            modal.focus_force()
            modal.attributes("-topmost", True)

            info_label = ctk.CTkLabel(
                modal,
                text=(
                    "La composition de l'étiquette n'a pas été reconnue.\n"
                    "Merci de consulter les photos dans la galerie ci-dessous puis d'indiquer le texte exact."
                ),
                justify="center",
            )
            info_label.pack(padx=16, pady=(18, 10))

            gallery_frame = ctk.CTkFrame(modal)
            gallery_frame.pack(expand=True, fill="both", padx=12, pady=(0, 10))

            gallery = ImagePreview(gallery_frame, width=240, height=260)
            gallery.set_removal_enabled(False)
            gallery.update_images(self.selected_images)
            gallery.pack(expand=True, fill="both", padx=6, pady=6)

            entry_label = ctk.CTkLabel(
                modal,
                text="Recopiez le texte de l'étiquette de composition (ou laissez vide si coupée) :",
                anchor="w",
            )
            entry_label.pack(fill="x", padx=16, pady=(8, 4))

            composition_text = ctk.CTkTextbox(modal, height=80)
            composition_text.pack(fill="x", padx=16, pady=(0, 10))

            def _apply_composition_text(raw_text: str) -> None:
                try:
                    clean_text = raw_text.strip()
                    if clean_text:
                        sentence = f"Composition : {clean_text.rstrip('.')}."
                    else:
                        sentence = "Etiquette de composition coupée pour plus de confort."

                    updated_description = (listing.description or "").replace(placeholder, sentence)
                    listing.description = updated_description

                    logger.info("Composition manuelle appliquée: %s", sentence)
                    if self.result_text:
                        output = self._format_listing(listing)
                        self.result_text.delete("1.0", "end")
                        self.result_text.insert("1.0", output)
                except Exception as exc_apply:  # pragma: no cover - defensive
                    logger.error("Erreur lors de l'application de la composition: %s", exc_apply, exc_info=True)

            def close_modal() -> None:
                try:
                    modal.grab_release()
                    modal.destroy()
                    self.focus_force()
                except Exception as exc_close:  # pragma: no cover - defensive
                    logger.error("Erreur lors de la fermeture de la modale composition: %s", exc_close, exc_info=True)

            def validate_composition() -> None:
                try:
                    user_text = composition_text.get("1.0", "end")
                    _apply_composition_text(user_text)
                    close_modal()
                except Exception as exc_validate:  # pragma: no cover - defensive
                    logger.error("Erreur lors de la validation de la composition: %s", exc_validate, exc_info=True)

            def fallback_composition() -> None:
                try:
                    _apply_composition_text("")
                    close_modal()
                except Exception as exc_fallback:  # pragma: no cover - defensive
                    logger.error("Erreur lors de l'application du fallback composition: %s", exc_fallback, exc_info=True)

            button_frame = ctk.CTkFrame(modal)
            button_frame.pack(pady=(4, 14))

            validate_btn = ctk.CTkButton(
                button_frame,
                text="Valider la composition",
                command=validate_composition,
                width=180,
            )
            validate_btn.pack(side="left", padx=8)

            missing_btn = ctk.CTkButton(
                button_frame,
                text="Étiquette coupée/absente",
                command=fallback_composition,
                width=180,
            )
            missing_btn.pack(side="left", padx=8)

            modal.protocol("WM_DELETE_WINDOW", fallback_composition)
        except Exception as exc:
            logger.error("_open_composition_modal: erreur %s", exc, exc_info=True)

    # ------------------------------------------------------------------
    # Format
    # ------------------------------------------------------------------

    def _format_listing(self, listing: VintedListing) -> str:
        try:
            lines: List[str] = []

            lines.append(f"TITRE : {listing.title or '(vide)'}")
            lines.append("")
            lines.append("DESCRIPTION :")
            lines.append(listing.description or "(vide)")
            lines.append("")

            if listing.condition:
                lines.append(f"État : {listing.condition}")

            if listing.tags:
                lines.append("")
                lines.append(f"Tags : {', '.join(listing.tags)}")

            if listing.size:
                logger.info(
                    "_format_listing: taille %s disponible mais non ajoutée pour éviter les pieds de description.",
                    listing.size,
                )
            if getattr(listing, "sku", None):
                logger.info(
                    "_format_listing: SKU %s disponible mais non affiché pour éviter les pieds de description.",
                    listing.sku,
                )

            return "\n".join(lines)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("_format_listing: erreur -> rendu brut (%s)", exc, exc_info=True)
            return (
                f"TITRE : {getattr(listing, 'title', '(vide)')}\n\nDESCRIPTION :\n"
                f"{getattr(listing, 'description', '(vide)')}"
            )

    # ------------------------------------------------------------------
    # Gestion du SKU manuel
    # ------------------------------------------------------------------

    def _needs_manual_sku(self, listing: VintedListing) -> bool:
        try:
            sku_value = getattr(listing, "sku", None)
            sku_status = getattr(listing, "sku_status", None)

            if sku_value:
                logger.info("SKU détecté (%s), pas de saisie manuelle requise.", sku_value)
                return False

            if sku_status and sku_status != "ok":
                logger.warning(
                    "SKU manquant ou illisible (statut=%s), ouverture de la saisie manuelle.",
                    sku_status,
                )
                return True

            logger.info("SKU absent sans statut explicite, demande manuelle enclenchée.")
            return True
        except Exception as exc:
            logger.error("Erreur lors de la vérification du SKU: %s", exc, exc_info=True)
            return False

    def _apply_manual_sku(self, listing: VintedListing, sku_value: str) -> None:
        try:
            normalized = sku_value.strip()
            if not normalized:
                logger.info("SKU manuel vide, aucune mise à jour appliquée.")
                return

            base_title = listing.title.strip()
            if SKU_PREFIX in base_title:
                base_title = base_title.split(SKU_PREFIX)[0].strip()

            listing.sku = normalized
            listing.sku_status = "manual"
            listing.title = f"{base_title} {SKU_PREFIX}{normalized}".strip()

            logger.info("SKU manuel appliqué: %s", listing.title)

            if self.result_text:
                output = self._format_listing(listing)
                self.result_text.delete("1.0", "end")
                self.result_text.insert("1.0", output)

        except Exception as exc:
            logger.error("Erreur lors de l'application du SKU manuel: %s", exc, exc_info=True)

    def _prompt_for_sku(self, listing: VintedListing) -> None:
        try:
            sku_window = ctk.CTkToplevel(self)
            sku_window.title("SKU manquant")
            sku_window.geometry("420x220")
            sku_window.transient(self)
            sku_window.grab_set()
            sku_window.lift()
            sku_window.focus_force()
            sku_window.attributes("-topmost", True)

            info_label = ctk.CTkLabel(
                sku_window,
                text=(
                    "SKU non détecté dans les photos.\n"
                    "Merci de le saisir manuellement (ou fermez pour ignorer)."
                ),
                justify="center",
            )
            info_label.pack(padx=20, pady=(20, 10))

            sku_var = ctk.StringVar()
            sku_entry = ctk.CTkEntry(sku_window, textvariable=sku_var, width=260)
            sku_entry.pack(pady=8)
            sku_entry.focus_set()

            button_frame = ctk.CTkFrame(sku_window)
            button_frame.pack(pady=10)

            def close_window() -> None:
                try:
                    logger.info("Fermeture de la fenêtre de saisie SKU.")
                    sku_window.grab_release()
                    sku_window.destroy()
                    self.focus_force()
                except Exception as exc_close:
                    logger.error(
                        "Erreur lors de la fermeture de la fenêtre SKU: %s",
                        exc_close,
                        exc_info=True,
                    )

            def validate_sku() -> None:
                try:
                    self._apply_manual_sku(listing, sku_var.get())
                    close_window()
                except Exception as exc_validate:
                    logger.error(
                        "Erreur lors de la validation du SKU manuel: %s",
                        exc_validate,
                        exc_info=True,
                    )

            validate_btn = ctk.CTkButton(
                button_frame,
                text="Valider",
                command=validate_sku,
                width=120,
            )
            validate_btn.pack(side="left", padx=8)

            cancel_btn = ctk.CTkButton(
                button_frame,
                text="Annuler",
                command=close_window,
                width=120,
            )
            cancel_btn.pack(side="left", padx=8)

            sku_window.protocol("WM_DELETE_WINDOW", close_window)
            logger.info("Fenêtre de saisie SKU affichée en modal.")
        except Exception as exc:
            logger.error("Erreur lors de l'affichage de la saisie SKU: %s", exc, exc_info=True)
