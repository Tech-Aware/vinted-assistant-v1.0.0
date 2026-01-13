from __future__ import annotations

"""
Copyright 2025 Kevin Andreazza
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy at http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

"""Widgets used to preview selected images in the UI."""

import logging
from pathlib import Path
from typing import Callable, Iterable, List, Optional
import tkinter as tk

import customtkinter as ctk
from PIL import Image, UnidentifiedImageError

logger = logging.getLogger(__name__)


class ImagePreview(ctk.CTkFrame):
    """Widget showing thumbnails for the selected images in a responsive gallery."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        width: int = 220,
        height: int = 320,
        on_remove: Optional[Callable[[Path], None]] = None,
        get_ocr_var: Optional[Callable[[Path], Optional[tk.BooleanVar]]] = None,
        get_defect_var: Optional[Callable[[Path], Optional[tk.BooleanVar]]] = None,
        on_defect_change: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(master)
        self._thumb_min_width = width
        self._default_max_height = max(1, height)
        self._max_height = max(1, height)
        self._max_allowed_height = 1400
        self._card_bg = "#0f2135"
        self._card_border = "#1f3953"
        self._remove_bg = "#d9534f"
        self._remove_hover = "#c33c37"
        self._preview_images: List[ctk.CTkImage] = []
        self._pil_images: List[Image.Image] = []
        self._labels: List[ctk.CTkLabel] = []
        self._image_paths: List[Path] = []
        self._on_remove = on_remove
        self._resize_after_id: Optional[str] = None
        self._mousewheel_bind_ids: dict[str, str] = {}
        self._mousewheel_target: Optional[ctk.CTkBaseClass] = None
        self._remove_buttons: List[ctk.CTkButton] = []
        self._removal_enabled = True
        self._get_ocr_var = get_ocr_var
        self._get_defect_var = get_defect_var
        self._on_defect_change = on_defect_change
        self._ocr_checkboxes: List[ctk.CTkCheckBox] = []
        self._defect_checkboxes: List[ctk.CTkCheckBox] = []

        self._scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color=self._card_bg,
            border_color=self._card_border,
            border_width=1,
            corner_radius=14,
        )
        self._scroll_frame.pack_forget()
        self._scroll_frame.bind("<Enter>", self._on_scroll_enter, add="+")
        self._scroll_frame.bind("<Leave>", self._on_scroll_leave, add="+")

        self._gallery_container = ctk.CTkFrame(
            self._scroll_frame,
            fg_color="transparent",
        )
        self._gallery_container.grid(row=0, column=0, sticky="nwe")
        self._scroll_frame.grid_columnconfigure(0, weight=1)

        self._empty_label = ctk.CTkLabel(
            self,
            text="Aucune image sélectionnée",
            text_color="#e2f4ff",
        )
        self._empty_label.pack(expand=True, fill="both")

        self.bind("<Configure>", self._on_resize)
        self.bind("<Destroy>", self._on_destroy, add="+")

    def _show_empty_state(self, message: str = "Aucune image sélectionnée") -> None:
        self._scroll_frame.pack_forget()
        self._empty_label.configure(text=message)
        self._empty_label.pack(expand=True, fill="both")

    def _show_gallery(self) -> None:
        self._empty_label.pack_forget()
        self._scroll_frame.pack(expand=True, fill="both")

    def set_removal_enabled(self, enabled: bool) -> None:
        """Active ou désactive les boutons de suppression des vignettes."""
        try:
            self._removal_enabled = enabled
            state = "normal" if enabled else "disabled"
            for btn in self._remove_buttons:
                btn.configure(state=state)
            logger.info("set_removal_enabled: suppression %s", "activée" if enabled else "désactivée")
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("set_removal_enabled: erreur %s", exc, exc_info=True)

    def update_images(self, paths: Iterable[Path]) -> None:
        self._labels.clear()
        self._preview_images.clear()
        self._pil_images.clear()
        self._remove_buttons.clear()
        self._ocr_checkboxes.clear()
        self._defect_checkboxes.clear()
        self._image_paths = list(paths)

        for widget in self._gallery_container.winfo_children():
            widget.destroy()

        if not self._image_paths:
            self._show_empty_state()
            logger.info("Aucune image à afficher dans la galerie")
            return

        for path in self._image_paths:
            try:
                with Image.open(path) as pil_img:
                    self._pil_images.append(pil_img.copy())
            except (UnidentifiedImageError, OSError) as exc:
                logger.error("Impossible de créer la vignette pour %s", path, exc_info=exc)

        if not self._pil_images:
            self._show_empty_state("Impossible de lire les images sélectionnées")
            logger.error("Aucune vignette valide n'a pu être générée")
            return

        self._update_target_height()
        self._show_gallery()
        self._render_gallery()
        logger.info("%d vignette(s) générée(s)", len(self._pil_images))

    def _update_target_height(self) -> None:
        try:
            if not self._pil_images:
                self._max_height = self._default_max_height
                logger.info(
                    "Hauteur de galerie réinitialisée à la valeur par défaut (%spx) faute d'image.",
                    self._default_max_height,
                )
                return

            tallest = max((img.height for img in self._pil_images), default=self._default_max_height)
            capped_height = min(max(1, tallest), self._max_allowed_height)
            if capped_height != tallest:
                logger.info(
                    "Hauteur d'image maximale (%spx) plafonnée à %spx pour éviter un débordement UI.",
                    tallest,
                    capped_height,
                )
            self._max_height = capped_height
            logger.info(
                "Hauteur de galerie ajustée dynamiquement à %spx pour éviter la troncature.",
                self._max_height,
            )
        except Exception as exc:  # pragma: no cover - defensive
            self._max_height = self._default_max_height
            logger.error(
                "Échec du calcul de la hauteur cible de galerie: %s. Repli sur %spx.",
                exc,
                self._default_max_height,
                exc_info=True,
            )

    def _on_resize(self, _event: object) -> None:
        if not self._pil_images:
            return
        if self._resize_after_id is not None:
            self.after_cancel(self._resize_after_id)
        self._resize_after_id = self.after(120, self._render_gallery)

    def _render_gallery(self) -> None:
        self._resize_after_id = None
        for widget in self._gallery_container.winfo_children():
            widget.destroy()
        self._labels.clear()
        self._preview_images.clear()
        self._ocr_checkboxes.clear()
        self._defect_checkboxes.clear()

        column_count = self._calculate_columns()
        for column in range(column_count):
            self._gallery_container.grid_columnconfigure(column, weight=1)

        gap = 12
        available_width = max(self._scroll_frame.winfo_width(), self._thumb_min_width)
        column_width = max(self._thumb_min_width, (available_width - gap * (column_count + 1)) // column_count)
        max_height = self._max_height

        for index, (image, path) in enumerate(zip(self._pil_images, self._image_paths)):
            thumbnail = image.copy()
            thumbnail.thumbnail((column_width, max_height))
            tk_img = ctk.CTkImage(light_image=thumbnail, dark_image=thumbnail, size=thumbnail.size)
            self._preview_images.append(tk_img)

            card = ctk.CTkFrame(
                self._gallery_container,
                fg_color=self._card_bg,
                border_color=self._card_border,
                border_width=1,
                corner_radius=14,
            )
            row, column = divmod(index, column_count)
            card.grid(row=row, column=column, padx=gap, pady=gap, sticky="nsew")

            label = ctk.CTkLabel(card, image=tk_img, text="", cursor="hand2")
            label.pack(expand=True, fill="both", padx=6, pady=6)
            label.bind("<Button-1>", lambda _event, p=path: self._open_full_image(p))
            self._labels.append(label)

            if self._on_remove is not None:
                remove_button = ctk.CTkButton(
                    card,
                    text="✕",
                    width=24,
                    height=24,
                    corner_radius=12,
                    fg_color=self._remove_bg,
                    hover_color=self._remove_hover,
                    text_color="white",
                    command=lambda p=path: self._request_remove(p),
                )
                remove_button.place(relx=1.0, rely=0.0, anchor="ne", x=-6, y=6)
                state = "normal" if self._removal_enabled else "disabled"
                remove_button.configure(state=state)
                self._remove_buttons.append(remove_button)

            if self._get_ocr_var is not None:
                try:
                    ocr_var = self._get_ocr_var(path)
                except Exception as exc:
                    logger.warning("Impossible de récupérer le flag OCR pour %s: %s", path, exc)
                    ocr_var = None

                if ocr_var is not None:
                    checkbox = ctk.CTkCheckBox(
                        card,
                        text="OCR",
                        variable=ocr_var,
                        corner_radius=10,
                        fg_color="#1b5cff",
                        hover_color="#1cc59c",
                        text_color="white",
                    )
                    checkbox.place(relx=0.0, rely=0.0, anchor="nw", x=6, y=6)
                    self._ocr_checkboxes.append(checkbox)

            if self._get_defect_var is not None:
                try:
                    defect_var = self._get_defect_var(path)
                except Exception as exc:
                    logger.warning("Impossible de récupérer le flag défaut pour %s: %s", path, exc)
                    defect_var = None

                if defect_var is not None:
                    defect_checkbox = ctk.CTkCheckBox(
                        card,
                        text="Défaut",
                        variable=defect_var,
                        corner_radius=10,
                        fg_color="#d9534f",
                        hover_color="#c33c37",
                        text_color="white",
                        command=self._on_defect_checkbox_change,
                    )
                    defect_checkbox.place(relx=0.0, rely=0.0, anchor="nw", x=6, y=32)
                    self._defect_checkboxes.append(defect_checkbox)

        self._gallery_container.update_idletasks()

    def _open_full_image(self, path: Path) -> None:
        try:
            with Image.open(path) as pil_img:
                display_img = pil_img.copy()
        except (UnidentifiedImageError, OSError) as exc:
            logger.error("Impossible d'ouvrir l'image %s", path, exc_info=exc)
            return

        top = ctk.CTkToplevel(self)
        top.title(path.name)
        top.transient(self.winfo_toplevel())
        top.focus()

        screen_w = top.winfo_screenwidth()
        screen_h = top.winfo_screenheight()
        max_size = (int(screen_w * 0.8), int(screen_h * 0.8))
        display_img.thumbnail(max_size)

        tk_img = ctk.CTkImage(light_image=display_img, dark_image=display_img, size=display_img.size)
        image_label = ctk.CTkLabel(top, image=tk_img, text="")
        image_label.pack(padx=16, pady=16)

        close_button = ctk.CTkButton(top, text="Fermer", command=top.destroy)
        close_button.pack(pady=(0, 16))

        top.bind("<Escape>", lambda _event: top.destroy())
        top._image_ref = tk_img  # type: ignore[attr-defined]

    def _on_scroll_enter(self, _event: object) -> None:
        self._bind_mousewheel()

    def _on_scroll_leave(self, event: object) -> None:
        x_root = getattr(event, "x_root", None)
        y_root = getattr(event, "y_root", None)
        if x_root is not None and y_root is not None:
            widget = self.winfo_containing(x_root, y_root)
            if widget is not None and self._is_descendant(widget, self._scroll_frame):
                return
        self._unbind_mousewheel()

    def _bind_mousewheel(self) -> None:
        if self._mousewheel_bind_ids:
            return
        target = self.winfo_toplevel()
        bindings = {
            "<MouseWheel>": target.bind("<MouseWheel>", self._on_mousewheel_windows, add="+"),
            "<Button-4>": target.bind("<Button-4>", self._on_mousewheel_linux, add="+"),
            "<Button-5>": target.bind("<Button-5>", self._on_mousewheel_linux, add="+"),
        }
        self._mousewheel_bind_ids = {seq: funcid for seq, funcid in bindings.items() if funcid}
        self._mousewheel_target = target if self._mousewheel_bind_ids else None

    def _unbind_mousewheel(self) -> None:
        if not self._mousewheel_bind_ids:
            return
        target = self._mousewheel_target or self.winfo_toplevel()
        for sequence, funcid in self._mousewheel_bind_ids.items():
            try:
                target.unbind(sequence, funcid)
            except Exception:
                continue
        self._mousewheel_bind_ids.clear()
        self._mousewheel_target = None

    def _on_destroy(self, event: object) -> None:
        if getattr(event, "widget", None) is self:
            self._unbind_mousewheel()

    def _on_mousewheel_windows(self, event: object) -> None:
        delta = getattr(event, "delta", 0)
        if delta == 0:
            return
        steps = int(-delta / 120)
        if steps == 0:
            steps = -1 if delta > 0 else 1
        self._scroll_by(steps)

    def _on_mousewheel_linux(self, event: object) -> None:
        num = getattr(event, "num", None)
        if num == 4:
            self._scroll_by(-1)
        elif num == 5:
            self._scroll_by(1)

    def _scroll_by(self, units: int) -> None:
        if units == 0:
            return
        canvas = self._get_scroll_canvas()
        if canvas is None:
            return
        canvas.yview_scroll(units, "units")

    def _get_scroll_canvas(self):
        canvas = getattr(self._scroll_frame, "_parent_canvas", None)
        if canvas is None:
            canvas = getattr(self._scroll_frame, "_canvas", None)
        return canvas

    def _is_descendant(self, widget: object, ancestor: object) -> bool:
        current = widget
        while current is not None:
            if current is ancestor:
                return True
            current = getattr(current, "master", None)
        return False

    def _calculate_columns(self) -> int:
        available_width = max(self._scroll_frame.winfo_width(), self._thumb_min_width)
        min_card_width = self._thumb_min_width + 24
        columns = max(1, available_width // max(min_card_width, 1))
        return max(1, min(columns, len(self._pil_images)))

    def _request_remove(self, path: Path) -> None:
        if self._on_remove is None or not self._removal_enabled:
            return
        logger.info("Suppression demandée pour %s", path)
        self._on_remove(path)

    def _on_defect_checkbox_change(self) -> None:
        """Appelé quand une checkbox défaut change d'état."""
        if self._on_defect_change is not None:
            try:
                self._on_defect_change()
            except Exception as exc:
                logger.warning("Erreur lors du callback on_defect_change: %s", exc)
