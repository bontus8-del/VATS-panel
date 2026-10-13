"""Тёмная шапка приложения: брендинг, домен, ключ, RPS."""
import customtkinter as ctk

import config


class Header(ctk.CTkFrame):
    def __init__(self, parent, domain_var, key_var, rps_var):
        super().__init__(parent, fg_color=config.DARK_HEADER, corner_radius=0, height=80)
        self.pack_propagate(False)
        self.domain_var = domain_var
        self.key_var = key_var
        self.rps_var = rps_var
        self._flash_after_id = None
        self._build()

    def _build(self):
        # --- брендинг ---
        brand_box = ctk.CTkFrame(self, fg_color="transparent")
        brand_box.pack(side="left", padx=24, pady=12)

        top_brand = ctk.CTkFrame(brand_box, fg_color="transparent")
        top_brand.pack(anchor="w")

        ctk.CTkLabel(top_brand, text="📞",
                     font=ctk.CTkFont(size=22)).pack(side="left", padx=(0, 10))

        ctk.CTkLabel(top_brand, text="ВАТС Панель",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color="#ffffff").pack(side="left", padx=(0, 10))

        badge = ctk.CTkFrame(top_brand, fg_color=config.RED_ACCENT, corner_radius=12)
        badge.pack(side="left")
        ctk.CTkLabel(badge, text="MTC EXOLVE",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#ffffff").pack(padx=8, pady=2)

        ctk.CTkLabel(brand_box, text="Интеграционный CRM API клиент",
                     font=ctk.CTkFont(size=11),
                     text_color="#94a3b8").pack(anchor="w", pady=(2, 0))

        # --- авторизация + RPS ---
        auth_box = ctk.CTkFrame(self, fg_color="transparent")
        auth_box.pack(side="right", padx=24, pady=12)

        # RPS (слева от домена)
        r_frame = ctk.CTkFrame(auth_box, fg_color="transparent")
        r_frame.pack(side="left", padx=(0, 12))
        ctk.CTkLabel(r_frame, text="⚙ МАКС. RPS",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#94a3b8").pack(anchor="w")
        self.rps_entry = ctk.CTkEntry(
            r_frame, textvariable=self.rps_var, width=70, height=34,
            corner_radius=6, fg_color="#1f2937", border_color="#374151",
            text_color="#ffffff", font=ctk.CTkFont(size=12), justify="center",
        )
        self.rps_entry.pack(pady=(2, 0))

        # Домен
        d_frame = ctk.CTkFrame(auth_box, fg_color="transparent")
        d_frame.pack(side="left", padx=(0, 12))
        ctk.CTkLabel(d_frame, text="🌐 ДОМЕН ВАТС",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#94a3b8").pack(anchor="w")
        self.domain_entry = ctk.CTkEntry(
            d_frame, textvariable=self.domain_var, width=210, height=34,
            corner_radius=6, fg_color="#1f2937", border_color="#374151",
            text_color="#ffffff", font=ctk.CTkFont(size=12),
        )
        self.domain_entry.pack(pady=(2, 0))

        # Ключ
        k_frame = ctk.CTkFrame(auth_box, fg_color="transparent")
        k_frame.pack(side="left")
        ctk.CTkLabel(k_frame, text="🔑 КЛЮЧ (X-API-KEY)",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#94a3b8").pack(anchor="w")
        self.key_entry = ctk.CTkEntry(
            k_frame, textvariable=self.key_var, show="•", width=230, height=34,
            corner_radius=6, fg_color="#1f2937", border_color="#374151",
            text_color="#ffffff", font=ctk.CTkFont(size=12),
        )
        self.key_entry.pack(pady=(2, 0))

    # --- публичный API для VatsApp ---
    def flash_key_error(self, duration_ms: int = 3000):
        self.key_entry.configure(border_color="#dc2626", border_width=2)
        if self._flash_after_id is not None:
            try:
                self.after_cancel(self._flash_after_id)
            except Exception:
                pass
        self._flash_after_id = self.after(duration_ms, self._reset_key_border)

    def _reset_key_border(self):
        self.key_entry.configure(border_color="#374151", border_width=1)
        self._flash_after_id = None