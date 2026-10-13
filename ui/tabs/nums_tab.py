"""Вкладка «Номера ВАТС».

- данные из /crmapi/v1/telnums (поле disabled)
- колонки: [✓] | Номер | Название | Маршрут | Статус | [Действие]
- выделение чекбоксами, сохраняется между страницами
- массовые кнопки выделения + меню ⋮
- единая кнопка массового действия (меняет текст/цвет/команду)
- РЕАЛЬНЫЕ действия:
  * строка: enabled → disable; disabled+маршрут → enable; disabled+без маршрута →
    RouteDialog → set_route с disabled=false (без отдельного /enabled)
  * массово: включение через RouteDialog → set_route с disabled=false;
            выключение — /enabled DELETE
- группы кэшируются на сессию вкладки (self._groups_cache)
- прогресс «Обработано N из M» в статус-баре (троттлинг 300 мс)
- ФИНАЛИЗАЦИЯ выполняется ТОЛЬКО в главном потоке (через app.after)
- отчёт в DebugTab; сводка — тостом
"""
import json
import time
import tkinter as tk
from datetime import datetime

import customtkinter as ctk

import config
from .base_tab import BaseTab
from ..widgets.pagination import PaginationBar
from ..widgets.route_dialog import RouteDialog
from api import ExolveApiError


PROGRESS_THROTTLE_S = 0.3  # не чаще одного обновления статуса в 300 мс


def _normalize_disabled(value) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("", "0", "false", "no", "off", "enabled", "включен", "нет"):
            return False
        if v in ("1", "true", "yes", "on", "disabled", "отключен", "да"):
            return True
    return bool(value)


def _route_text(item: dict) -> str:
    t = str(item.get("type") or "").lower()
    if t == "user":
        user = item.get("user") or ""
        user_name = item.get("user_name") or ""
        if user and user_name:
            return f"👤 {user_name} ({user})"
        if user:
            return f"👤 {user}"
        return "👤 Сотрудник (не задан)"
    if t == "group":
        grp = item.get("group") or ""
        grp_name = item.get("group_name") or ""
        if grp and grp_name:
            return f"👥 {grp_name} ({grp})"
        if grp:
            return f"👥 {grp}"
        return "👥 Отдел (не задан)"
    if t == "ivr":
        return "☎ Меню самообслуживания"
    if t == "scheduler":
        return "⏰ Расписание"
    if t == "fax":
        return "📠 Факс"
    if t == "voicemail":
        return "📭 Автоответчик"
    if t == "hangup":
        return "🚫 Сообщение о нерабочем времени"
    if t == "duty":
        return "👮 Дежурный"
    if not t:
        return "— не задан"
    return t


def _has_routable_route(item: dict) -> bool:
    return bool(str(item.get("type") or "").strip())


def _route_body(route_params: dict) -> dict:
    """Минимальный body для POST /telnums/{telnum}.

    Согласно документации достаточно {type, user|group, disabled}.
    Поля user_name/group_name не отправляем — их вычислит сервер.
    """
    body = {"disabled": False}
    rtype = route_params.get("type")
    if rtype == "user":
        body["type"] = "user"
        body["user"] = route_params.get("user", "")
    elif rtype == "group":
        body["type"] = "group"
        body["group"] = route_params.get("group", "")
    return body


