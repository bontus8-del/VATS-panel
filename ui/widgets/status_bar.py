"""Тонкий статус-бар внизу окна."""
import time

import customtkinter as ctk

import config


_KIND_COLORS = {
    "info": config.TEXT_MUTED,
    "success": "#16a34a",
    "warning": "#d97706",
    "error": "#dc2626",
    "busy": "#3b82f6",
}


class StatusBar(ctk.CTkFrame):
    def __init__(self, parent, height: int = 28):
        super().__init__(parent, fg_color="#f1f5f9", corner_radius=0, height=height)
        self.pack_propagate(False)
        self._build()

    def _build(self):
        self.lbl_left = ctk.CTkLabel(
            self, text="Готово", anchor="w",
            font=ctk.CTkFont(size=11), text_color=config.TEXT_MUTED,
        )
        self.lbl_left.pack(side="left", padx=12, fill="x", expand=True)

        self.lbl_right = ctk.CTkLabel(
            self, text="", anchor="e",
            font=ctk.CTkFont(size=11), text_color=config.TEXT_MUTED,
        )
        self.lbl_right.pack(side="right", padx=12)

    def set_status(self, text: str, kind: str = "info"):
        self.lbl_left.configure(
            text=text,
            text_color=_KIND_COLORS.get(kind, config.TEXT_MUTED),
        )
        # При "busy" время не показываем, иначе — текущее
        if kind == "busy":
            self.lbl_right.configure(text="")
        else:
            self.lbl_right.configure(text=time.strftime("%H:%M:%S"))