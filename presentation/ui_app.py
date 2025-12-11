# presentation/ui_app.py

from __future__ import annotations

import logging
from pathlib import Path
import os
from typing import Dict, List, Optional

from PIL import Image

import customtkinter as ctk
from tkinter import filedialog, messagebox

from domain.ai_provider import AIProviderName, AIListingProvider
from domain.models import VintedListing
from domain.templates import AnalysisProfileName, AnalysisProfile, ALL_PROFILES

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

        self.providers = providers
        self.provider_var = ctk.StringVar(value="")
        self.profile_var = ctk.StringVar(value="")

        self.openai_key_var = ctk.StringVar(value=os.environ.get("OPENAI_API_KEY", ""))
        self.gemini_key_var = ctk.StringVar(value=os.environ.get("GEMINI_API_KEY", ""))

        self.size_fr_var = ctk.StringVar(value="")
        self.size_us_var = ctk.StringVar(value="")

        self.image_paths: Optional[List[Path]] = None
        self.thumbnail_images: List[ctk.CTkImage] = []
        self._gallery_resize_after: Optional[str] = None
        self._last_gallery_width: int = 0

        self.profiles_by_name_value: Dict[str, AnalysisProfile] = {
            profile.name.value: profile for profile in ALL_PROFILES.values()
        }

        self._build_ui()

        logger.info("UI VintedAIApp initialisée.")

    # ------------------------------------------------------------------
    # Construction de l'UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        self._build_top_bar()

        left_frame = ctk.CTkFrame(self, width=280)
        left_frame.pack(side="left", fill="y", padx=10, pady=10)

        right_frame = ctk.CTkFrame(self)
        right_frame.pack(side="right", expand=True, fill="both", padx=10, pady=10)

        gallery_label = ctk.CTkLabel(right_frame, text="Galerie d'images :")
        gallery_label.pack(anchor="w", pady=(10, 0), padx=10)

        self.gallery_frame = ctk.CTkScrollableFrame(right_frame, height=230)
        self.gallery_frame.pack(fill="both", padx=10, pady=10)
        self.gallery_frame.bind("<Configure>", self._on_gallery_resize)

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
            state="readonly",
            width=240,
        )
        profile_combo.pack(anchor="w", pady=5)

        # --- Inputs manuels (v1 simple) ---
        # Taille FR
        fr_label = ctk.CTkLabel(left_frame, text="Taille FR (optionnel) :")
        fr_label.pack(anchor="w", pady=(15,0))
        fr_entry = ctk.CTkEntry(left_frame, textvariable=self.size_fr_var, width=240)
        fr_entry.pack(anchor="w", pady=5)

        # Taille US
        us_label = ctk.CTkLabel(left_frame, text="Taille US (optionnel) :")
        us_label.pack(anchor="w", pady=(5,0))
        us_entry = ctk.CTkEntry(left_frame, textvariable=self.size_us_var, width=240)
        us_entry.pack(anchor="w", pady=5)

        # --- Sélection des images ---
        image_btn = ctk.CTkButton(
            left_frame,
            text="Sélectionner les images...",
            command=self.select_images,
            width=240,
        )
        image_btn.pack(anchor="w", pady=(20, 5))

        self.image_label = ctk.CTkLabel(
            left_frame,
            text="Aucune image sélectionnée.",
            wraplength=240,
            justify="left",
        )
        self.image_label.pack(anchor="w", pady=(0, 10))

        # --- Bouton de génération ---
        generate_btn = ctk.CTkButton(
            left_frame,
            text="Générer l'annonce",
            command=self.generate_listing,
            width=240,
        )
        generate_btn.pack(anchor="w", pady=(20, 10))

        # --- Zone de résultat ---
        result_label = ctk.CTkLabel(right_frame, text="Résultat (titre + description) :")
        result_label.pack(anchor="w", pady=(10, 0), padx=10)

        self.result_text = ctk.CTkTextbox(right_frame, wrap="word")
        self.result_text.pack(expand=True, fill="both", padx=10, pady=10)

    def _build_top_bar(self) -> None:
        try:
            top_bar = ctk.CTkFrame(self)
            top_bar.pack(fill="x", padx=10, pady=(5, 0))

            settings_btn = ctk.CTkButton(
                top_bar,
                text="⚙️",
                width=40,
                command=self.open_settings_menu,
            )
            settings_btn.pack(side="left", padx=(5, 10), pady=5)

            title_label = ctk.CTkLabel(
                top_bar,
                text="Assistant Vinted - Préférences adaptatives",
                font=ctk.CTkFont(size=16, weight="bold"),
            )
            title_label.pack(side="left", pady=5)

            provider_values = [p.value for p in self.providers.keys()]
            if provider_values and not self.provider_var.get():
                self.provider_var.set(provider_values[0])

            logger.info("Barre supérieure initialisée avec bouton paramètres.")
        except Exception as exc:
            logger.error("Erreur lors de la construction de la barre supérieure: %s", exc, exc_info=True)

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
    # sélection images
    # ------------------------------------------------------------------

    def select_images(self) -> None:
        try:
            filetypes = [
                ("Images", "*.jpg *.jpeg *.png *.webp"),
                ("Tous les fichiers", "*.*"),
            ]

            paths = filedialog.askopenfilenames(
                title="Sélectionne les images (même article)",
                filetypes=filetypes,
            )

            if not paths:
                logger.info("Aucune image sélectionnée.")
                return

            self.image_paths = [Path(p) for p in paths]

            if len(self.image_paths) == 1:
                self.image_label.configure(
                    text=f"1 image sélectionnée :\n{self.image_paths[0]}"
                )
            else:
                first = self.image_paths[0]
                count = len(self.image_paths)
                self.image_label.configure(
                    text=f"{count} images sélectionnées.\nPremière : {first}"
                )

            logger.info(
                "Images sélectionnées: %s",
                [str(p) for p in self.image_paths],
            )

            self._refresh_gallery()
        except Exception as exc:
            logger.error("Erreur lors de la sélection des images: %s", exc, exc_info=True)
            messagebox.showerror(
                "Erreur sélection",
                f"Impossible de charger les images sélectionnées :\n{exc}",
            )

    def _on_gallery_resize(self, event: object) -> None:
        try:
            if not self.image_paths:
                return

            width = getattr(event, "width", 0)
            if width and abs(width - self._last_gallery_width) < 10:
                return

            self._last_gallery_width = width

            if self._gallery_resize_after:
                self.after_cancel(self._gallery_resize_after)

            self._gallery_resize_after = self.after(120, self._refresh_gallery)
            logger.debug("Redimensionnement de la galerie détecté (width=%s).", width)
        except Exception as exc:
            logger.error("Erreur lors du recalcul de la galerie: %s", exc, exc_info=True)

    def _refresh_gallery(self) -> None:
        try:
            for child in self.gallery_frame.winfo_children():
                child.destroy()

            self.thumbnail_images.clear()

            if not self.image_paths:
                logger.info("Galerie réinitialisée (aucune image).")
                return

            thumb_size = 120
            gallery_width = max(self.gallery_frame.winfo_width(), thumb_size + 20)
            columns = max(1, gallery_width // (thumb_size + 20))

            for idx, img_path in enumerate(self.image_paths):
                try:
                    row = idx // columns
                    col = idx % columns

                    card = ctk.CTkFrame(self.gallery_frame)
                    card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")

                    pil_image = Image.open(img_path)
                    pil_image.thumbnail((thumb_size, thumb_size))
                    thumb = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=(thumb_size, thumb_size))
                    self.thumbnail_images.append(thumb)

                    img_label = ctk.CTkLabel(card, image=thumb, text="")
                    img_label.pack(expand=True, fill="both", padx=4, pady=4)
                    img_label.bind(
                        "<Button-1>",
                        lambda _evt, path=img_path: self._show_full_image(path),
                    )

                    remove_btn = ctk.CTkButton(
                        card,
                        text="✕",
                        width=26,
                        height=26,
                        fg_color="#c0392b",
                        hover_color="#e74c3c",
                        command=lambda path=img_path: self._remove_image(path),
                    )
                    remove_btn.place(relx=1, rely=0, anchor="ne", x=-4, y=4)
                except Exception as exc_img:
                    logger.error("Erreur lors du rendu d'une miniature: %s", exc_img, exc_info=True)

            logger.info("Galerie mise à jour (%s images).", len(self.image_paths))
        except Exception as exc:
            logger.error("Erreur lors de la mise à jour de la galerie: %s", exc, exc_info=True)

    def _remove_image(self, image_path: Path) -> None:
        try:
            if not self.image_paths:
                return

            self.image_paths = [p for p in self.image_paths if p != image_path]

            if not self.image_paths:
                self.image_label.configure(text="Aucune image sélectionnée.")
            elif len(self.image_paths) == 1:
                self.image_label.configure(text=f"1 image sélectionnée :\n{self.image_paths[0]}")
            else:
                first = self.image_paths[0]
                self.image_label.configure(
                    text=f"{len(self.image_paths)} images sélectionnées.\nPremière : {first}"
                )

            logger.info("Image supprimée de la galerie: %s", image_path)
            self._refresh_gallery()
        except Exception as exc:
            logger.error("Erreur lors de la suppression d'une image: %s", exc, exc_info=True)
            messagebox.showerror(
                "Suppression image",
                f"Impossible de retirer cette image :\n{exc}",
            )

    def _show_full_image(self, image_path: Path) -> None:
        try:
            viewer = ctk.CTkToplevel(self)
            viewer.title(image_path.name)
            viewer.geometry("720x640")
            viewer.transient(self)
            viewer.grab_set()

            pil_image = Image.open(image_path)
            pil_image.thumbnail((700, 580))
            full_img = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=pil_image.size)

            img_label = ctk.CTkLabel(viewer, image=full_img, text="")
            img_label.pack(expand=True, fill="both", padx=10, pady=10)

            self.thumbnail_images.append(full_img)

            close_btn = ctk.CTkButton(viewer, text="Fermer", command=viewer.destroy, width=100)
            close_btn.pack(pady=8)

            logger.info("Affichage en grand de l'image: %s", image_path)
        except Exception as exc:
            logger.error("Erreur lors de l'affichage d'une image: %s", exc, exc_info=True)
            messagebox.showerror(
                "Affichage image",
                f"Impossible d'afficher l'image :\n{exc}",
            )

    # ------------------------------------------------------------------
    # Provider & profil
    # ------------------------------------------------------------------

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
        if not self.image_paths:
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
            [str(p) for p in self.image_paths],
        )

        self.result_text.delete("1.0", "end")

        # ---- UI DATA (v1 simple) ----
        size_fr = self.size_fr_var.get().strip() or None
        size_us = self.size_us_var.get().strip() or None

        ui_data = {
            "size_fr": size_fr,
            "size_us": size_us,
        }

        try:
            listing: VintedListing = provider.generate_listing(
                self.image_paths,
                profile,
                ui_data=ui_data,
            )

            output = self._format_listing(listing)
            self.result_text.insert("1.0", output)

        except Exception as exc:
            logger.error("Erreur provider IA: %s", exc, exc_info=True)
            messagebox.showerror(
                "Erreur IA",
                f"Une erreur est survenue pendant l'analyse IA :\n{exc}",
            )

    # ------------------------------------------------------------------
    # Format
    # ------------------------------------------------------------------

    def _format_listing(self, listing: VintedListing) -> str:
        lines: List[str] = []

        lines.append(f"TITRE : {listing.title or '(vide)'}")
        lines.append("")
        lines.append("DESCRIPTION :")
        lines.append(listing.description or "(vide)")
        lines.append("")

        if listing.brand:
            lines.append(f"Marque : {listing.brand}")
        if listing.size:
            lines.append(f"Taille : {listing.size}")
        if listing.condition:
            lines.append(f"État : {listing.condition}")
        if listing.color:
            lines.append(f"Couleur : {listing.color}")

        if listing.tags:
            lines.append("")
            lines.append(f"Tags : {', '.join(listing.tags)}")

        return "\n".join(lines)
