"""Простой tooltip для любого виджета Tk/CTk.

Показывается по <Enter> с задержкой, скрывается по <Leave> и по <ButtonPress>.
Позиционируется чуть ниже виджета.
"""
import tkinter as tk


class Tooltip:
    def __init__(self, widget, text: str, delay: int = 500, wraplength: int = 300):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.wraplength = wraplength
        self._tip = None
        self._after_id = None

        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        widget.bind("<ButtonPress>", self._on_leave, add="+")
        widget.bind("<FocusOut>", self._on_leave, add="+")

    def _on_enter(self, _event=None):
        self._cancel()
        self._after_id = self.widget.after(self.delay, self._show)

    def _on_leave(self, _event=None):
        self._cancel()
        self._hide()

    def _cancel(self):
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self):
        self._after_id = None
        if self._tip is not None:
            return

        x = self.widget.winfo_rootx() + 6
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4

        self._tip = tk.Toplevel(self.widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{x}+{y}")
        self._tip.configure(bg="#1f2937")
        try:
            self._tip.attributes("-topmost", True)
        except Exception:
            pass

        tk.Label(
            self._tip, text=self.text, justify="left",
            bg="#1f2937", fg="#ffffff", font=("Segoe UI", 9),
            padx=10, pady=6, wraplength=self.wraplength,
        ).pack()

    def _hide(self):
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None