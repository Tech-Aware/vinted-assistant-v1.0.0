# presentation/ui_app.py

from __future__ import annotations

import asyncio
import logging
import os
import re
import threading
import tkinter as tk
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image  # encore utilisé pour l'aperçu plein écran si tu le gardes ailleurs

import customtkinter as ctk
from tkinter import filedialog, messagebox

from domain.ai_provider import AIProviderName, AIListingProvider
from domain.models import VintedListing
from domain.templates import AnalysisProfileName, AnalysisProfile, ALL_PROFILES
from domain.title_builder import SKU_PREFIX, build_pull_title, build_pull_tommy_title

from presentation.image_preview import ImagePreview  # <- widget réutilisé depuis l'ancienne app

# Import du browser bridge pour communication avec l'extension Chrome
try:
    from infrastructure.browser_bridge import get_bridge
    BROWSER_BRIDGE_AVAILABLE = True
except ImportError:
    BROWSER_BRIDGE_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("Browser bridge non disponible - fonctionnalité d'envoi vers Vinted désactivée")

logger = logging.getLogger(__name__)


class VintedAIApp(ctk.CTk):
    """
    UI principale de l'assistant Vinted.

    ÉTAPE 1 :
    - choix modèle Gemini
    - choix profil d'analyse
    - sélection d'images
    - inputs manuels size_fr + size_us
    - generate_listing() avec ui_data minimal

    Pas encore de SKU UI.
    Pas encore de missing/low-confidence.
    """

    def __init__(self, providers: Dict[AIProviderName, AIListingProvider]) -> None:
        super().__init__()

        self.title("Assistant Vinted - Analyse d'images Gemini")
        self.geometry("900x600")
        self.minsize(520, 520)

        self.palette: Dict[str, str] = {}
        self.fonts: Dict[str, ctk.CTkFont] = {}

        self._main_mousewheel_bind_ids: dict[str, str] = {}
        self._main_mousewheel_target: Optional[ctk.CTkBaseClass] = None

        # Browser bridge pour communication avec extension Chrome
        self.browser_bridge = None
        self.bridge_server_running = False
        if BROWSER_BRIDGE_AVAILABLE:
            try:
                self.browser_bridge = get_bridge()
                # Démarrer le serveur en arrière-plan
                threading.Thread(target=self._start_bridge_server_async, daemon=True).start()
            except Exception as exc:
                logger.error("Impossible d'initialiser le browser bridge: %s", exc, exc_info=True)

        self.providers = providers
        self.gemini_provider: Optional[AIListingProvider] = providers.get(AIProviderName.GEMINI)
        if not self.gemini_provider:
            logger.critical("Provider Gemini introuvable : l'application ne peut pas démarrer.")
            raise RuntimeError("Provider Gemini introuvable.")

        self.gemini_model_var = ctk.StringVar(value=self._strip_models_prefix(self._get_provider_model()))
        self.gemini_model_var.trace_add("write", self._on_model_change)
        self.profile_var = ctk.StringVar(value="")

        self.gemini_key_var = ctk.StringVar(value=os.environ.get("GEMINI_API_KEY", ""))

        self.size_fr_var = ctk.StringVar(value="")
        self.size_us_var = ctk.StringVar(value="")
        self.measure_mode_var = ctk.StringVar(value="etiquette")

        # Gestion des images
        self.selected_images: List[Path] = []
        self.ocr_flags: Dict[Path, tk.BooleanVar] = {}
        self._image_directories: set[Path] = set()
        self.image_paths: Optional[List[Path]] = None  # compat avec le reste du code
        self.thumbnail_images: List[ctk.CTkImage] = []  # encore utilisé pour les aperçus plein écran

        self.size_inputs_frame: Optional[ctk.CTkFrame] = None
        self.measure_mode_frame: Optional[ctk.CTkFrame] = None
        self.fr_label: Optional[ctk.CTkLabel] = None
        self.size_hint: Optional[ctk.CTkLabel] = None

        self.profiles_by_name_value: Dict[str, AnalysisProfile] = {
            profile.name.value: profile for profile in ALL_PROFILES.values()
        }

        self.title_label: Optional[ctk.CTkLabel] = None
        self.gallery_info_label: Optional[ctk.CTkLabel] = None
        self.clear_gallery_btn: Optional[ctk.CTkButton] = None
        self.status_label: Optional[ctk.CTkLabel] = None
        self.preview_frame: Optional[ImagePreview] = None
        self.current_listing: Optional[VintedListing] = None

        self.title_text: Optional[ctk.CTkTextbox] = None
        self.description_text: Optional[ctk.CTkTextbox] = None
        self.description_header_label: Optional[ctk.CTkLabel] = None
        self.description_toggle_btn: Optional[ctk.CTkButton] = None

        self.description_variants: List[Dict[str, str]] = []
        self.description_variant_index: int = 0

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

    def _on_main_scroll_enter(self, _event: object) -> None:
        self._bind_main_mousewheel()

    def _on_main_scroll_leave(self, event: object) -> None:
        # évite d'unbind si on “sort” vers un enfant interne
        x_root = getattr(event, "x_root", None)
        y_root = getattr(event, "y_root", None)
        if x_root is not None and y_root is not None:
            widget = self.winfo_containing(x_root, y_root)
            if widget is not None and self._is_descendant(widget, self.main_content_frame):
                return
        self._unbind_main_mousewheel()

    def _bind_main_mousewheel(self) -> None:
        if self._main_mousewheel_bind_ids:
            return
        target = self.winfo_toplevel()
        bindings = {
            "<MouseWheel>": target.bind("<MouseWheel>", self._on_main_mousewheel_windows, add="+"),
            "<Button-4>": target.bind("<Button-4>", self._on_main_mousewheel_linux, add="+"),
            "<Button-5>": target.bind("<Button-5>", self._on_main_mousewheel_linux, add="+"),
        }
        self._main_mousewheel_bind_ids = {seq: fid for seq, fid in bindings.items() if fid}
        self._main_mousewheel_target = target if self._main_mousewheel_bind_ids else None

    def _unbind_main_mousewheel(self) -> None:
        if not self._main_mousewheel_bind_ids:
            return
        target = self._main_mousewheel_target or self.winfo_toplevel()
        for sequence, funcid in self._main_mousewheel_bind_ids.items():
            try:
                target.unbind(sequence, funcid)
            except Exception:
                continue
        self._main_mousewheel_bind_ids.clear()
        self._main_mousewheel_target = None

    def _on_main_mousewheel_windows(self, event: object) -> None:
        # optionnel: laisser les CTkTextbox scroller eux-mêmes
        if self._event_targets_text_widget(event):
            return

        delta = getattr(event, "delta", 0)
        if delta == 0:
            return
        steps = int(-delta / 120) or (-1 if delta > 0 else 1)
        self._main_scroll_by(steps)

    def _on_main_mousewheel_linux(self, event: object) -> None:
        if self._event_targets_text_widget(event):
            return

        num = getattr(event, "num", None)
        if num == 4:
            self._main_scroll_by(-1)
        elif num == 5:
            self._main_scroll_by(1)

    def _main_scroll_by(self, units: int) -> None:
        if units == 0 or not self.main_content_frame:
            return
        canvas = getattr(self.main_content_frame, "_parent_canvas", None) \
                 or getattr(self.main_content_frame, "_canvas", None)
        if canvas is None:
            return
        canvas.yview_scroll(units, "units")

    def _event_targets_text_widget(self, event: object) -> bool:
        x_root = getattr(event, "x_root", None)
        y_root = getattr(event, "y_root", None)
        if x_root is None or y_root is None:
            return False
        widget = self.winfo_containing(x_root, y_root)
        if widget is None:
            return False

        # CustomTkinter textbox encapsule un tk.Text interne; on laisse l'input scroller
        cls_name = widget.winfo_class()
        return cls_name in ("Text",) or "CTkTextbox" in widget.__class__.__name__

    def _is_descendant(self, widget: object, ancestor: object) -> bool:
        current = widget
        while current is not None:
            if current is ancestor:
                return True
            current = getattr(current, "master", None)
        return False

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
            # On laisse les cartes s'adapter à leur contenu pour éviter la troncature des textes.
            card.pack_propagate(True)
            return card
        except Exception as exc:
            logger.error("Erreur lors de la création d'une carte UI: %s", exc, exc_info=True)
            return ctk.CTkFrame(parent)

    def _build_menu(self) -> None:
        try:
            menu_bar = tk.Menu(self)
            settings_menu = tk.Menu(menu_bar, tearoff=0)
            settings_menu.add_command(label="Préférences…", command=self.open_settings_menu)
            menu_bar.add_cascade(label="Paramètres", menu=settings_menu)
            self.configure(menu=menu_bar)
            logger.info("Menu principal initialisé avec entrée Paramètres.")
        except Exception as exc:
            logger.error("Erreur lors de la création du menu principal: %s", exc, exc_info=True)

    def _build_generate_button(self, parent: ctk.CTkFrame) -> None:
        try:
            # Statut non affiché pour aligner les boutons mais conservé pour mise à jour interne
            status_wrapper = ctk.CTkFrame(parent, fg_color="transparent")
            self.status_label = ctk.CTkLabel(
                status_wrapper,
                text="",
                font=self.fonts.get("small"),
                text_color=self.palette.get("text_muted"),
            )
            self.generate_btn = ctk.CTkButton(
                parent,
                text="Générer",
                command=self.generate_listing,
                width=96,
                height=28,
                corner_radius=10,
                fg_color=self.palette.get("accent_gradient_start"),
                hover_color=self.palette.get("accent_gradient_end"),
                text_color="white",
            )
            self.generate_btn.pack(anchor="e", padx=6, pady=(2, 4))

            logger.info("Bouton de génération positionné dans le header de la galerie.")
        except Exception as exc:
            logger.error(
                "Erreur lors de l'initialisation du bouton de génération: %s", exc, exc_info=True
            )
    def _build_ui(self) -> None:
        try:
            self._build_background()
            self._build_menu()

            # Barre du haut
            # self._build_top_bar()

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

            header_inner = ctk.CTkFrame(header, fg_color="transparent")
            header_inner.pack(fill="x", padx=8, pady=6)

            header_left = ctk.CTkFrame(header_inner, fg_color="transparent")
            header_left.pack(side="left", fill="x", expand=True)

            gallery_label = ctk.CTkLabel(
                header_left,
                text="Galerie",
                font=self.fonts.get("heading"),
                text_color=self.palette.get("text_primary"),
            )
            gallery_label.pack(side="left", anchor="w", padx=(6, 10), pady=(4, 2))

            self.gallery_info_label = ctk.CTkLabel(
                header_left,
                text="",
                text_color=self.palette.get("text_muted"),
            )
            self.gallery_info_label.pack(side="left", padx=(0, 10), pady=(4, 2))

            profile_values = [name.value for name in AnalysisProfileName]
            if profile_values and not self.profile_var.get():
                self.profile_var.set(profile_values[0])

            profile_frame = ctk.CTkFrame(header_left, fg_color="transparent")
            profile_frame.pack(side="left", padx=(0, 12), pady=(2, 2))

            profile_label = ctk.CTkLabel(
                profile_frame,
                text="Profil :",
                font=self.fonts.get("small"),
                text_color=self.palette.get("text_primary"),
            )
            profile_label.pack(side="left", padx=(0, 6))

            profile_combo = ctk.CTkComboBox(
                profile_frame,
                values=profile_values,
                variable=self.profile_var,
                command=self._on_profile_change,
                state="readonly",
                width=170,
                fg_color=self.palette.get("input_bg"),
                button_color=self.palette.get("card_border"),
                border_color=self.palette.get("border"),
                text_color=self.palette.get("text_primary"),
            )
            profile_combo.pack(side="left")

            header_actions = ctk.CTkFrame(header_inner, fg_color="transparent")
            header_actions.pack(side="right", anchor="e", pady=(0, 2))

            buttons_row = ctk.CTkFrame(header_actions, fg_color="transparent")
            buttons_row.pack(anchor="e")

            add_image_btn = ctk.CTkButton(
                buttons_row,
                text="+",
                width=48,
                height=28,
                corner_radius=12,
                fg_color=self.palette.get("accent_gradient_end"),
                hover_color=self.palette.get("accent_gradient_start"),
                text_color="white",
                command=self.select_images,
            )
            add_image_btn.pack(side="left", padx=(0, 6), pady=(2, 4))

            generate_wrapper = ctk.CTkFrame(buttons_row, fg_color="transparent")
            generate_wrapper.pack(side="left", padx=(0, 6), pady=(0, 2))
            self._build_generate_button(generate_wrapper)

            self.clear_gallery_btn = ctk.CTkButton(
                buttons_row,
                text="Vider",
                width=84,
                height=28,
                corner_radius=12,
                fg_color=self.palette.get("card_border"),
                hover_color=self.palette.get("accent_gradient_start"),
                text_color="white",
                command=self._clear_gallery,
            )
            self.clear_gallery_btn.pack(side="left", padx=(0, 6), pady=(2, 4))
            self.clear_gallery_btn.pack_forget()

            self.reset_gallery_btn = ctk.CTkButton(
                buttons_row,
                text="⟲",  # ton symbole
                width=30,
                height=28,
                corner_radius=12,
                fg_color=self.palette.get("accent_gradient_end"),
                hover_color=self.palette.get("accent_gradient_start"),
                text_color="white",
                font=ctk.CTkFont(size=16, weight="bold"),
                border_spacing=0,  # clé: padding interne
                anchor="center",  # si ta version CTk le supporte
                command=self._reset_all,
            )
            self.reset_gallery_btn.pack(side="left", padx=(0, 0), pady=(2, 4))

            size_controls_frame = ctk.CTkFrame(header, fg_color="transparent")
            size_controls_frame.pack(fill="x", padx=8, pady=(0, 8))

            self.size_inputs_frame = ctk.CTkFrame(
                size_controls_frame,
                fg_color="transparent",
            )
            self.size_inputs_frame.grid(row=0, column=0, sticky="w", padx=(6, 10))

            size_row = ctk.CTkFrame(self.size_inputs_frame, fg_color="transparent")
            size_row.pack(anchor="w", pady=(4, 2))

            self.fr_label = ctk.CTkLabel(
                size_row,
                text="Taille FR (optionnel) :",
                text_color=self.palette.get("text_primary"),
            )
            self.fr_label.grid(row=0, column=0, sticky="w", padx=(0, 6))

            fr_entry = ctk.CTkEntry(
                size_row,
                textvariable=self.size_fr_var,
                fg_color=self.palette.get("input_bg"),
                border_color=self.palette.get("border"),
                text_color=self.palette.get("text_primary"),
                width=78,
            )
            fr_entry.grid(row=0, column=1, sticky="w", padx=(0, 10))

            us_label = ctk.CTkLabel(
                size_row,
                text="Taille US (optionnel) :",
                text_color=self.palette.get("text_primary"),
            )
            us_label.grid(row=0, column=2, sticky="w", padx=(0, 6))

            us_entry = ctk.CTkEntry(
                size_row,
                textvariable=self.size_us_var,
                fg_color=self.palette.get("input_bg"),
                border_color=self.palette.get("border"),
                text_color=self.palette.get("text_primary"),
                width=78,
            )
            us_entry.grid(row=0, column=3, sticky="w")

            self.size_hint = ctk.CTkLabel(
                size_row,
                text="Renseigner les tailles améliore la précision des fiches.",
                font=self.fonts.get("small"),
                text_color=self.palette.get("text_muted"),
                justify="left",
                wraplength=220,
                anchor="w",
            )
            self.size_hint.grid(row=0, column=4, sticky="w", padx=(12, 0))

            self.measure_mode_frame = ctk.CTkFrame(
                size_controls_frame,
                fg_color="transparent",
            )
            self.measure_mode_frame.grid(row=0, column=1, sticky="e", padx=(12, 6))

            measure_row = ctk.CTkFrame(self.measure_mode_frame, fg_color="transparent")
            measure_row.pack(anchor="e", pady=(4, 2))

            measure_label = ctk.CTkLabel(
                measure_row,
                text="Méthode de relevé :",
                font=self.fonts.get("heading"),
                text_color=self.palette.get("text_primary"),
            )
            measure_label.grid(row=0, column=0, sticky="w", padx=(0, 8))

            etiquette_radio = ctk.CTkRadioButton(
                measure_row,
                text="Étiquette visible",
                variable=self.measure_mode_var,
                value="etiquette",
                text_color=self.palette.get("text_primary"),
            )
            etiquette_radio.grid(row=0, column=1, sticky="w", padx=(0, 8))

            measures_radio = ctk.CTkRadioButton(
                measure_row,
                text="Analyser les mesures",
                variable=self.measure_mode_var,
                value="mesures",
                text_color=self.palette.get("text_primary"),
            )
            measures_radio.grid(row=0, column=2, sticky="w")

            # Zone de preview réutilisée depuis l’ancienne app
            self.preview_frame = ImagePreview(
                gallery_wrapper,
                on_remove=self._remove_image,
                get_ocr_var=lambda p: self.ocr_flags.get(p),
            )
            self.preview_frame.configure(fg_color=self.palette.get("bg_end"))
            self.preview_frame.pack(fill="both", expand=True, padx=8, pady=(4, 0))

            # --- Contenu principal (gauche = paramètres, droite = résultat) ---
            self.main_content_frame = ctk.CTkScrollableFrame(
                self._content_container or self,
                fg_color=self.palette.get("bg_end"),
            )
            self.main_content_frame.pack(expand=True, fill="both", padx=10, pady=10)
            self.main_content_frame.bind("<Enter>", self._on_main_scroll_enter, add="+")
            self.main_content_frame.bind("<Leave>", self._on_main_scroll_leave, add="+")
            self.bind("<Destroy>", lambda e: self._unbind_main_mousewheel(), add="+")

            right_scrollable = ctk.CTkFrame(
                self.main_content_frame,
                fg_color=self.palette.get("bg_end"),
                corner_radius=14,
            )
            right_scrollable.pack(side="left", expand=True, fill="both")

            # --- Zone de résultat : titre + descriptions ---
            result_label = ctk.CTkLabel(
                right_scrollable,
                text="Résultat généré",
                font=self.fonts.get("heading"),
                text_color=self.palette.get("text_primary"),
            )
            result_label.pack(anchor="w", pady=(10, 0), padx=10)

            # Carte Titre
            title_card = self._create_card(right_scrollable)
            title_card.configure(fg_color=self.palette.get("bg_end"))
            title_card.pack(fill="x", padx=10, pady=(0, 0))

            title_header = ctk.CTkFrame(
                title_card,
                fg_color=self.palette.get("bg_end"),
            )
            title_header.pack(fill="x", padx=10, pady=(4, 0))
            title_copy_btn = ctk.CTkButton(
                title_header,
                text="📋",
                width=36,
                height=32,
                corner_radius=10,
                fg_color=self.palette.get("card_border"),
                hover_color=self.palette.get("accent_gradient_start"),
                text_color="white",
                command=self._copy_title_to_clipboard,
            )
            title_copy_btn.pack(side="right")

            title_label = ctk.CTkLabel(
                title_header,
                text="Titre",
                font=self.fonts.get("heading"),
                text_color=self.palette.get("text_primary"),
            )
            title_label.pack(side="left", padx=(0, 8))

            self.title_text = ctk.CTkTextbox(
                title_card,
                height=24,
                wrap="word",
                fg_color=self.palette.get("white"),
                text_color="black",
                corner_radius=12,
                border_width=1,
                border_color=self.palette.get("border"),
            )
            self.title_text.pack(fill="x", padx=10, pady=(6, 10))

            # Carte Description avec carrousel
            description_card = self._create_card(right_scrollable)
            description_card.configure(fg_color=self.palette.get("bg_end"))
            description_card.pack(fill="both", expand=True, padx=10, pady=(0, 8))

            description_header = ctk.CTkFrame(
                description_card,
                fg_color=self.palette.get("bg_end"),
            )
            description_header.pack(fill="x", padx=10, pady=(8, 0))

            self.description_header_label = ctk.CTkLabel(
                description_header,
                text="Description (en attente)",
                font=self.fonts.get("heading"),
                text_color=self.palette.get("text_primary"),
            )
            self.description_header_label.pack(side="left", padx=(0, 8))

            description_controls = ctk.CTkFrame(
                description_header,
                fg_color="transparent",
            )
            description_controls.pack(side="right")

            self.description_toggle_btn = ctk.CTkButton(
                description_controls,
                text="▶",
                width=38,
                height=32,
                corner_radius=10,
                fg_color=self.palette.get("card_border"),
                hover_color=self.palette.get("accent_gradient_start"),
                text_color="white",
                command=self._toggle_description_variant,
            )
            self.description_toggle_btn.pack(side="left", padx=(0, 6))

            description_copy_btn = ctk.CTkButton(
                description_controls,
                text="📋",
                width=36,
                height=32,
                corner_radius=10,
                fg_color=self.palette.get("card_border"),
                hover_color=self.palette.get("accent_gradient_start"),
                text_color="white",
                command=self._copy_description_to_clipboard,
            )
            description_copy_btn.pack(side="left")

            # NOUVEAU: Bouton "Envoyer vers Vinted" (si bridge disponible)
            if BROWSER_BRIDGE_AVAILABLE:
                self.send_vinted_btn = ctk.CTkButton(
                    description_controls,
                    text="📤 Vinted",
                    width=90,
                    height=32,
                    corner_radius=10,
                    fg_color=self.palette.get("accent_gradient_start"),
                    hover_color=self.palette.get("accent_gradient_end"),
                    text_color="white",
                    command=self._send_to_vinted_clicked,
                )
                self.send_vinted_btn.pack(side="left", padx=(6, 0))
                logger.info("Bouton 'Envoyer vers Vinted' ajouté à l'interface")

            self.description_text = ctk.CTkTextbox(
                description_card,
                wrap="word",
                fg_color="white",
                text_color="black",
                corner_radius=12,
                border_width=1,
                border_color=self.palette.get("border"),
            )
            self.description_text.pack(expand=True, fill="both", padx=10, pady=(6, 10))

            self._update_profile_ui()

            logger.info("UI principale construite avec zone droite scrollable.")
        except Exception as exc:
            logger.error("Erreur lors de la construction de l'UI principale: %s", exc, exc_info=True)

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



            self.title_label = ctk.CTkLabel(
                top_bar,
                text="Assistant Vinted - Préférences adaptatives",
                font=ctk.CTkFont(size=16, weight="bold"),
                text_color=self.palette.get("text_primary"),
            )
            self.title_label.pack(side="left", pady=5)

            self._update_top_bar_title()

            logger.info("Barre supérieure initialisée avec bouton paramètres.")
        except Exception as exc:
            logger.error("Erreur lors de la construction de la barre supérieure: %s", exc, exc_info=True)

    def _on_model_change(self, *_args: object) -> None:
        try:
            logger.info("Modèle Gemini sélectionné: %s", self.gemini_model_var.get())
            self._apply_model_selection()
            self._update_top_bar_title()
        except Exception as exc:
            logger.error("Erreur lors du changement de modèle Gemini: %s", exc, exc_info=True)

    def _apply_model_selection(self) -> None:
        try:
            model_choice = self.gemini_model_var.get()
            if not model_choice:
                logger.warning("Aucun modèle Gemini sélectionné : conservation de la configuration actuelle.")
                return

            provider = self._get_selected_provider()
            if not provider:
                logger.error("Impossible d'appliquer le modèle : provider Gemini indisponible.")
                return

            if hasattr(provider, "update_model"):
                provider.update_model(model_choice)
            elif hasattr(provider, "_model_name"):
                provider._model_name = model_choice  # type: ignore[attr-defined]
                logger.warning(
                    "Provider Gemini sans méthode update_model: assignation directe appliquée (%s).",
                    model_choice,
                )
            else:
                logger.error("Provider Gemini ne supporte pas la mise à jour du modèle.")
        except Exception as exc:
            logger.error("Erreur lors de l'application du modèle Gemini: %s", exc, exc_info=True)

    @staticmethod
    def _strip_models_prefix(model_name: str) -> str:
        try:
            cleaned = (model_name or "").strip()
            if cleaned.startswith("models/"):
                return cleaned.split("models/", 1)[1]
            return cleaned
        except Exception as exc:  # pragma: no cover - robustesse
            logger.error("Erreur lors du nettoyage du nom de modèle: %s", exc, exc_info=True)
            return model_name

    def _get_provider_model(self) -> str:
        try:
            if hasattr(self.gemini_provider, "model_name"):
                return str(getattr(self.gemini_provider, "model_name"))
            if hasattr(self.gemini_provider, "_model_name"):
                return str(getattr(self.gemini_provider, "_model_name"))
            if hasattr(self.gemini_provider, "model"):
                return str(getattr(self.gemini_provider, "model"))
        except Exception as exc:  # pragma: no cover - robustesse
            logger.error("Erreur lors de la récupération du modèle Gemini: %s", exc, exc_info=True)
        return "modèle inconnu"

    def _get_active_model_label(self) -> str:
        try:
            model_candidate = self.gemini_model_var.get() or self._strip_models_prefix(self._get_provider_model())
            model_label = self._strip_models_prefix(str(model_candidate))
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
    # Menu paramètres (modèle + clé API)
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

            model_values = ["gemini-3-pro-preview", "gemini-2.5-flash"]

            provider_label = ctk.CTkLabel(settings_window, text="Modèle Gemini :")
            provider_label.pack(anchor="w", padx=20, pady=(15, 0))

            provider_combo = ctk.CTkComboBox(
                settings_window,
                values=model_values,
                variable=self.gemini_model_var,
                state="readonly",
                width=260,
            )
            provider_combo.pack(anchor="w", padx=20, pady=8)

            gemini_label = ctk.CTkLabel(settings_window, text="GEMINI_API_KEY :")
            gemini_label.pack(anchor="w", padx=20, pady=(10, 0))
            gemini_entry = ctk.CTkEntry(settings_window, textvariable=self.gemini_key_var, width=360, show="*")
            gemini_entry.pack(anchor="w", padx=20, pady=5)

            def save_settings() -> None:
                try:
                    os.environ["GEMINI_API_KEY"] = self.gemini_key_var.get()
                    os.environ["GEMINI_MODEL"] = self.gemini_model_var.get()
                    logger.info(
                        "Paramètres mis à jour (modèle=%s, gemini_key=%s)",
                        self.gemini_model_var.get(),
                        "***" if self.gemini_key_var.get() else "(vide)",
                    )
                    self._apply_model_selection()
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
                    self.ocr_flags[path_obj] = tk.BooleanVar(value=False)
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
                self.ocr_flags.pop(image_path, None)
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

    def _clear_gallery(self) -> None:
        try:
            if not self.selected_images:
                logger.info("Aucune image à supprimer: galerie déjà vide.")
                return

            cleared_count = len(self.selected_images)
            self.selected_images.clear()
            self.image_paths = []
            self._image_directories.clear()
            self.ocr_flags.clear()

            if self.preview_frame:
                self.preview_frame.update_images([])

            self._update_gallery_info()
            logger.info("Galerie vidée (%d image(s) supprimée(s)).", cleared_count)
        except Exception as exc:
            logger.error("Erreur lors du vidage de la galerie: %s", exc, exc_info=True)
            messagebox.showerror(
                "Vider la galerie",
                f"Impossible de vider la galerie :\n{exc}",
            )


    def _reset_all(self):
        """
        Reset complet:
        - supprime les fichiers images actuellement sélectionnés (dans leurs dossiers source)
        - vide la galerie
        - vide titre + description
        - reset états internes
        """
        # 1) Récupérer la liste des fichiers images à supprimer
        files_to_delete = []
        if hasattr(self, "selected_images") and self.selected_images:
            files_to_delete = [Path(p) for p in self.selected_images]
        elif hasattr(self, "image_paths") and self.image_paths:
            files_to_delete = [Path(p) for p in self.image_paths]

        # Filtrer (sécurité)
        files_to_delete = [f for f in files_to_delete if isinstance(f, Path)]

        # 2) Confirmation
        n_files = sum(1 for f in files_to_delete if f.exists() and f.is_file())
        ok = messagebox.askyesno(
            "Réinitialiser",
            f"Cette action va supprimer {n_files} image(s) (fichiers) depuis leur dossier source,\n"
            f"puis vider la galerie, le titre et la description.\n\n"
            f"Continuer ?"
        )
        if not ok:
            return

        # 3) Supprimer les fichiers (sans toucher aux dossiers)
        for f in files_to_delete:
            try:
                f = f.resolve()
                if f.exists() and f.is_file():
                    f.unlink()
            except Exception as e:
                print(f"[RESET] Impossible de supprimer {f}: {e}")

        # 4) Vider la galerie (ta méthode existante)
        self._clear_gallery()

        # 5) Vider titre + description
        try:
            if hasattr(self, "title_text") and self.title_text:
                self.title_text.delete("1.0", "end")
        except Exception as e:
            print(f"[RESET] title_text delete error: {e}")

        try:
            if hasattr(self, "description_text") and self.description_text:
                self.description_text.delete("1.0", "end")
        except Exception as e:
            print(f"[RESET] description_text delete error: {e}")

        # 6) Reset variantes/états
        self.description_variants = []
        self.description_variant_index = 0

        if hasattr(self, "current_listing"):
            self.current_listing = None

        # 7) Mettre à jour l’affichage du bouton reset (si tu actives la logique show/hide)
        if hasattr(self, "_update_reset_button_visibility"):
            self._update_reset_button_visibility()

    def _update_gallery_info(self) -> None:
        try:
            if not self.gallery_info_label:
                return

            count = len(self.selected_images)
            if not count:
                self.gallery_info_label.configure(text="")
                logger.info("Compteur de galerie vidé (aucune image affichée).")
                if self.clear_gallery_btn and self.clear_gallery_btn.winfo_manager():
                    try:
                        self.clear_gallery_btn.pack_forget()
                        logger.info("Bouton de vidage de galerie masqué (aucune image).")
                    except Exception as btn_exc:
                        logger.error(
                            "Erreur lors du masquage du bouton de vidage: %s",
                            btn_exc,
                            exc_info=True,
                        )
                return

            plural = "s" if count > 1 else ""
            self.gallery_info_label.configure(text=f"{count} image{plural} sélectionnée{plural}")
            logger.info("Mise à jour du compteur de galerie: %s", count)

            if self.clear_gallery_btn:
                try:
                    if count >= 1:
                        if not self.clear_gallery_btn.winfo_manager():
                            self.clear_gallery_btn.pack(side="left", padx=(0, 6), pady=(2, 4))
                            logger.info(
                                "Bouton de vidage de galerie affiché (compte: %s).",
                                count,
                            )
                    elif self.clear_gallery_btn.winfo_manager():
                        self.clear_gallery_btn.pack_forget()
                        logger.info(
                            "Bouton de vidage de galerie masqué (compte: %s).",
                            count,
                        )
                except Exception as btn_exc:
                    logger.error(
                        "Erreur lors de la mise à jour du bouton de vidage: %s",
                        btn_exc,
                        exc_info=True,
                    )
        except Exception as exc:
            logger.error("Erreur lors de la mise à jour des informations de galerie: %s", exc, exc_info=True)

    # ------------------------------------------------------------------
    # Provider & profil
    # ------------------------------------------------------------------

    def _profile_requires_measure_mode(self, profile_key: str) -> bool:
        return profile_key in {
            AnalysisProfileName.POLAIRE_OUTDOOR.value,
            AnalysisProfileName.PULL.value,
        }

    def _update_profile_ui(self) -> None:
        try:
            profile_key = self.profile_var.get()
            uses_measure_mode = self._profile_requires_measure_mode(profile_key)

            if uses_measure_mode:
                if self.size_inputs_frame and self.size_inputs_frame.winfo_manager():
                    self.size_inputs_frame.grid_remove()
                    logger.info("Champs de taille masqués (profil: %s).", profile_key)
                if self.measure_mode_frame and not self.measure_mode_frame.winfo_manager():
                    self.measure_mode_frame.grid()
                    logger.info(
                        "Profil %s détecté : affichage des options de méthode de relevé.",
                        profile_key,
                    )
            else:
                if self.measure_mode_frame and self.measure_mode_frame.winfo_manager():
                    self.measure_mode_frame.grid_remove()
                    logger.info("Options de méthode de relevé masquées (profil: %s).", profile_key)
                if self.size_inputs_frame and not self.size_inputs_frame.winfo_manager():
                    self.size_inputs_frame.grid()
                    logger.info(
                        "Profil %s détecté : affichage des tailles FR/US.",
                        profile_key,
                    )

            self._refresh_size_requirements(profile_key)
        except Exception as exc:
            logger.error("Erreur lors de la mise à jour de l'UI du profil: %s", exc, exc_info=True)

    def _refresh_size_requirements(self, profile_key: str) -> None:
        try:
            if not self.fr_label or not self.size_hint:
                logger.warning("Labels de taille non initialisés, impossible de rafraîchir les exigences.")
                return

            is_levis = profile_key == AnalysisProfileName.JEAN_LEVIS.value
            fr_text = "Taille FR (obligatoire) :" if is_levis else "Taille FR (optionnel) :"
            hint_text = (
                "Pour un jean Levi's, la taille FR est requise. La taille US reste optionnelle."
                if is_levis
                else "Renseigner les tailles améliore la précision des fiches."
            )

            self.fr_label.configure(text=fr_text, text_color=self.palette.get("text_primary"))
            self.size_hint.configure(
                text=hint_text,
                text_color=self.palette.get("text_muted"),
                wraplength=340,
                anchor="w",
                justify="left",
            )

            logger.info(
                "Mise à jour des indications de taille (profil=%s, taille FR %s)",
                profile_key,
                "obligatoire" if is_levis else "optionnelle",
            )
        except Exception as exc:
            logger.error(
                "Erreur lors de la mise à jour des exigences de taille pour le profil %s: %s",
                profile_key,
                exc,
                exc_info=True,
            )

    def _on_profile_change(self, _choice: Optional[str] = None) -> None:
        try:
            logger.info("Profil d'analyse sélectionné: %s", self.profile_var.get())
            self._update_profile_ui()
        except Exception as exc:
            logger.error("Erreur lors du changement de profil: %s", exc, exc_info=True)

    def _get_selected_provider(self) -> Optional[AIListingProvider]:
        if not self.gemini_provider:
            logger.error("Provider Gemini indisponible.")
            return None
        return self.gemini_provider

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
                    "Provider Gemini manquant",
                    "Le provider Gemini est introuvable ou non configuré.",
                )
                if self.status_label:
                    self.status_label.configure(
                        text="Provider Gemini non configuré.",
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

            if self.title_text:
                try:
                    self.title_text.delete("1.0", "end")
                    self.title_text.insert("1.0", "Analyse en cours...")
                except Exception as exc_text:
                    logger.error(
                        "Erreur lors de la mise à jour du titre temporaire: %s",
                        exc_text,
                        exc_info=True,
                    )

            if self.description_text:
                try:
                    self.description_text.delete("1.0", "end")
                    self.description_text.insert("1.0", "Analyse en cours...\n")
                    if self.description_header_label:
                        self.description_header_label.configure(text="Description (analyse en cours)")
                except Exception as exc_text:
                    logger.error(
                        "Erreur lors de la mise à jour de la description temporaire: %s",
                        exc_text,
                        exc_info=True,
                    )

            self.description_variants = []
            self.description_variant_index = 0

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

            try:
                ocr_image_paths = [
                    str(path)
                    for path, flag in self.ocr_flags.items()
                    if flag.get()
                ]
                ui_data["ocr_image_paths"] = ocr_image_paths
                logger.info(
                    "Images marquées OCR: %s",
                    ocr_image_paths,
                )
            except Exception as exc_flags:  # pragma: no cover - defensive
                logger.warning(
                    "Impossible de construire la liste des images OCR: %s",
                    exc_flags,
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
                    # Binding explicite pour éviter une closure invalide dans Tkinter
                    self.after(
                        0,
                        lambda exc=exc_generation: self._handle_generation_failure(exc),
                    )

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

            if listing.fallback_reason:
                logger.warning(
                    "Résultat de fallback reçu (raison=%s).", listing.fallback_reason
                )
                if self.status_label:
                    self.status_label.configure(
                        text="Résultat partiel (fallback) : vérifiez les photos/étiquettes.",
                        text_color="#f5c542",
                    )
                try:
                    messagebox.showwarning(
                        "Résultat partiel",
                        f"Le résultat provient d'un fallback : {listing.fallback_reason}\n"
                        "Merci de vérifier manuellement le titre et la description.",
                    )
                except Exception as warn_exc:  # pragma: no cover - robustesse UI
                    logger.error(
                        "Impossible d'afficher le message de fallback: %s",
                        warn_exc,
                        exc_info=True,
                    )
            else:
                if self.status_label:
                    self.status_label.configure(
                        text="Fiche générée avec succès.",
                        text_color=self.palette.get("accent_gradient_start", "#1cc59c"),
                    )

            self._prompt_composition_if_needed(listing)

            self._update_result_fields(listing)

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
            modal.geometry("780x720")
            modal.transient(self)
            modal.grab_set()
            modal.lift()
            modal.focus_force()
            modal.attributes("-topmost", True)

            modal.configure(fg_color=self.palette.get("bg_end", "#0b3864"))

            header_frame = ctk.CTkFrame(
                modal,
                fg_color=self.palette.get("card_bg"),
                border_color=self.palette.get("card_border"),
                border_width=1,
                corner_radius=16,
            )
            header_frame.pack(fill="x", padx=16, pady=(16, 10))

            title_label = ctk.CTkLabel(
                header_frame,
                text="Composition manquante",
                font=self.fonts.get("heading"),
                text_color=self.palette.get("text_primary"),
                anchor="w",
            )
            title_label.pack(fill="x", padx=16, pady=(14, 6))

            info_label = ctk.CTkLabel(
                header_frame,
                text=(
                    "La composition de l'étiquette n'a pas été reconnue.\n"
                    "Merci de consulter les photos dans la galerie ci-dessous puis d'indiquer le texte exact."
                ),
                justify="left",
                text_color=self.palette.get("text_muted"),
            )
            info_label.pack(fill="x", padx=16, pady=(0, 14))

            gallery_frame = ctk.CTkFrame(
                modal,
                fg_color=self.palette.get("card_bg"),
                border_color=self.palette.get("card_border"),
                border_width=1,
                corner_radius=16,
            )
            gallery_frame.pack(expand=True, fill="both", padx=16, pady=(0, 10))

            gallery = ImagePreview(
                gallery_frame,
                width=240,
                height=260,
                get_ocr_var=lambda p: self.ocr_flags.get(p),
            )
            gallery.set_removal_enabled(False)
            gallery.update_images(self.selected_images)
            gallery.pack(expand=True, fill="both", padx=6, pady=6)

            entry_label = ctk.CTkLabel(
                gallery_frame,
                text=(
                    "Précisez la composition via les listes déroulantes ci-dessous (jusqu'à 4 lignes).\n"
                    "Merci d'indiquer le pourcentage uniquement si un composant est sélectionné."
                ),
                anchor="center",
                justify="center",
                text_color=self.palette.get("text_muted"),
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

            composition_frame = ctk.CTkFrame(
                modal,
                fg_color=self.palette.get("card_bg"),
                border_color=self.palette.get("card_border"),
                border_width=1,
                corner_radius=16,
            )
            composition_frame.pack(padx=16, pady=(0, 14), anchor="center")

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

                    updated_description = (listing.description or "").replace(
                        placeholder, sentence
                    )
                    listing.description = updated_description

                    try:
                        raw_desc = getattr(listing, "description_raw", "") or ""
                        updated_raw = raw_desc.replace(placeholder, sentence)
                        if updated_raw.strip() and sentence not in updated_raw:
                            updated_raw = (updated_raw.strip() + "\n\n" + sentence).strip()
                        listing.description_raw = updated_raw
                    except Exception as exc_raw:  # pragma: no cover - defensive
                        logger.warning(
                            "_apply_composition_text: mise à jour description brute ignorée (%s)",
                            exc_raw,
                        )

                    logger.info("Composition manuelle appliquée: %s", sentence)
                    self._update_result_fields(listing)
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

            button_frame = ctk.CTkFrame(
                modal,
                fg_color=self.palette.get("bg_end"),
            )
            button_frame.pack(pady=(8, 16))

            validate_btn = ctk.CTkButton(
                button_frame,
                text="Valider la composition",
                command=validate_composition,
                width=180,
                fg_color=self.palette.get("accent_gradient_start"),
                hover_color=self.palette.get("accent_gradient_end"),
            )
            validate_btn.pack(side="left", padx=8)

            missing_btn = ctk.CTkButton(
                button_frame,
                text="Étiquette coupée/absente",
                command=fallback_composition,
                width=180,
                fg_color=self.palette.get("input_bg"),
                hover_color=self.palette.get("card_border"),
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

            if profile_name != AnalysisProfileName.PULL:
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

            updated_title = build_pull_title(features)
            if updated_title and updated_title != listing.title:
                logger.info(
                    "Titre recalcule pour profil pull apres composition: %s", updated_title
                )
                listing.title = updated_title
        except Exception as exc:
            logger.error(
                "_rebuild_title_with_manual_composition: erreur lors du recalcul de titre: %s",
                exc,
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # Mise à jour des zones de résultat
    # ------------------------------------------------------------------

    def _update_result_fields(self, listing: VintedListing) -> None:
        try:
            if not listing:
                logger.warning("_update_result_fields: listing manquant.")
                return

            if self.title_text:
                self.title_text.delete("1.0", "end")
                self.title_text.insert("1.0", listing.title or "(vide)")

            self._set_description_variants(listing)
        except Exception as exc:
            logger.error("_update_result_fields: erreur %s", exc, exc_info=True)

    def _set_description_variants(self, listing: VintedListing) -> None:
        try:
            variants: List[Dict[str, str]] = []

            refined_desc = listing.description or ""

            variants.append(
                {
                    "label": "Description raffinée",
                    "value": refined_desc.strip() or "(vide)",
                }
            )

            if not variants:
                variants.append(
                    {
                        "label": "Description",
                        "value": "(vide)",
                    }
                )

            self.description_variants = variants
            self.description_variant_index = 0
            self._render_description_variant()
        except Exception as exc:
            logger.error("_set_description_variants: erreur %s", exc, exc_info=True)

    def _render_description_variant(self) -> None:
        try:
            if not self.description_text:
                logger.debug("_render_description_variant: zone de description indisponible.")
                return

            if not self.description_variants:
                logger.warning("_render_description_variant: aucune variante à afficher.")
                return

            variant = self.description_variants[self.description_variant_index % len(self.description_variants)]
            self.description_text.delete("1.0", "end")
            self.description_text.insert("1.0", variant.get("value", "(vide)"))

            if self.description_header_label:
                self.description_header_label.configure(text=variant.get("label", "Description"))

            if self.description_toggle_btn:
                next_state = "normal" if len(self.description_variants) > 1 else "disabled"
                self.description_toggle_btn.configure(state=next_state)
                logger.info(
                    "Bouton de bascule description %s (nombre de variantes: %s).",
                    "activé" if next_state == "normal" else "désactivé",
                    len(self.description_variants),
                )
        except Exception as exc:
            logger.error("_render_description_variant: erreur %s", exc, exc_info=True)

    def _toggle_description_variant(self) -> None:
        try:
            if len(self.description_variants) <= 1:
                logger.info("_toggle_description_variant: une seule variante disponible.")
                return

            self.description_variant_index = (self.description_variant_index + 1) % len(
                self.description_variants
            )
            self._render_description_variant()
        except Exception as exc:
            logger.error("_toggle_description_variant: erreur %s", exc, exc_info=True)

    def _copy_title_to_clipboard(self) -> None:
        try:
            if not self.title_text:
                logger.warning("_copy_title_to_clipboard: zone de titre absente.")
                return
            text = self.title_text.get("1.0", "end").strip()
            self.clipboard_clear()
            self.clipboard_append(text)
            logger.info("Titre copié dans le presse-papiers.")
        except Exception as exc:
            logger.error("_copy_title_to_clipboard: erreur %s", exc, exc_info=True)

    def _copy_description_to_clipboard(self) -> None:
        try:
            if not self.description_text:
                logger.warning("_copy_description_to_clipboard: zone de description absente.")
                return
            text = self.description_text.get("1.0", "end").strip()
            self.clipboard_clear()
            self.clipboard_append(text)
            logger.info("Description courante copiée dans le presse-papiers.")
        except Exception as exc:
            logger.error("_copy_description_to_clipboard: erreur %s", exc, exc_info=True)

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

            # 1) SKU présent => jamais de saisie manuelle
            if sku_value:
                logger.info("SKU détecté (%s), pas de saisie manuelle requise.", sku_value)
                return False

            # 2) SKU absent + statut explicite
            # - ok mais sku absent => incohérent => demander
            # - missing / invalid / illisible => demander
            if sku_status:
                sku_status_norm = str(sku_status).strip().lower()

                if sku_status_norm == "ok":
                    logger.warning("SKU status=ok mais sku absent -> saisie manuelle requise.")
                    return True

                logger.warning(
                    "SKU manquant/invalid (statut=%s), ouverture de la saisie manuelle.",
                    sku_status,
                )
                return True

            # 3) SKU absent + pas de statut => demander
            logger.info("SKU absent (aucun statut), demande manuelle enclenchée.")
            return True

        except Exception as exc:
            logger.error("Erreur lors de la vérification du SKU: %s", exc, exc_info=True)
            return True

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

            self._update_result_fields(listing)

        except Exception as exc:
            logger.error("Erreur lors de l'application du SKU manuel: %s", exc, exc_info=True)

    def _prompt_for_sku(self, listing: VintedListing) -> None:
        try:
            sku_window = ctk.CTkToplevel(self)
            sku_window.title("SKU manquant")
            sku_window.geometry("520x280")
            sku_window.transient(self)
            sku_window.grab_set()
            sku_window.lift()
            sku_window.focus_force()
            sku_window.attributes("-topmost", True)

            sku_window.configure(fg_color=self.palette.get("bg_end", "#0b3864"))

            container = ctk.CTkFrame(
                sku_window,
                fg_color=self.palette.get("card_bg"),
                border_color=self.palette.get("card_border"),
                border_width=1,
                corner_radius=16,
            )
            container.pack(fill="both", expand=True, padx=18, pady=18)

            title_label = ctk.CTkLabel(
                container,
                text="SKU manquant",
                font=self.fonts.get("heading"),
                text_color=self.palette.get("text_primary"),
                anchor="w",
            )
            title_label.pack(fill="x", padx=16, pady=(16, 8))

            info_label = ctk.CTkLabel(
                container,
                text=(
                    "SKU non détecté dans les photos.\n"
                    "Merci de le saisir manuellement (ou fermez pour ignorer)."
                ),
                justify="left",
                text_color=self.palette.get("text_muted"),
            )
            info_label.pack(fill="x", padx=16, pady=(0, 6))

            sku_var = ctk.StringVar()
            sku_entry = ctk.CTkEntry(
                container,
                textvariable=sku_var,
                width=320,
                fg_color=self.palette.get("input_bg"),
                border_color=self.palette.get("border"),
            )
            sku_entry.pack(pady=8, padx=16)
            sku_entry.focus_set()

            hint_label = ctk.CTkLabel(
                container,
                text="Exemple : REF12345 (sera ajouté au titre).",
                justify="left",
                text_color=self.palette.get("text_muted"),
            )
            hint_label.pack(fill="x", padx=16, pady=(0, 10))

            button_frame = ctk.CTkFrame(
                container,
                fg_color=self.palette.get("card_bg"),
            )
            button_frame.pack(pady=12)

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
                width=140,
                fg_color=self.palette.get("accent_gradient_start"),
                hover_color=self.palette.get("accent_gradient_end"),
            )
            validate_btn.pack(side="left", padx=8)

            cancel_btn = ctk.CTkButton(
                button_frame,
                text="Annuler",
                command=close_window,
                width=140,
                fg_color=self.palette.get("input_bg"),
                hover_color=self.palette.get("card_border"),
            )
            cancel_btn.pack(side="left", padx=8)

            sku_window.protocol("WM_DELETE_WINDOW", close_window)
            logger.info("Fenêtre de saisie SKU affichée en modal.")
        except Exception as exc:
            logger.error("Erreur lors de l'affichage de la saisie SKU: %s", exc, exc_info=True)

    # ------------------------------------------------------------------
    # Browser Bridge - Envoi vers Vinted (NOUVEAU)
    # ------------------------------------------------------------------

    def _start_bridge_server_async(self) -> None:
        """Démarre le serveur HTTP du bridge de manière asynchrone"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.browser_bridge.start_server())
            self.bridge_server_running = True
            logger.info("Serveur browser bridge démarré avec succès")
        except Exception as exc:
            logger.error("Erreur lors du démarrage du serveur bridge: %s", exc, exc_info=True)
            self.bridge_server_running = False

    def _send_to_vinted_clicked(self) -> None:
        """
        NOUVEAU: Callback pour le bouton "Envoyer vers Vinted"
        Envoie le titre et la description générés vers le brouillon Vinted
        """
        try:
            if not self.bridge_server_running or not self.browser_bridge:
                messagebox.showwarning(
                    "Bridge non disponible",
                    "Le serveur de communication avec l'extension Chrome n'est pas démarré.\n"
                    "Utilisez le copier-coller manuel."
                )
                return

            if not self.current_listing:
                messagebox.showwarning(
                    "Pas de fiche générée",
                    "Veuillez d'abord générer une fiche avant d'envoyer vers Vinted."
                )
                return

            title = self.title_text.get("1.0", "end").strip() if self.title_text else ""
            description = self.description_text.get("1.0", "end").strip() if self.description_text else ""

            if not title or not description:
                messagebox.showwarning(
                    "Données incomplètes",
                    "Le titre ou la description est vide. Générez d'abord une fiche complète."
                )
                return

            # Envoyer de manière asynchrone dans un thread séparé
            def _send_async():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    success = loop.run_until_complete(
                        self.browser_bridge.send_to_vinted(title, description)
                    )

                    if success:
                        self.after(0, lambda: messagebox.showinfo(
                            "Succès",
                            "✅ Titre et description envoyés vers le brouillon Vinted!\n\n"
                            "Vérifiez le brouillon dans votre navigateur et complétez les champs restants."
                        ))
                    else:
                        self.after(0, lambda: messagebox.showerror(
                            "Échec",
                            "❌ L'envoi vers Vinted a échoué.\n\n"
                            "Vérifications:\n"
                            "- Un brouillon Vinted est-il ouvert dans Chrome?\n"
                            "- L'extension est-elle installée et activée?\n"
                            "- Le port forwarding est-il configuré (Chromebook)?"
                        ))
                except Exception as exc_send:
                    logger.error("Erreur lors de l'envoi vers Vinted: %s", exc_send, exc_info=True)
                    self.after(0, lambda: messagebox.showerror(
                        "Erreur",
                        f"Une erreur est survenue:\n{exc_send}"
                    ))

            threading.Thread(target=_send_async, daemon=True).start()
            logger.info("Envoi vers Vinted lancé en arrière-plan")

        except Exception as exc:
            logger.error("Erreur dans _send_to_vinted_clicked: %s", exc, exc_info=True)
            messagebox.showerror(
                "Erreur",
                f"Impossible d'envoyer vers Vinted:\n{exc}"
            )
