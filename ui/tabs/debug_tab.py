import tkinter as tk
import customtkinter as ctk

import config
from .base_tab import BaseTab


class DebugTab(BaseTab):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self._build()

    def _build(self):
        card = ctk.CTkFrame(self, fg_color=config.CARD_BG, corner_radius=10,
                            border_color=config.BORDER_COLOR, border_width=1)
        card.pack(fill="both", expand=True, padx=15, pady=2)

        ctk.CTkButton(card, text="📋 Скопировать RAW JSON", fg_color="#e2e8f0",
                      text_color=config.TEXT_MAIN, hover_color="#cbd5e1",
                      font=ctk.CTkFont(size=12, weight="bold"), corner_radius=6, height=32,
                      command=self.copy_raw).pack(anchor="w", padx=15, pady=10)

        self.textbox = ctk.CTkTextbox(card, font=ctk.CTkFont(family="Consolas", size=12),
                                      fg_color="#0f172a", text_color="#38bdf8", corner_radius=6)
        self.textbox.pack(fill="both", expand=True, padx=15, pady=(0, 15))

    def set_raw(self, text: str):
        self.textbox.delete("1.0", tk.END)
        self.textbox.insert(tk.END, text)

    def copy_raw(self):
        self.app.copy_to_clipboard(self.textbox.get("1.0", tk.END).strip())