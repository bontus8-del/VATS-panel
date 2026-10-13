"""Поле ввода с выпадающим списком подсказок.

Особенности:
- Свободный ввод сохраняется: пользователь может вписать любое значение руками.
- Список фильтруется через search_callback(query) -> list[item].
- В строке списка показывается format_callback(item), в поле подставляется
  select_callback(item).
- Debounce 250 мс, максимум 15 строк.
- Закрытие: Esc, выбор элемента, клик вне поля (FocusOut).
- show_all_on_focus=True — при фокусе на пустом поле показать полный список
  (search_callback вызывается с пустым query).
- Список — Toplevel(overrideredirect); при нехватке места снизу открывается вверх.
- Опциональный tooltip_text показывается при наведении на поле.
"""
import tkinter as tk
import customtkinter as ctk

import config
from .tooltip import Tooltip


class AutocompleteEntry(ctk.CTkFrame):
    DEBOUNCE_MS = 250
    ROW_HEIGHT = 26
    FONT = ("Segoe UI", 10)
    MAX_ROWS = 15
    MIN_DROPDOWN_WIDTH = 320

    def __init__(self, parent, search_callback, format_callback, select_callback,
                 width: int = 220, height: int = 34,
                 placeholder: str = "", tooltip_text: str = "",
                 show_all_on_focus: bool = False):
        super().__init__(parent, fg_color="transparent")
        self._search_cb = search_callback
        self._format_cb = format_callback
        self._select_cb = select_callback
        self._show_all_on_focus = show_all_on_focus

        self.var = tk.StringVar()
        self.entry = ctk.CTkEntry(
            self, textvariable=self.var, width=width, height=height,
            corner_radius=6, fg_color="#ffffff", border_color=config.BORDER_COLOR,
            placeholder_text=placeholder, font=ctk.CTkFont(size=12),
        )
        self.entry.pack()

        if tooltip_text:
            Tooltip(self.entry, tooltip_text)

        self._dropdown = None
        self._items = []
        self._debounce_id = None
        self._suppress_change = False

        self.var.trace_add("write", lambda *a: self._on_change())
        self.entry.bind("<FocusIn>", self._on_focus_in, add="+")
        self.entry.bind("<FocusOut>", self._on_focus_out, add="+")
        self.entry.bind("<Escape>", lambda e: self._hide_dropdown(), add="+")

    # --- публичный API ---
    def get(self) -> str:
        return self.var.get()

    def set(self, value: str):
        self._suppress_change = True
        try:
            self.var.set(value)
        finally:
            self._suppress_change = False

    def destroy(self):
        if self._debounce_id is not None:
            try:
                self.after_cancel(self._debounce_id)
            except Exception:
                pass
            self._debounce_id = None
        self._hide_dropdown()
        super().destroy()

    # --- события ---
    def _on_change(self):
        if self._suppress_change:
            return
        if self._debounce_id is not None:
            try:
                self.after_cancel(self._debounce_id)
            except Exception:
                pass
        self._debounce_id = self.after(self.DEBOUNCE_MS, self._do_search)

    def _on_focus_in(self, event):
        if self._show_all_on_focus:
            # Небольшая задержка, чтобы клик успел сработать по полю
            self.after(50, self._do_search)

    def _do_search(self):
        self._debounce_id = None
        query = self.var.get().strip()
        if not query and not self._show_all_on_focus:
            self._hide_dropdown()
            return
        try:
            self._items = self._search_cb(query) or []
        except Exception:
            self._items = []
        if not self._items:
            self._hide_dropdown()
            return
        self._show_dropdown()

    def _on_focus_out(self, event):
        self.after(150, self._hide_dropdown)

    def _apply_selection(self, item):
        value = self._select_cb(item)
        self.set(value)
        self._hide_dropdown()
        try:
            self.entry.focus_set()
        except Exception:
            pass

    # --- выпадающий список ---
    def _show_dropdown(self):
        self._hide_dropdown()
        items = self._items[:self.MAX_ROWS]

        self.update_idletasks()
        x = self.entry.winfo_rootx()
        y = self.entry.winfo_rooty() + self.entry.winfo_height() + 2
        w = max(self.entry.winfo_width(), self.MIN_DROPDOWN_WIDTH)
        h = self.ROW_HEIGHT * len(items) + 4

        screen_h = self.winfo_screenheight()
        if y + h > screen_h - 20:
            y = self.entry.winfo_rooty() - h - 2

        self._dropdown = tk.Toplevel(self)
        self._dropdown.wm_overrideredirect(True)
        self._dropdown.wm_geometry(f"{w}x{h}+{x}+{y}")
        self._dropdown.configure(bg=config.BORDER_COLOR)
        try:
            self._dropdown.attributes("-topmost", True)
        except Exception:
            pass

        inner = tk.Frame(self._dropdown, bg="#ffffff", bd=0)
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        for it in items:
            text = self._format_cb(it)
            lbl = tk.Label(
                inner, text=text, anchor="w",
                bg="#ffffff", fg=config.TEXT_MAIN,
                font=self.FONT, padx=8, cursor="hand2",
            )
            lbl.pack(fill="x")
            lbl.bind("<Enter>", lambda e, l=lbl: l.configure(bg="#e0f2fe"))
            lbl.bind("<Leave>", lambda e, l=lbl: l.configure(bg="#ffffff"))
            lbl.bind("<Button-1>", lambda e, it=it: self._apply_selection(it))

    def _hide_dropdown(self):
        if self._dropdown is not None:
            d = self._dropdown
            self._dropdown = None
            try:
                d.destroy()
            except Exception:
                pass