class NumsTab(BaseTab):
    COL_CHECK = 0
    COL_NUM = 1
    COL_NAME = 2
    COL_ROUTE = 3
    COL_STATUS = 4
    COL_ACTION = 5

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.raw_nums_data: list = []
        self._filtered: list = []
        self._selected: set = set()
        self._groups_cache = None
        self._action_mode = None
        self._busy = False
        self.search_var = tk.StringVar()
        self._build()
        self.search_var.trace_add("write", lambda *a: self._schedule_search(self._on_search))

    # --- построение ---
    def _build(self):
        top_card = ctk.CTkFrame(self, fg_color=config.CARD_BG, corner_radius=10,
                                border_color=config.BORDER_COLOR, border_width=1)
        top_card.pack(fill="x", pady=(5, 6), ipady=4, padx=15)

        self.btn_refresh = ctk.CTkButton(
            top_card, text="🔄 Обновить", fg_color=config.RED_ACCENT,
            hover_color=config.RED_HOVER, font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=6, height=36, command=self.load,
        )
        self.btn_refresh.pack(side="left", padx=15, pady=8)

        self.lbl_count = ctk.CTkLabel(top_card, text="Всего номеров: 0",
                                      font=ctk.CTkFont(size=13, weight="bold"),
                                      text_color=config.TEXT_MUTED)
        self.lbl_count.pack(side="left", padx=10)

        ctk.CTkEntry(top_card, placeholder_text="🔍 Поиск по номеру, имени, маршруту...",
                     textvariable=self.search_var, width=280, height=36, corner_radius=6,
                     fg_color="#f8fafc", border_color=config.BORDER_COLOR
                     ).pack(side="right", padx=15)

        self._build_actions_bar()

        table_card = ctk.CTkFrame(self, fg_color=config.CARD_BG, corner_radius=10,
                                  border_color=config.BORDER_COLOR, border_width=1)
        table_card.pack(fill="both", expand=True, padx=15, pady=2)

        header_frame = ctk.CTkFrame(table_card, fg_color="#f1f5f9", corner_radius=6, height=38)
        header_frame.pack(fill="x", padx=10, pady=(10, 5))
        header_frame.pack_propagate(False)
        self._configure_row_columns(header_frame)

        for col, title in (
            (self.COL_CHECK, ""),
            (self.COL_NUM, "НОМЕР"),
            (self.COL_NAME, "НАЗВАНИЕ"),
            (self.COL_ROUTE, "МАРШРУТ"),
            (self.COL_STATUS, "СТАТУС"),
            (self.COL_ACTION, "ДЕЙСТВИЕ"),
        ):
            ctk.CTkLabel(header_frame, text=title,
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color="#475569", anchor="w"
                         ).grid(row=0, column=col, padx=8, pady=6, sticky="ew")

        self.scroll = ctk.CTkScrollableFrame(table_card, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=5, pady=5)

        self.pagination = PaginationBar(self, on_change=self._on_page_change)
        self.pagination.pack(fill="x", padx=15, pady=(5, 10))

    def _build_actions_bar(self):
        bar = ctk.CTkFrame(self, fg_color=config.CARD_BG, corner_radius=8,
                           border_color=config.BORDER_COLOR, border_width=1)
        bar.pack(fill="x", padx=15, pady=(0, 6), ipady=3)

        left = ctk.CTkFrame(bar, fg_color="transparent")
        left.pack(side="left", padx=10, pady=4)

        self.btn_select_all = ctk.CTkButton(
            left, text="☑ Выделить всё", width=160, height=30,
            fg_color="#e2e8f0", text_color=config.TEXT_MAIN, hover_color="#cbd5e1",
            font=ctk.CTkFont(size=12, weight="bold"), corner_radius=6,
            command=self._on_toggle_select_all,
        )
        self.btn_select_all.pack(side="left", padx=(0, 2))

        self.btn_select_more = ctk.CTkButton(
            left, text="⋮", width=30, height=30,
            fg_color="#e2e8f0", text_color=config.TEXT_MAIN, hover_color="#cbd5e1",
            font=ctk.CTkFont(size=14, weight="bold"), corner_radius=6,
            command=self._show_select_menu,
        )
        self.btn_select_more.pack(side="left")

        self.lbl_selected = ctk.CTkLabel(bar, text="Выбрано: 0",
                                         font=ctk.CTkFont(size=12, weight="bold"),
                                         text_color=config.TEXT_MUTED)
        self.lbl_selected.pack(side="left", padx=15)

        self.btn_action = ctk.CTkButton(
            bar, text="Изменить статус", width=190, height=30,
            fg_color="#94a3b8", hover_color="#94a3b8",
            text_color="#ffffff", font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=6, command=self._on_action_click,
            state="disabled",
        )
        self.btn_action.pack(side="right", padx=(4, 10), pady=4)

        self._update_actions_bar()

    @staticmethod
    def _configure_row_columns(frame):
        frame.grid_columnconfigure(NumsTab.COL_CHECK, weight=0, minsize=40)
        frame.grid_columnconfigure(NumsTab.COL_NUM, weight=0, minsize=140)
        frame.grid_columnconfigure(NumsTab.COL_NAME, weight=2, uniform="col")
        frame.grid_columnconfigure(NumsTab.COL_ROUTE, weight=3, uniform="col")
        frame.grid_columnconfigure(NumsTab.COL_STATUS, weight=1, uniform="col")
        frame.grid_columnconfigure(NumsTab.COL_ACTION, weight=0, minsize=100)

    def _set_busy(self, busy: bool):
        self._busy = busy
        state = "disabled" if busy else "normal"
        self.btn_refresh.configure(state=state)
        self.btn_select_all.configure(state=state)
        self.btn_select_more.configure(state=state)
        if busy:
            self.btn_action.configure(state="disabled")
        else:
            self._update_actions_bar()

    # --- поиск ---
    def _on_search(self):
        self._search_after_id = None
        self.render(reset_page=True)

    # --- API: номера ---
    def load(self):
        client = self.app.get_client()
        if not client:
            return

        self._groups_cache = None

        self.btn_refresh.configure(state="disabled")
        self.app.set_status("Загрузка номеров…", "busy")

        def fetch():
            try:
                items, raw = client.get_telnums()
                self.app.set_debug_raw(raw)
                self.app.after(0, lambda: self._apply(items))
            except Exception as ex:
                err = ex if isinstance(ex, ExolveApiError) else ExolveApiError(f"Неожиданная ошибка: {ex}")
                self.app.after(0, lambda err=err: self.app.handle_api_error(err))

        def done():
            self.btn_refresh.configure(state="normal")

        self.app.run_async(fetch, on_done=done)

    def _apply(self, items):
        self.raw_nums_data = items if isinstance(items, list) else []
        actual = {self._telnum(n) for n in self.raw_nums_data if isinstance(n, dict)}
        self._selected &= actual
        self.app.set_status(f"Загружено номеров: {len(self.raw_nums_data)}", "success")
        self.render(reset_page=True)

    # --- API: группы ---
    def _ensure_groups(self, on_ready):
        """Загрузить группы (если нет в кэше) и вызвать on_ready(groups, error)
        в главном потоке."""
        if self._groups_cache is not None:
            on_ready(self._groups_cache, None)
            return
        client = self.app.get_client()
        if not client:
            on_ready([], "Нет клиента")
            return

        self.app.set_status("Загрузка групп…", "busy")

        def fetch():
            try:
                items, raw = client.get_groups()
                self._groups_cache = items if isinstance(items, list) else []
                self.app.after(0, lambda: on_ready(self._groups_cache, None))
            except ExolveApiError as e:
                self.app.after(0, lambda e=e: on_ready([], str(e)))
            except Exception as e:
                self.app.after(0, lambda e=e: on_ready([], f"Неожиданная ошибка: {e}"))

        self.app.run_async(fetch)

    # --- фильтрация / рендер ---
    def render(self, reset_page: bool = False):
        query = self.search_var.get().strip().lower()
        if query:
            self._filtered = [n for n in self.raw_nums_data
                              if isinstance(n, dict) and self._matches(n, query)]
            self.lbl_count.configure(text=f"Найдено номеров: {len(self._filtered)}")
        else:
            self._filtered = [n for n in self.raw_nums_data if isinstance(n, dict)]
            self.lbl_count.configure(text=f"Всего номеров: {len(self._filtered)}")

        self.pagination.set_total(len(self._filtered), reset_page=reset_page)
        self._update_actions_bar()

    @staticmethod
    def _telnum(item: dict) -> str:
        return str(item.get("telnum", item.get("phone", item.get("number", ""))))

    def _matches(self, item: dict, query: str) -> bool:
        fields = [
            self._telnum(item),
            item.get("name", ""),
            item.get("user", ""),
            item.get("user_name", ""),
            item.get("group", ""),
            item.get("group_name", ""),
        ]
        return any(query in str(f).lower() for f in fields)

    def _find_item(self, telnum: str):
        for n in self.raw_nums_data:
            if isinstance(n, dict) and self._telnum(n) == telnum:
                return n
        return None

    def _on_page_change(self, page, page_size):
        self._render_page()

    def _render_page(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        self.selected_row = None
        self.selected_data = None

        for item in self.pagination.slice(self._filtered):
            self._render_row(item)

        self.after_idle(lambda: self._reset_scroll(self.scroll))

    def _render_row(self, item: dict):
        telnum = self._telnum(item)
        name = str(item.get("name") or "").strip() or "—"
        route = _route_text(item)
        disabled = _normalize_disabled(item.get("disabled"))

        row = ctk.CTkFrame(self.scroll, fg_color=config.ROW_BG_NORMAL,
                           corner_radius=6, height=46)
        row.pack(fill="x", pady=2, padx=2)
        row.pack_propagate(False)
        self._configure_row_columns(row)

        var = ctk.BooleanVar(value=telnum in self._selected)
        chk = ctk.CTkCheckBox(
            row, text="", width=24, height=24, variable=var,
            checkbox_width=20, checkbox_height=20,
            fg_color=config.RED_ACCENT, hover_color=config.RED_HOVER,
            border_color="#94a3b8", corner_radius=4,
            command=lambda tn=telnum, v=var: self._on_checkbox(tn, v.get()),
        )
        chk.grid(row=0, column=self.COL_CHECK, padx=(12, 4), pady=8, sticky="w")

        lbl_num = ctk.CTkLabel(row, text=telnum,
                               font=ctk.CTkFont(size=12, weight="bold"),
                               text_color=config.TEXT_MAIN, anchor="w")
        lbl_num.grid(row=0, column=self.COL_NUM, padx=8, pady=8, sticky="ew")

        lbl_name = ctk.CTkLabel(row, text=name, font=ctk.CTkFont(size=12),
                                text_color=config.TEXT_MAIN, anchor="w")
        lbl_name.grid(row=0, column=self.COL_NAME, padx=8, pady=8, sticky="ew")

        lbl_route = ctk.CTkLabel(row, text=route, font=ctk.CTkFont(size=12),
                                 text_color=config.TEXT_MUTED, anchor="w")
        lbl_route.grid(row=0, column=self.COL_ROUTE, padx=8, pady=8, sticky="ew")

        if disabled:
            status_color, status_bg, status_text = "#dc2626", "#fee2e2", "○ Отключен"
        else:
            status_color, status_bg, status_text = "#16a34a", "#dcfce7", "● Включен"
        badge = ctk.CTkFrame(row, fg_color=status_bg, corner_radius=6)
        badge.grid(row=0, column=self.COL_STATUS, padx=8, pady=8, sticky="w")
        lbl_status = ctk.CTkLabel(badge, text=status_text,
                                  font=ctk.CTkFont(size=11, weight="bold"),
                                  text_color=status_color)
        lbl_status.pack(padx=10, pady=2)

        action_text = "Вкл" if disabled else "Выкл"
        btn_action = ctk.CTkButton(
            row, text=action_text, width=72, height=28,
            fg_color="#bbf7d0" if disabled else "#fecaca",
            text_color="#166534" if disabled else "#991b1b",
            hover_color="#86efac" if disabled else "#fca5a5",
            font=ctk.CTkFont(size=11, weight="bold"),
            corner_radius=6,
            command=lambda tn=telnum: self._on_row_action(tn),
        )
        btn_action.grid(row=0, column=self.COL_ACTION, padx=(4, 12), pady=8)

        for w in (row, lbl_num, lbl_name, lbl_route, badge, lbl_status):
            w.bind("<Button-3>", lambda e, t=telnum: self._ctx_menu(e, t))
            w.bind("<Button-2>", lambda e, t=telnum: self._ctx_menu(e, t))
            w.bind("<Button-1>", lambda e, r=row, t=telnum: self.select_row(r, t),
                   add="+")

    # --- выделение ---
    def _on_checkbox(self, telnum: str, is_selected: bool):
        if is_selected:
            self._selected.add(telnum)
        else:
            self._selected.discard(telnum)
        self._update_actions_bar()

    def _on_toggle_select_all(self):
        all_telnums = [self._telnum(n) for n in self._filtered]
        if all_telnums and all(t in self._selected for t in all_telnums):
            for t in all_telnums:
                self._selected.discard(t)
        else:
            for t in all_telnums:
                self._selected.add(t)
        self._render_page()
        self._update_actions_bar()

    def _show_select_menu(self):
        menu = tk.Menu(self, tearoff=0, font=("Segoe UI", 10))
        menu.add_command(label="Выделить включенные", command=self._select_enabled)
        menu.add_command(label="Выделить отключенные", command=self._select_disabled)
        menu.add_separator()
        menu.add_command(label="Снять выделение", command=self._clear_selection)
        try:
            x = self.btn_select_more.winfo_rootx()
            y = self.btn_select_more.winfo_rooty() + self.btn_select_more.winfo_height()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _select_enabled(self):
        self._selected.clear()
        for n in self._filtered:
            if isinstance(n, dict) and not _normalize_disabled(n.get("disabled")):
                self._selected.add(self._telnum(n))
        self._render_page()
        self._update_actions_bar()

    def _select_disabled(self):
        self._selected.clear()
        for n in self._filtered:
            if isinstance(n, dict) and _normalize_disabled(n.get("disabled")):
                self._selected.add(self._telnum(n))
        self._render_page()
        self._update_actions_bar()

    def _clear_selection(self):
        self._selected.clear()
        self._render_page()
        self._update_actions_bar()

    def _count_selected_by_status(self):
        enabled = 0
        disabled = 0
        for n in self.raw_nums_data:
            if not isinstance(n, dict):
                continue
            if self._telnum(n) in self._selected:
                if _normalize_disabled(n.get("disabled")):
                    disabled += 1
                else:
                    enabled += 1
        return enabled, disabled

    def _update_actions_bar(self):
        n = len(self._selected)
        self.lbl_selected.configure(text=f"Выбрано: {n}")

        all_telnums = [self._telnum(x) for x in self._filtered]
        if all_telnums and all(t in self._selected for t in all_telnums):
            self.btn_select_all.configure(text="☐ Снять выделение")
        else:
            self.btn_select_all.configure(text="☑ Выделить всё")

        if n == 0:
            self._action_mode = None
            self.btn_action.configure(
                state="disabled",
                text="Изменить статус",
                fg_color="#94a3b8", hover_color="#94a3b8",
                text_color="#ffffff",
            )
            return

        enabled, disabled = self._count_selected_by_status()
        if enabled > disabled:
            self._action_mode = "disable"
            self.btn_action.configure(
                state="normal",
                text=f"❌ Выключить ({n})",
                fg_color="#dc2626", hover_color="#b91c1c",
                text_color="#ffffff",
            )
        else:
            self._action_mode = "enable"
            self.btn_action.configure(
                state="normal",
                text=f"✅ Включить ({n})",
                fg_color="#16a34a", hover_color="#15803d",
                text_color="#ffffff",
            )

    # === ДЕЙСТВИЯ ===

    def _on_action_click(self):
        if self._busy:
            return
        mode = self._action_mode
        if mode == "enable":
            self._bulk_enable_flow()
        elif mode == "disable":
            self._bulk_disable_flow()

    # --- строка ---
    def _on_row_action(self, telnum: str):
        if self._busy:
            return
        item = self._find_item(telnum)
        if not item:
            return
        disabled = _normalize_disabled(item.get("disabled"))
        if not disabled:
            self._do_disable_single(telnum)
        else:
            if _has_routable_route(item):
                self._do_enable_single(telnum, route_params=None)
            else:
                self._single_enable_with_dialog(telnum)

    def _single_enable_with_dialog(self, telnum: str):
        def on_groups(groups, err):
            if err:
                self.app.show_error("Ошибка", f"Не удалось загрузить группы:\n{err}")
                return
            dialog = RouteDialog(self.app, self.app, groups)
            self.app.wait_window(dialog)
            params = dialog.result
            if not params:
                return
            self._do_enable_single(telnum, route_params=params)

        self._ensure_groups(on_groups)

    def _do_disable_single(self, telnum: str):
        client = self.app.get_client()
        if not client:
            return
        self._set_busy(True)
        self.app.set_status(f"Выключение {telnum}…", "busy")

        def worker():
            try:
                client.disable_telnum(telnum)
                self.app.after(0, lambda: self._on_single_success(telnum, enabled=False))
            except ExolveApiError as e:
                self.app.after(0, lambda e=e: self.app.handle_api_error(e))

        def done():
            self._set_busy(False)

        self.app.run_async(worker, on_done=done)

    def _do_enable_single(self, telnum: str, route_params=None):
        """Включение одиночного номера.

        Если route_params задан — одним запросом set_telnum_route с disabled=False.
        Если нет (маршрут уже есть) — просто enable_telnum.
        """
        client = self.app.get_client()
        if not client:
            return
        self._set_busy(True)
        self.app.set_status(f"Включение {telnum}…", "busy")

        def worker():
            try:
                if route_params:
                    client.set_telnum_route(telnum, _route_body(route_params))
                else:
                    client.enable_telnum(telnum)
                self.app.after(0, lambda: self._on_single_success(
                    telnum, enabled=True, route_params=route_params))
            except ExolveApiError as e:
                self.app.after(0, lambda e=e: self.app.handle_api_error(e))

        def done():
            self._set_busy(False)

        self.app.run_async(worker, on_done=done)

    def _on_single_success(self, telnum: str, enabled: bool, route_params=None):
        item = self._find_item(telnum)
        if item is not None:
            item["disabled"] = not enabled
            if route_params:
                item["type"] = route_params.get("type", "")
                if route_params.get("type") == "user":
                    item["user"] = route_params.get("user", "")
                    item["user_name"] = route_params.get("user_name", "")
                elif route_params.get("type") == "group":
                    item["group"] = route_params.get("group", "")
                    item["group_name"] = route_params.get("group_name", "")
        self._render_page()
        self.app.set_status(f"Готово: {telnum}", "success")

    # --- массовые ---
    def _bulk_enable_flow(self):
        telnums = sorted(self._selected)
        if not telnums:
            return

        def on_groups(groups, err):
            if err:
                self.app.show_error("Ошибка", f"Не удалось загрузить группы:\n{err}")
                return
            dialog = RouteDialog(self.app, self.app, groups)
            self.app.wait_window(dialog)
            params = dialog.result
            if not params:
                return
            self._bulk_enable(telnums, params)

        self._ensure_groups(on_groups)

    def _bulk_disable_flow(self):
        telnums = sorted(self._selected)
        if not telnums:
            return
        self._bulk_disable(telnums)

    def _bulk_enable(self, telnums: list, route_params: dict):
        client = self.app.get_client()
        if not client:
            return
        total = len(telnums)
        self._set_busy(True)
        body = _route_body(route_params)

        def worker():
            results = []
            last_ts = 0.0
            for i, tn in enumerate(telnums, 1):
                entry = {"telnum": tn, "status": "ok", "error": None}
                try:
                    client.set_telnum_route(tn, body)
                except ExolveApiError as e:
                    entry["status"] = "error"
                    entry["error"] = str(e)
                except Exception as e:
                    entry["status"] = "error"
                    entry["error"] = f"Неожиданная ошибка: {e}"
                results.append(entry)

                now = time.monotonic()
                if now - last_ts >= PROGRESS_THROTTLE_S or i == total:
                    last_ts = now
                    self.app.after(0, lambda i=i, t=total: self.app.set_status(
                        f"Включение {i} из {t}…", "busy"))

            self.app.after(0, lambda: self._finalize_bulk(
                "enable", telnums, route_params, results))

        def done():
            self._set_busy(False)

        self.app.run_async(worker, on_done=done)

    def _bulk_disable(self, telnums: list):
        client = self.app.get_client()
        if not client:
            return
        total = len(telnums)
        self._set_busy(True)

        def worker():
            results = []
            last_ts = 0.0
            for i, tn in enumerate(telnums, 1):
                entry = {"telnum": tn, "status": "ok", "error": None}
                try:
                    client.disable_telnum(tn)
                except ExolveApiError as e:
                    entry["status"] = "error"
                    entry["error"] = str(e)
                except Exception as e:
                    entry["status"] = "error"
                    entry["error"] = f"Неожиданная ошибка: {e}"
                results.append(entry)

                now = time.monotonic()
                if now - last_ts >= PROGRESS_THROTTLE_S or i == total:
                    last_ts = now
                    self.app.after(0, lambda i=i, t=total: self.app.set_status(
                        f"Выключение {i} из {t}…", "busy"))

            self.app.after(0, lambda: self._finalize_bulk(
                "disable", telnums, None, results))

        def done():
            self._set_busy(False)

        self.app.run_async(worker, on_done=done)

    def _finalize_bulk(self, action: str, telnums: list, route_params, results: list):
        """Выполняется только в главном потоке (вызывается через app.after)."""
        for r in results:
            if r["status"] != "ok":
                continue
            item = self._find_item(r["telnum"])
            if item is None:
                continue
            if action == "enable":
                item["disabled"] = False
                if route_params:
                    item["type"] = route_params.get("type", "")
                    if route_params.get("type") == "user":
                        item["user"] = route_params.get("user", "")
                        item["user_name"] = route_params.get("user_name", "")
                    elif route_params.get("type") == "group":
                        item["group"] = route_params.get("group", "")
                        item["group_name"] = route_params.get("group_name", "")
            else:
                item["disabled"] = True

        ok = sum(1 for r in results if r["status"] == "ok")
        failed = len(results) - ok
        report = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": action,
            "route": route_params,
            "total": len(results),
            "ok": ok,
            "failed": failed,
            "items": results,
        }
        self.app.set_debug_raw(json.dumps(report, ensure_ascii=False, indent=2))

        verb = "включено" if action == "enable" else "выключено"
        if failed == 0:
            self.app.show_info("Готово", f"Успешно {verb}: {ok} из {len(results)}.")
        else:
            self.app.show_warning(
                "Завершено с ошибками",
                f"{verb.capitalize()}: {ok}, с ошибками: {failed} (всего {len(results)}).\n"
                f"Подробности — во вкладке «RAW Ответ (Debug)»."
            )

        self._render_page()

    # --- контекстное меню ---
    def _ctx_menu(self, event, telnum: str):
        menu = tk.Menu(self, tearoff=0, font=("Segoe UI", 10))
        menu.add_command(label=f"Скопировать номер ({telnum})",
                         command=lambda: self.app.copy_to_clipboard(telnum))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()