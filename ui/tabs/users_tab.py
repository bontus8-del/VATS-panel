import tkinter as tk
import customtkinter as ctk

import config
from .base_tab import BaseTab
from ..widgets.pagination import PaginationBar
from api import ExolveApiError


class UsersTab(BaseTab):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.raw_users_data = []
        self._filtered = []
        self.search_var = tk.StringVar()
        self._build()
        self.search_var.trace_add("write", lambda *a: self._schedule_search(self._on_search))

    # --- UI ---
    def _build(self):
        top_card = ctk.CTkFrame(self, fg_color=config.CARD_BG, corner_radius=10,
                                border_color=config.BORDER_COLOR, border_width=1)
        top_card.pack(fill="x", pady=(5, 10), ipady=4, padx=15)

        self.btn_refresh = ctk.CTkButton(
            top_card, text="🔄 Обновить", fg_color=config.RED_ACCENT,
            hover_color=config.RED_HOVER, font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=6, height=36, command=self.load,
        )
        self.btn_refresh.pack(side="left", padx=15, pady=8)

        self.lbl_count = ctk.CTkLabel(top_card, text="Всего в системе: 0",
                                      font=ctk.CTkFont(size=13, weight="bold"),
                                      text_color=config.TEXT_MUTED)
        self.lbl_count.pack(side="left", padx=10)

        ctk.CTkEntry(top_card, placeholder_text="🔍 Поиск по имени, логину...",
                     textvariable=self.search_var, width=250, height=36, corner_radius=6,
                     fg_color="#f8fafc", border_color=config.BORDER_COLOR).pack(side="right", padx=15)

        table_card = ctk.CTkFrame(self, fg_color=config.CARD_BG, corner_radius=10,
                                  border_color=config.BORDER_COLOR, border_width=1)
        table_card.pack(fill="both", expand=True, padx=15, pady=2)

        header_frame = ctk.CTkFrame(table_card, fg_color="#f1f5f9", corner_radius=6, height=38)
        header_frame.pack(fill="x", padx=10, pady=(10, 5))
        header_frame.pack_propagate(False)

        for i, w in enumerate((3, 3, 1, 2, 1)):
            header_frame.grid_columnconfigure(i, weight=w, uniform="col")

        for col, title in enumerate(("ИМЯ ПОЛЬЗОВАТЕЛЯ", "ЛОГИН", "ВН. НОМЕР", "ДОЛЖНОСТЬ", "РОЛЬ")):
            ctk.CTkLabel(header_frame, text=title, font=ctk.CTkFont(size=11, weight="bold"),
                         text_color="#475569", anchor="w").grid(row=0, column=col, padx=12, pady=6, sticky="ew")

        self.scroll = ctk.CTkScrollableFrame(table_card, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=5, pady=5)

        self.pagination = PaginationBar(self, on_change=self._on_page_change)
        self.pagination.pack(fill="x", padx=15, pady=(5, 10))

    def _on_search(self):
        self._search_after_id = None
        self.render(reset_page=True)

    # --- API ---
    def load(self):
        client = self.app.get_client()
        if not client:
            return

        self.btn_refresh.configure(state="disabled")
        self.app.set_status("Загрузка пользователей…", "busy")

        def fetch():
            try:
                items, raw = client.get_users()
                self.app.set_debug_raw(raw)
                self.app.after(0, lambda: self._apply(items))
            except Exception as ex:
                err = ex if isinstance(ex, ExolveApiError) else ExolveApiError(f"Неожиданная ошибка: {ex}")
                self.app.after(0, lambda err=err: self.app.handle_api_error(err))

        def done():
            self.btn_refresh.configure(state="normal")

        self.app.run_async(fetch, on_done=done)

    def _apply(self, items):
        self.raw_users_data = items if isinstance(items, list) else []
        self.app.set_status(f"Загружено пользователей: {len(self.raw_users_data)}", "success")
        self.render(reset_page=True)

    # --- рендер ---
    def render(self, reset_page: bool = False):
        query = self.search_var.get().strip().lower()
        if query:
            self._filtered = [u for u in self.raw_users_data if self._matches(u, query)]
            self.lbl_count.configure(text=f"Всего найдено: {len(self._filtered)}")
        else:
            self._filtered = list(self.raw_users_data)
            self.lbl_count.configure(text=f"Всего в системе: {len(self._filtered)}")

        self.pagination.set_total(len(self._filtered), reset_page=reset_page)

    @staticmethod
    def _matches(u, query: str) -> bool:
        if not isinstance(u, dict):
            return False
        name = str(u.get("name") or u.get("displayName") or u.get("fullName")
                   or (str(u.get("first_name", "")) + " " + str(u.get("last_name", "")))).strip()
        login = str(u.get("login") or u.get("id") or u.get("email") or u.get("username") or "").strip()
        num = str(u.get("ext") or u.get("num") or u.get("extNum")
                  or u.get("extension") or u.get("number") or "").strip()
        return (query in name.lower() or query in login.lower() or query in num.lower())

    def _on_page_change(self, page, page_size):
        self._render_page()

    def _render_page(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        self.selected_row = None
        self.selected_data = None

        for u in self.pagination.slice(self._filtered):
            if not isinstance(u, dict):
                continue
            name = str(u.get("name") or u.get("displayName") or u.get("fullName")
                       or (str(u.get("first_name", "")) + " " + str(u.get("last_name", "")))).strip()
            if not name or name == " ":
                name = "Без имени"
            login = str(u.get("login") or u.get("id") or u.get("email") or u.get("username") or "-").strip()
            num = str(u.get("ext") or u.get("num") or u.get("extNum")
                      or u.get("extension") or u.get("number") or "-").strip()
            pos = str(u.get("position") or u.get("title") or u.get("job") or "-").strip()
            role = str(u.get("role") or "User").strip()

            row = ctk.CTkFrame(self.scroll, fg_color=config.ROW_BG_NORMAL, corner_radius=6, height=42)
            row.pack(fill="x", pady=2, padx=2)
            row.pack_propagate(False)
            for i, w in enumerate((3, 3, 1, 2, 1)):
                row.grid_columnconfigure(i, weight=w, uniform="col")

            lbl_name = ctk.CTkLabel(row, text=name, font=ctk.CTkFont(size=12, weight="bold"),
                                    text_color=config.TEXT_MAIN, anchor="w")
            lbl_name.grid(row=0, column=0, padx=12, pady=6, sticky="ew")

            lbl_login = ctk.CTkLabel(row, text=login, font=ctk.CTkFont(size=12, weight="bold"),
                                     text_color=config.RED_ACCENT, anchor="w")
            lbl_login.grid(row=0, column=1, padx=12, pady=6, sticky="ew")

            lbl_num = ctk.CTkLabel(row, text=num, font=ctk.CTkFont(size=12),
                                   text_color=config.TEXT_MUTED, anchor="w")
            lbl_num.grid(row=0, column=2, padx=12, pady=6, sticky="ew")

            lbl_pos = ctk.CTkLabel(row, text=pos, font=ctk.CTkFont(size=12),
                                   text_color=config.TEXT_MUTED, anchor="w")
            lbl_pos.grid(row=0, column=3, padx=12, pady=6, sticky="ew")

            lbl_role = ctk.CTkLabel(row, text=role, font=ctk.CTkFont(size=12),
                                    text_color=config.TEXT_MUTED, anchor="w")
            lbl_role.grid(row=0, column=4, padx=12, pady=6, sticky="ew")

            full_row_str = f"{name}\t{login}\t{num}\t{pos}\t{role}"
            for w in (row, lbl_name, lbl_login, lbl_num, lbl_pos, lbl_role):
                w.bind("<Button-1>", lambda e, r=row, fs=full_row_str: self.select_row(r, fs))
                w.bind("<Button-3>", lambda e, r=row, fs=full_row_str, n=name, l=login:
                       self._ctx_menu(e, r, fs, n, l))
                w.bind("<Button-2>", lambda e, r=row, fs=full_row_str, n=name, l=login:
                       self._ctx_menu(e, r, fs, n, l))

        self.after_idle(lambda: self._reset_scroll(self.scroll))

    def _ctx_menu(self, event, row_frame, full_row_str, name, login):
        self.select_row(row_frame, full_row_str)
        menu = tk.Menu(self, tearoff=0, font=("Segoe UI", 10))
        menu.add_command(label=f"Скопировать логин ({login})",
                         command=lambda: self.app.copy_to_clipboard(login))
        menu.add_command(label=f"Скопировать имя ({name})",
                         command=lambda: self.app.copy_to_clipboard(name))
        menu.add_separator()
        menu.add_command(label="Скопировать строку целиком",
                         command=lambda: self.app.copy_to_clipboard(full_row_str))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()