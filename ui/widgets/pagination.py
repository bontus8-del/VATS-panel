"""Панель пагинации: селектор размера страницы + навигация.

Логика отображения номеров страниц:
- total <= 7 → показываем все страницы
- иначе: всегда 1 и last, окно ±2 вокруг текущей, разрывы — многоточие
- « ‹ › » дизейблятся на границах
"""
import tkinter as tk
import customtkinter as ctk

import config


class PaginationBar(ctk.CTkFrame):
    def __init__(self, parent, on_change,
                 page_sizes=(10, 20, 50, 100), default_size: int = 20):
        super().__init__(parent, fg_color="transparent")
        self.on_change = on_change
        self.page_sizes = page_sizes
        self.page_size = default_size
        self.page = 1
        self.total = 0
        self._build()
        self._update_state()

    # --- публичный API ---
    @property
    def total_pages(self) -> int:
        if self.total <= 0:
            return 1
        return (self.total + self.page_size - 1) // self.page_size

    def slice(self, items):
        """Вернуть подсписок items для текущей страницы."""
        start = (self.page - 1) * self.page_size
        return items[start:start + self.page_size]

    def set_total(self, total: int, reset_page: bool = False):
        """Обновить общее количество элементов.

        reset_page=True — вернуться на первую страницу (используется при поиске
        и при новой загрузке данных).
        """
        self.total = max(0, total)
        if reset_page:
            self.page = 1
        max_page = self.total_pages
        if self.page > max_page:
            self.page = max_page
        if self.page < 1:
            self.page = 1
        self._rebuild_numbers()
        self._update_state()
        self.on_change(self.page, self.page_size)

    def go_to(self, page: int):
        page = max(1, min(page, self.total_pages))
        if page == self.page:
            return
        self.page = page
        self._rebuild_numbers()
        self._update_state()
        self.on_change(self.page, self.page_size)

    # --- UI ---
    def _build(self):
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.pack(side="left")
        ctk.CTkLabel(left, text="Отображать по:",
                     font=ctk.CTkFont(size=12),
                     text_color=config.TEXT_MUTED).pack(side="left", padx=(0, 6))

        self.size_var = tk.StringVar(value=str(self.page_size))
        ctk.CTkOptionMenu(
            left,
            values=[str(s) for s in self.page_sizes],
            variable=self.size_var,
            width=78, height=28,
            fg_color="#e2e8f0",
            button_color="#cbd5e1",
            button_hover_color="#94a3b8",
            text_color=config.TEXT_MAIN,
            font=ctk.CTkFont(size=12),
            dropdown_font=ctk.CTkFont(size=12),
            corner_radius=6,
            command=self._on_size_change,
        ).pack(side="left")

        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.pack(side="right")

        self.btn_first = self._nav_btn(nav, "«", lambda: self.go_to(1))
        self.btn_prev = self._nav_btn(nav, "‹", lambda: self.go_to(self.page - 1))

        self.numbers = ctk.CTkFrame(nav, fg_color="transparent")
        self.numbers.pack(side="left", padx=4)

        self.btn_next = self._nav_btn(nav, "›", lambda: self.go_to(self.page + 1))
        self.btn_last = self._nav_btn(nav, "»", lambda: self.go_to(self.total_pages))

    def _nav_btn(self, parent, text, command):
        btn = ctk.CTkButton(
            parent, text=text, width=30, height=28,
            fg_color="#e2e8f0", text_color=config.TEXT_MAIN,
            hover_color="#cbd5e1",
            font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=6, command=command,
        )
        btn.pack(side="left", padx=1)
        return btn

    def _rebuild_numbers(self):
        for w in self.numbers.winfo_children():
            w.destroy()

        total = self.total_pages
        if total <= 1:
            return

        for p in self._page_range():
            if p is None:
                ctk.CTkLabel(self.numbers, text="…", width=16,
                             text_color=config.TEXT_MUTED,
                             font=ctk.CTkFont(size=12)).pack(side="left")
                continue

            is_cur = (p == self.page)
            ctk.CTkButton(
                self.numbers, text=str(p), width=32, height=28,
                fg_color=config.RED_ACCENT if is_cur else "#e2e8f0",
                text_color="#ffffff" if is_cur else config.TEXT_MAIN,
                hover_color=config.RED_HOVER if is_cur else "#cbd5e1",
                font=ctk.CTkFont(size=12, weight="bold" if is_cur else "normal"),
                corner_radius=6,
                command=lambda pp=p: self.go_to(pp),
            ).pack(side="left", padx=1)

    def _page_range(self):
        total = self.total_pages
        cur = self.page
        if total <= 7:
            return list(range(1, total + 1))

        pages = {1, total}
        for p in range(cur - 2, cur + 3):
            if 1 <= p <= total:
                pages.add(p)

        sorted_pages = sorted(pages)
        result = []
        for i, p in enumerate(sorted_pages):
            if i > 0 and p - sorted_pages[i - 1] > 1:
                result.append(None)  # многоточие
            result.append(p)
        return result

    def _update_state(self):
        total = self.total_pages
        at_first = self.page <= 1
        at_last = self.page >= total
        self.btn_first.configure(state="disabled" if at_first else "normal")
        self.btn_prev.configure(state="disabled" if at_first else "normal")
        self.btn_next.configure(state="disabled" if at_last else "normal")
        self.btn_last.configure(state="disabled" if at_last else "normal")

    def _on_size_change(self, value: str):
        try:
            new_size = int(value)
        except ValueError:
            return
        if new_size == self.page_size:
            return
        self.page_size = new_size
        self.page = 1
        self._rebuild_numbers()
        self._update_state()
        self.on_change(self.page, self.page_size)