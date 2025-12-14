# presentation/ui_app.py

from __future__ import annotations

import logging
import os
import re
import threading
import tkinter as tk
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image  # encore utilisé pour l’aperçu plein écran si tu le gardes ailleurs

import customtkinter as ctk
from tkinter import filedialog, messagebox

from domain.ai_provider import AIProviderName, AIListingProvider
from domain.models import VintedListing
from domain.templates import AnalysisProfileName, AnalysisProfile, ALL_PROFILES
from domain.title_builder import SKU_PREFIX, build_pull_tommy_title

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

        self.palette: Dict[str, str] = {}
        self.fonts: Dict[str, ctk.CTkFont] = {}

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
        self.status_label: Optional[ctk.CTkLabel] = None
        self.preview_frame: Optional[ImagePreview] = None
        self.current_listing: Optional[VintedListing] = None

        self._background_canvas: Optional[tk.Canvas] = None
        self._content_container: Optional[ctk.CTkFrame] = None

        self._init_theme()
        self._build_ui()

        logger.info("UI VintedAIApp initialisée.")

    # ------------------------------------------------------------------
    # Construction de l'UI
    # ------------------------------------------------------------------

    def _init_theme(self) -> None:
        try:
            ctk.set_appearance_mode("light")
            self.palette = {
                "bg_start": "#1dd8a6",
                "bg_end": "#0b3864",
                "card_bg": "#0f2135",
                "card_border": "#1f3953",
                "accent_gradient_start": "#1cc59c",
                "accent_gradient_end": "#1b5cff",
                "text_primary": "#e2f4ff",
                "text_muted": "#a7bed3",
                "input_bg": "#102338",
                "border": "#1e3350",
            }

            self.fonts = {
                "heading": ctk.CTkFont(size=14, weight="bold"),
                "small": ctk.CTkFont(size=11),
            }

            self.configure(fg_color=self.palette.get("bg_end"))
            logger.info("Thème moderne initialisé avec palette verte/bleu.")
        except Exception as exc:
            logger.error("Erreur lors de l'initialisation du thème: %s", exc, exc_info=True)

    def _build_background(self) -> None:
        try:
            if self._background_canvas is None:
                self._background_canvas = tk.Canvas(self, highlightthickness=0, bd=0)
                self._background_canvas.pack(fill="both", expand=True)
                self._background_canvas.bind("<Configure>", self._draw_background_gradient, add="+")

            if self._content_container is None:
                self._content_container = ctk.CTkFrame(
                    self,
                    fg_color=self.palette.get("bg_end", "#0b3864"),
                )
                self._content_container.place(relx=0, rely=0, relwidth=1, relheight=1)

            logger.info("Fond dégradé et conteneur principal préparés.")
        except Exception as exc:
            logger.error("Erreur lors de la création du fond dégradé: %s", exc, exc_info=True)

    def _draw_background_gradient(self, event: tk.Event) -> None:
        try:
            if not self._background_canvas:
                return

            self._background_canvas.delete("gradient")
            width = max(int(getattr(event, "width", self.winfo_width())), 1)
            height = max(int(getattr(event, "height", self.winfo_height())), 1)

            start_hex = self.palette.get("bg_start", "#1dd8a6")
            end_hex = self.palette.get("bg_end", "#0b3864")

            def _hex_to_rgb(color: str) -> Tuple[int, int, int]:
                color = color.lstrip("#")
                return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))

            start_r, start_g, start_b = _hex_to_rgb(start_hex)
            end_r, end_g, end_b = _hex_to_rgb(end_hex)

            for y in range(height):
                ratio = y / max(height - 1, 1)
                r = int(start_r + (end_r - start_r) * ratio)
                g = int(start_g + (end_g - start_g) * ratio)
                b = int(start_b + (end_b - start_b) * ratio)
                color = f"#{r:02x}{g:02x}{b:02x}"
                self._background_canvas.create_line(
                    0,
                    y,
                    width,
                    y,
                    tags="gradient",
                    fill=color,
                )

            self._background_canvas.lower("gradient")
        except Exception as exc:
            logger.error("Erreur lors du dessin du dégradé: %s", exc, exc_info=True)

    def _create_card(self, parent: ctk.CTkBaseClass) -> ctk.CTkFrame:
        try:
            card = ctk.CTkFrame(
                parent,
                fg_color=self.palette.get("card_bg"),
                border_color=self.palette.get("card_border"),
                border_width=1,
                corner_radius=14,
            )
            card.pack_propagate(False)
            return card
        except Exception as exc:
            logger.error("Erreur lors de la création d'une carte UI: %s", exc, exc_info=True)
            return ctk.CTkFrame(parent)

    def _build_ui(self) -> None:
        try:
            self._build_background()

            # Barre du haut
            self._build_top_bar()

            # --- Galerie d'images (header + ImagePreview) ---
            gallery_wrapper = ctk.CTkFrame(
                self._content_container or self,
                fg_color=self.palette.get("bg_end"),
            )
            gallery_wrapper.pack(fill="x", padx=0, pady=(4, 8))

            header = ctk.CTkFrame(
                gallery_wrapper,
                fg_color=self.palette.get("card_bg", "#0b1b2b"),
                corner_radius=14,
            )
            header.pack(fill="x")

            gallery_label = ctk.CTkLabel(
                header,
                text="Galerie d'images",
                font=self.fonts.get("heading"),
                text_color=self.palette.get("text_primary"),
            )
            gallery_label.pack(side="left", anchor="w", padx=14, pady=10)

            add_image_btn = ctk.CTkButton(
                header,
                text="+ Ajouter",
                width=110,
                height=34,
                corner_radius=16,
                fg_color=self.palette.get("accent_gradient_end"),
                hover_color=self.palette.get("accent_gradient_start"),
                text_color="white",
                command=self.select_images,
            )
            add_image_btn.pack(side="right", padx=14, pady=10)

            self.gallery_info_label = ctk.CTkLabel(
                header,
                text="",
                text_color=self.palette.get("text_muted"),
            )
            self.gallery_info_label.pack(side="right", padx=(0, 10))

            # Zone de preview réutilisée depuis l’ancienne app
            self.preview_frame = ImagePreview(
                gallery_wrapper,
                on_remove=self._remove_image,
            )
            self.preview_frame.configure(fg_color=self.palette.get("bg_end"))
            self.preview_frame.pack(fill="both", expand=True, padx=8, pady=(4, 0))

            # --- Contenu principal (gauche = paramètres, droite = résultat) ---
            self.main_content_frame = ctk.CTkFrame(
                self._content_container or self,
                fg_color=self.palette.get("bg_end"),
            )
            self.main_content_frame.pack(expand=True, fill="both", padx=10, pady=10)

            left_frame = ctk.CTkFrame(
                self.main_content_frame,
                width=280,
                fg_color=self.palette.get("bg_end"),
            )
            left_frame.pack(side="left", fill="y", padx=(0, 10))

            sidebar_inner = ctk.CTkFrame(
                left_frame,
                fg_color=self.palette.get("bg_end"),
            )
            sidebar_inner.pack(fill="both", expand=True, padx=6, pady=6)

            right_scrollable = ctk.CTkScrollableFrame(
                self.main_content_frame,
                fg_color=self.palette.get("card_bg"),
                corner_radius=14,
            )
            right_scrollable.pack(side="left", expand=True, fill="both")

            # --- Profil d'analyse ---
            profile_card = self._create_card(sidebar_inner)
            profile_card.pack(anchor="w", fill="x", pady=(8, 0), padx=4)
            profile_label = ctk.CTkLabel(
                profile_card,
                text="Profil d'analyse",
                font=self.fonts.get("heading"),
                text_color=self.palette.get("text_primary"),
            )
            profile_label.pack(anchor="w", pady=(6, 2), padx=12)

            profile_values = [name.value for name in AnalysisProfileName]
            if profile_values:
                self.profile_var.set(profile_values[0])

            profile_combo = ctk.CTkComboBox(
                profile_card,
                values=profile_values,
                variable=self.profile_var,
                command=self._on_profile_change,
                state="readonly",
                width=240,
                fg_color=self.palette.get("input_bg"),
                button_color=self.palette.get("card_border"),
                border_color=self.palette.get("border"),
                text_color=self.palette.get("text_primary"),
            )
            profile_combo.pack(anchor="w", pady=5, padx=12)

            hint_profile = ctk.CTkLabel(
                profile_card,
                text="Choisissez le profil d'analyse adapté à l'article.",
                font=self.fonts.get("small"),
                text_color=self.palette.get("text_muted"),
                justify="left",
                wraplength=220,
            )
            hint_profile.pack(anchor="w", pady=(2, 6), padx=12)

            # --- Inputs manuels (v1 simple) ---
            self.size_inputs_frame = self._create_card(sidebar_inner)
            self.size_inputs_frame.pack(anchor="w", fill="x", pady=(10, 0), padx=4)

            fr_label = ctk.CTkLabel(
                self.size_inputs_frame,
                text="Taille FR (optionnel) :",
                text_color=self.palette.get("text_primary"),
            )
            fr_label.pack(anchor="w", pady=(5, 0), padx=12)
            fr_entry = ctk.CTkEntry(
                self.size_inputs_frame,
                textvariable=self.size_fr_var,
                width=240,
                fg_color=self.palette.get("input_bg"),
                border_color=self.palette.get("border"),
                text_color=self.palette.get("text_primary"),
            )
            fr_entry.pack(anchor="w", pady=5, padx=12)

            us_label = ctk.CTkLabel(
                self.size_inputs_frame,
                text="Taille US (optionnel) :",
                text_color=self.palette.get("text_primary"),
            )
            us_label.pack(anchor="w", pady=(5, 0), padx=12)
            us_entry = ctk.CTkEntry(
                self.size_inputs_frame,
                textvariable=self.size_us_var,
                width=240,
                fg_color=self.palette.get("input_bg"),
                border_color=self.palette.get("border"),
                text_color=self.palette.get("text_primary"),
            )
            us_entry.pack(anchor="w", pady=5, padx=12)

            size_hint = ctk.CTkLabel(
                self.size_inputs_frame,
                text="Renseigner les tailles améliore la précision des fiches.",
                font=self.fonts.get("small"),
                text_color=self.palette.get("text_muted"),
                justify="left",
                wraplength=220,
            )
            size_hint.pack(anchor="w", pady=(2, 8), padx=12)

            # Méthode de relevé (profils polaire/pull)
            self.measure_mode_frame = self._create_card(sidebar_inner)
            measure_label = ctk.CTkLabel(
                self.measure_mode_frame,
                text="Méthode de relevé :",
                font=self.fonts.get("heading"),
                text_color=self.palette.get("text_primary"),
            )
            measure_label.pack(anchor="w", pady=(5, 0), padx=12)

            etiquette_radio = ctk.CTkRadioButton(
                self.measure_mode_frame,
                text="Étiquette visible",
                variable=self.measure_mode_var,
                value="etiquette",
                text_color=self.palette.get("text_primary"),
            )
            etiquette_radio.pack(anchor="w", pady=2, padx=12)

            measures_radio = ctk.CTkRadioButton(
                self.measure_mode_frame,
                text="Analyser les mesures",
                variable=self.measure_mode_var,
                value="mesures",
                text_color=self.palette.get("text_primary"),
            )
            measures_radio.pack(anchor="w", pady=2, padx=12)

            # --- Zone de résultat ---
            result_label = ctk.CTkLabel(
                right_scrollable,
                text="Résultat (titre + description)",
                font=self.fonts.get("heading"),
                text_color=self.palette.get("text_primary"),
            )
            result_label.pack(anchor="w", pady=(10, 0), padx=10)

            self.result_text = ctk.CTkTextbox(
                right_scrollable,
                wrap="word",
                fg_color=self.palette.get("input_bg"),
                text_color=self.palette.get("text_primary"),
                corner_radius=12,
                border_width=1,
                border_color=self.palette.get("border"),
            )
            self.result_text.pack(expand=True, fill="both", padx=10, pady=(10, 6))

            self._build_generate_button(right_scrollable)

            self._update_profile_ui()

            logger.info("UI principale construite avec zone droite scrollable.")
        except Exception as exc:
            logger.error("Erreur lors de la construction de l'UI principale: %s", exc, exc_info=True)

    def _build_generate_button(self, parent: ctk.CTkFrame) -> None:
        try:
            status_wrapper = ctk.CTkFrame(parent, fg_color="transparent")
            status_wrapper.pack(anchor="e", fill="x", padx=10, pady=(0, 2))

            self.status_label = ctk.CTkLabel(
                status_wrapper,
                text="Prêt à générer",
                font=self.fonts.get("small"),
                text_color=self.palette.get("text_muted"),
            )
            self.status_label.pack(anchor="e", pady=(0, 4))

            self.generate_btn = ctk.CTkButton(
                parent,
                text="Générer",
                command=self.generate_listing,
                width=160,
                height=42,
                corner_radius=18,
                fg_color=self.palette.get("accent_gradient_start"),
                hover_color=self.palette.get("accent_gradient_end"),
                text_color="white",
            )
            self.generate_btn.pack(anchor="e", padx=10, pady=(0, 10))

            logger.info("Bouton de génération positionné sous la zone de résultat.")
        except Exception as exc:
            logger.error(
                "Erreur lors de l'initialisation du bouton de génération: %s", exc, exc_info=True
            )

    def _build_top_bar(self) -> None:
        try:
            top_bar = ctk.CTkFrame(
                self._content_container or self,
                fg_color=self.palette.get("card_bg"),
                corner_radius=16,
                border_width=1,
                border_color=self.palette.get("card_border"),
            )
            top_bar.pack(fill="x", padx=12, pady=(10, 8))

            settings_btn = ctk.CTkButton(
                top_bar,
                text="⚙️",
                width=36,
                height=36,
                corner_radius=12,
                fg_color=self.palette.get("accent_gradient_start"),
                hover_color=self.palette.get("accent_gradient_end"),
                text_color="white",
                command=self.open_settings_menu,
            )
            settings_btn.pack(side="left", padx=(5, 10), pady=5)

            self.title_label = ctk.CTkLabel(
                top_bar,
                text="Assistant Vinted - Préférences adaptatives",
                font=ctk.CTkFont(size=16, weight="bold"),
                text_color=self.palette.get("text_primary"),
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
                    self.measure_mode_frame.pack(anchor="w", fill="x", pady=(10, 0), padx=4)
                logger.info(
                    "Profil %s détecté : affichage des options de méthode de relevé.",
                    profile_key,
                )
            else:
                if self.measure_mode_frame:
                    self.measure_mode_frame.pack_forget()
                if self.size_inputs_frame and not self.size_inputs_frame.winfo_manager():
                    self.size_inputs_frame.pack(anchor="w", fill="x", pady=(10, 0), padx=4)
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
        try:
            if not self.selected_images:
                messagebox.showwarning(
                    "Images manquantes",
                    "Merci de sélectionner au moins une image de l'article.",
                )
                if self.status_label:
                    self.status_label.configure(
                        text="Veuillez ajouter au moins une image.",
                        text_color="#f5c542",
                    )
                return

            provider = self._get_selected_provider()
            if not provider:
                messagebox.showerror(
                    "Provider IA manquant",
                    "Provider IA inconnu ou non configuré.",
                )
                if self.status_label:
                    self.status_label.configure(
                        text="Provider IA non configuré.",
                        text_color="#f5c542",
                    )
                return

            profile = self._get_selected_profile()
            if not profile:
                messagebox.showerror(
                    "Profil manquant",
                    "Profil d'analyse inconnu ou non configuré.",
                )
                if self.status_label:
                    self.status_label.configure(
                        text="Profil d'analyse manquant.",
                        text_color="#f5c542",
                    )
                return

            logger.info(
                "Lancement analyse IA (provider=%s, profile=%s, images=%s)",
                provider.name.value,
                profile.name.value,
                [str(p) for p in self.selected_images],
            )

            if self.generate_btn:
                self.generate_btn.configure(state="disabled")

            if self.result_text:
                self.result_text.delete("1.0", "end")
                self.result_text.insert("1.0", "Analyse en cours...\n")

            if self.status_label:
                self.status_label.configure(
                    text="Analyse en cours...", text_color=self.palette.get("text_muted")
                )

            profile_requires_measure = self._profile_requires_measure_mode(
                profile.name.value
            )

            if profile_requires_measure:
                measurement_mode = self.measure_mode_var.get()
                ui_data = {"measurement_mode": measurement_mode}
                logger.info(
                    "Mode de relevé sélectionné pour le profil %s: %s",
                    profile.name.value,
                    measurement_mode,
                )
            else:
                size_fr_input = self.size_fr_var.get().strip()
                size_fr = size_fr_input or None
                size_us = self.size_us_var.get().strip() or None

                if profile.name == AnalysisProfileName.JEAN_LEVIS and not size_fr:
                    if self.generate_btn:
                        self.generate_btn.configure(state="normal")
                    logger.warning(
                        "Blocage génération: taille FR manquante pour le profil jean Levi's."
                    )
                    messagebox.showwarning(
                        "Taille FR requise",
                        "Merci de renseigner la taille FR pour un jean Levi's avant de lancer la génération.",
                    )
                    return

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

            def _run_generation() -> None:
                try:
                    listing: VintedListing = provider.generate_listing(
                        self.selected_images,
                        profile,
                        ui_data=ui_data,
                    )
                    logger.info("Analyse IA terminée, scheduling de la mise à jour UI.")
                    self.after(0, lambda: self._handle_generation_success(listing))
                except Exception as exc_generation:
                    logger.error(
                        "Erreur provider IA: %s", exc_generation, exc_info=True
                    )
                    self.after(0, lambda: self._handle_generation_failure(exc_generation))

            try:
                thread = threading.Thread(
                    daemon=True,
                    target=_run_generation,
                )
                thread.start()
                logger.info("Thread de génération lancé en mode daemon.")
            except Exception as exc_thread:
                logger.error(
                    "Erreur lors du démarrage du thread de génération: %s",
                    exc_thread,
                    exc_info=True,
                )
                self._handle_generation_failure(exc_thread)
        except Exception as exc:
            logger.error("Erreur inattendue lors de la génération: %s", exc, exc_info=True)
            messagebox.showerror(
                "Erreur IA",
                f"Une erreur est survenue pendant l'analyse IA :\n{exc}",
            )

    def _handle_generation_success(self, listing: VintedListing) -> None:
        try:
            if self.generate_btn:
                self.generate_btn.configure(state="normal")

            self.current_listing = listing

            if self.status_label:
                self.status_label.configure(
                    text="Fiche générée avec succès.",
                    text_color=self.palette.get("accent_gradient_start", "#1cc59c"),
                )

            self._prompt_composition_if_needed(listing)

            if self.result_text:
                output = self._format_listing(listing)
                self.result_text.delete("1.0", "end")
                self.result_text.insert("1.0", output)

            if self._needs_manual_sku(listing):
                self._prompt_for_sku(listing)
        except Exception as exc:
            logger.error(
                "Erreur lors de la finalisation de la génération: %s",
                exc,
                exc_info=True,
            )

    def _handle_generation_failure(self, exc: Exception) -> None:
        try:
            if self.generate_btn:
                self.generate_btn.configure(state="normal")

            if self.status_label:
                self.status_label.configure(
                    text="Échec de la génération : consultez le message.",
                    text_color="#f87171",
                )

            messagebox.showerror(
                "Erreur IA",
                f"Une erreur est survenue pendant l'analyse IA :\n{exc}",
            )
        except Exception as exc_ui:
            logger.error(
                "Erreur lors de l'affichage de l'erreur IA: %s", exc_ui, exc_info=True
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
                text=(
                    "Précisez la composition via les listes déroulantes ci-dessous (jusqu'à 4 lignes).\n"
                    "Merci d'indiquer le pourcentage uniquement si un composant est sélectionné."
                ),
                anchor="center",
                justify="center",
            )
            entry_label.pack(fill="x", padx=16, pady=(8, 4))

            material_options = sorted(
                [
                    "acrylique",
                    "angora",
                    "coton",
                    "élasthanne",
                    "laine",
                    "nylon",
                    "polyester",
                    "viscose",
                ],
                key=lambda value: value.lower(),
            )
            percent_values = [str(index) for index in range(1, 101)]

            composition_frame = ctk.CTkFrame(modal)
            composition_frame.pack(padx=12, pady=(0, 12), anchor="center")

            composition_rows: List[Tuple[ctk.CTkComboBox, ctk.CTkComboBox]] = []
            tab_sequence: List[Any] = []

            def _attach_autocomplete(
                combobox: ctk.CTkComboBox, options: List[str], label: str
            ) -> None:
                try:
                    def _on_key_release(event: Any) -> None:
                        try:
                            current_value_raw = combobox.get()
                            current_value = current_value_raw.strip().lower()
                            filtered_values = [
                                value
                                for value in options
                                if value.lower().startswith(current_value)
                            ]
                            combobox.configure(values=filtered_values or options)
                            combobox.set(current_value_raw)
                            try:
                                combobox._entry.icursor(tk.END)
                            except Exception:  # pragma: no cover - best effort
                                pass
                            combobox._open_dropdown_menu()
                        except Exception as exc_key:  # pragma: no cover - defensive
                            logger.error(
                                "Autocomplete %s: erreur lors du filtrage: %s", label, exc_key, exc_info=True
                            )

                    combobox.bind("<KeyRelease>", _on_key_release)
                except Exception as exc_autocomplete:  # pragma: no cover - defensive
                    logger.error(
                        "Autocomplete %s: impossible d'attacher le filtre: %s", label, exc_autocomplete, exc_info=True
                    )

            for row_index in range(4):
                row_frame = ctk.CTkFrame(composition_frame)
                row_frame.pack(padx=8, pady=6, anchor="center")

                material_combo = ctk.CTkComboBox(
                    row_frame,
                    values=material_options,
                    state="normal",
                    width=260,
                    justify="center",
                )
                material_combo.set("")
                material_combo.pack(side="left", padx=(6, 10), pady=4)
                _attach_autocomplete(material_combo, material_options, f"matière-{row_index}")
                tab_sequence.append(material_combo._entry)

                percent_combo = ctk.CTkComboBox(
                    row_frame,
                    values=percent_values,
                    state="normal",
                    width=80,
                    justify="center",
                )
                percent_combo.set("")
                percent_combo.pack(side="left", padx=(0, 6), pady=4)
                _attach_autocomplete(percent_combo, percent_values, f"pourcentage-{row_index}")
                tab_sequence.append(percent_combo._entry)

                percent_label = ctk.CTkLabel(row_frame, text="%")
                percent_label.pack(side="left", padx=(0, 4))

                composition_rows.append((material_combo, percent_combo))

            def _collect_composition_rows() -> Optional[str]:
                try:
                    collected_parts: List[str] = []
                    for index, (material_combo, percent_combo) in enumerate(
                        composition_rows, start=1
                    ):
                        selected_material = material_combo.get().strip()
                        selected_percent = percent_combo.get().strip()

                        if selected_material and not selected_percent:
                            logger.warning(
                                "Ligne %s: pourcentage absent pour le composant %s.",
                                index,
                                selected_material,
                            )
                            messagebox.showerror(
                                "Pourcentage manquant",
                                (
                                    "Merci d'indiquer un pourcentage pour le composant de la ligne "
                                    f"{index}."
                                ),
                            )
                            return None

                        if selected_percent and not selected_material:
                            logger.warning(
                                "Ligne %s: composant manquant pour un pourcentage saisi.", index
                            )
                            messagebox.showerror(
                                "Composant manquant",
                                (
                                    "Merci de sélectionner un composant avant de renseigner un pourcentage "
                                    f"(ligne {index})."
                                ),
                            )
                            return None

                        if selected_material and selected_percent:
                            if selected_material.lower() not in [
                                option.lower() for option in material_options
                            ]:
                                logger.warning(
                                    "Ligne %s: composant inconnu saisi: %s.",
                                    index,
                                    selected_material,
                                )
                                messagebox.showerror(
                                    "Composant invalide",
                                    (
                                        "Merci de choisir un composant depuis la liste déroulante pour la ligne "
                                        f"{index}."
                                    ),
                                )
                                return None

                            if not selected_percent.isdigit():
                                logger.warning(
                                    "Ligne %s: pourcentage non numérique saisi: %s.",
                                    index,
                                    selected_percent,
                                )
                                messagebox.showerror(
                                    "Pourcentage invalide",
                                    "Le pourcentage doit être un nombre entre 1 et 100.",
                                )
                                return None

                            percent_value = int(selected_percent)
                            if percent_value < 1 or percent_value > 100:
                                logger.warning(
                                    "Ligne %s: pourcentage hors plage (%s).",
                                    index,
                                    percent_value,
                                )
                                messagebox.showerror(
                                    "Pourcentage invalide",
                                    "Les pourcentages doivent être compris entre 1 et 100.",
                                )
                                return None
                            collected_parts.append(f"{percent_value}% {selected_material}")

                    return ", ".join(collected_parts)
                except ValueError as exc_value:
                    logger.error(
                        "Erreur de conversion du pourcentage saisi: %s", exc_value, exc_info=True
                    )
                    messagebox.showerror(
                        "Saisie invalide", "Le pourcentage doit être un nombre entre 1 et 100."
                    )
                    return None
                except Exception as exc_collect:  # pragma: no cover - defensive
                    logger.error(
                        "Erreur lors de la collecte des compositions: %s", exc_collect, exc_info=True
                    )
                    messagebox.showerror(
                        "Erreur de saisie", f"Une erreur est survenue pendant la saisie : {exc_collect}"
                    )
                    return None

            def _apply_composition_text(raw_text: str) -> None:
                try:
                    clean_text = raw_text.strip()
                    if clean_text:
                        sentence = f"Composition : {clean_text.rstrip('.')}."
                    else:
                        sentence = "Etiquette de composition coupée pour plus de confort."

                    listing.manual_composition_text = clean_text or None
                    listing.features = getattr(listing, "features", {}) or {}
                    self._update_composition_features(listing, clean_text)
                    self._rebuild_title_with_manual_composition(listing)

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
                    collected_text = _collect_composition_rows()
                    if collected_text is None:
                        return
                    _apply_composition_text(collected_text)
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

            try:
                def _bind_tab_order() -> None:
                    try:
                        ordered_targets: List[Any] = tab_sequence + [validate_btn, missing_btn]
                        for idx, widget in enumerate(tab_sequence):
                            try:
                                next_widget = ordered_targets[idx + 1]
                            except Exception:
                                next_widget = validate_btn

                            def _focus_next(event: Any, target: Any = next_widget) -> str:
                                try:
                                    target.focus_set()
                                except Exception as exc_focus:  # pragma: no cover - defensive
                                    logger.error(
                                        "Navigation tabulation: focus impossible sur %s: %s",
                                        target,
                                        exc_focus,
                                        exc_info=True,
                                    )
                                return "break"

                            try:
                                widget.bind("<Tab>", _focus_next)
                            except Exception as exc_bind:  # pragma: no cover - defensive
                                logger.error(
                                    "Navigation tabulation: liaison impossible sur widget %s: %s",
                                    widget,
                                    exc_bind,
                                    exc_info=True,
                                )
                    except Exception as exc_tab:  # pragma: no cover - defensive
                        logger.error(
                            "Navigation tabulation: erreur lors de la configuration: %s",
                            exc_tab,
                            exc_info=True,
                        )

                _bind_tab_order()
            except Exception as exc_tab_bind:  # pragma: no cover - defensive
                logger.error(
                    "Navigation tabulation: erreur inattendue: %s", exc_tab_bind, exc_info=True
                )

            modal.protocol("WM_DELETE_WINDOW", fallback_composition)
        except Exception as exc:
            logger.error("_open_composition_modal: erreur %s", exc, exc_info=True)

    def _update_composition_features(self, listing: VintedListing, raw_text: str) -> None:
        try:
            features = getattr(listing, "features", {}) or {}
            lowered = raw_text.lower()
            parsed: Dict[str, Any] = {}

            def _search_percent(keywords: List[str]) -> Optional[int]:
                try:
                    for keyword in keywords:
                        before_match = re.search(rf"(\d{{1,3}})\s*%?\s*{keyword}", lowered)
                        if before_match:
                            return int(before_match.group(1))

                        after_match = re.search(rf"{keyword}[^\d]*(\d{{1,3}})\s*%", lowered)
                        if after_match:
                            return int(after_match.group(1))
                    return None
                except Exception:
                    return None

            cotton_percent = _search_percent(["coton", "cotton"])
            wool_percent = _search_percent(["laine", "wool", "cachemire", "cashmere", "angora"])

            if cotton_percent is not None:
                parsed["cotton_percent"] = cotton_percent
            if wool_percent is not None:
                parsed["wool_percent"] = wool_percent

            material_mapping = [
                ("cachemire", "cachemire"),
                ("cashmere", "cachemire"),
                ("angora", "angora"),
                ("laine", "laine"),
                ("wool", "laine"),
                ("coton", "coton"),
                ("cotton", "coton"),
            ]

            for keyword, label in material_mapping:
                if keyword in lowered:
                    parsed["material"] = label
                    break

            parsed["manual_composition_text"] = raw_text.strip() or None

            if parsed:
                features.update({k: v for k, v in parsed.items() if v is not None})
                listing.features = features
                logger.info("Features composition mis à jour: %s", parsed)
        except Exception as exc:
            logger.error("_update_composition_features: erreur %s", exc, exc_info=True)

    def _rebuild_title_with_manual_composition(self, listing: VintedListing) -> None:
        try:
            profile_value = self.profile_var.get()
            try:
                profile_name = AnalysisProfileName(profile_value)
            except Exception:
                logger.warning(
                    "_rebuild_title_with_manual_composition: profil inconnu (%s)",
                    profile_value,
                )
                return

            if profile_name != AnalysisProfileName.PULL_TOMMY:
                logger.info(
                    "_rebuild_title_with_manual_composition: profil %s sans recalcul titre.",
                    profile_value,
                )
                return

            features = getattr(listing, "features", {}) or {}
            if not features:
                logger.warning(
                    "_rebuild_title_with_manual_composition: aucun feature disponible pour recalculer."
                )
                return

            updated_title = build_pull_tommy_title(features)
            if updated_title and updated_title != listing.title:
                logger.info(
                    "Titre recalculé pour profil pull_tommy après composition: %s", updated_title
                )
                listing.title = updated_title
        except Exception as exc:
            logger.error(
                "_rebuild_title_with_manual_composition: erreur lors du recalcul de titre: %s",
                exc,
                exc_info=True,
            )

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
