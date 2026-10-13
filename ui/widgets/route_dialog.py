"""Модальный диалог выбора маршрута для номера/номеров.

Две вкладки: «👤 На сотрудника» и «👥 На отдел».
Возвращает dict параметров для ExolveClient.set_telnum_route или None при отмене.

Поля в result:
  type = "user":   {"type": "user",  "user": login, "user_name": name}
  type = "group":  {"type": "group", "group": gid, "group_name": name}
"""
import customtkinter as ctk

import config
from .autocomplete import AutocompleteEntry


class RouteDialog(ctk.CTkToplevel):
    def __init__(self, parent, app, groups):
        """
        parent — обычно VatsApp
        app — VatsApp (нужен для users_tab.raw_users_data)
        groups — list[dict] загруженных отделов
        """
        super().__init__(parent)
        self.app = app
        self.groups = groups or []
        self.result = None

        self.title("Выбор маршрута")
        self.geometry("540x360")
        self.resizable(False, False)
        self.transient(parent)
        self.configure(fg_color=config.BG_MAIN)

        self._build()

        # Модальность + центрирование + фокус
        self.after(10, self._center_on_parent)
        self.after(20, self._make_modal)
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _make_modal(self):
        try:
            self.grab_set()
            self.focus_force()
        except Exception:
            pass

    def _center_on_parent(self):
        try:
            self.update_idletasks()
            px = self.master.winfo_rootx()
            py = self.master.winfo_rooty()
            pw = self.master.winfo_width()
            ph = self.master.winfo_height()
            w = self.winfo_width()
            h = self.winfo_height()
            x = px + (pw - w) // 2
            y = py + (ph - h) // 2
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass

    # --- построение ---
    def _build(self):
        header = ctk.CTkFrame(self, fg_color=config.CARD_BG, corner_radius=0, height=56)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(header, text="📞 Куда маршрутизировать звонки?",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=config.TEXT_MAIN).pack(side="left", padx=20, pady=15)

        self.tabview = ctk.CTkTabview(
            self,
            corner_radius=8,
            fg_color=config.BG_MAIN,
            segmented_button_fg_color="#e2e8f0",
            segmented_button_selected_color=config.RED_ACCENT,
            segmented_button_selected_hover_color=config.RED_HOVER,
            segmented_button_unselected_color="#f1f5f9",
            segmented_button_unselected_hover_color="#cbd5e1",
        )
        self.tabview.pack(fill="both", expand=True, padx=20, pady=(10, 0))
        self.tabview._segmented_button.configure(
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=config.TEXT_MAIN,
            height=36,
        )

        self.tab_user = self.tabview.add("👤 На сотрудника")
        self.tab_group = self.tabview.add("👥 На отдел")

        # --- вкладка: сотрудник ---
        uf = ctk.CTkFrame(self.tab_user, fg_color="transparent")
        uf.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(uf, text="Логин сотрудника:",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=config.TEXT_MAIN).pack(anchor="w", pady=(0, 4))

        self.user_widget = AutocompleteEntry(
            uf,
            search_callback=self._search_users,
            format_callback=self._format_user,
            select_callback=self._login_of,
            width=460, height=36,
            placeholder="🔍 логин / имя / должность",
            tooltip_text="Начните вводить логин, имя или должность сотрудника.",
        )
        self.user_widget.pack(fill="x")

        # --- вкладка: отдел ---
        gf = ctk.CTkFrame(self.tab_group, fg_color="transparent")
        gf.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(gf, text="Отдел:",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=config.TEXT_MAIN).pack(anchor="w", pady=(0, 4))

        self.group_widget = AutocompleteEntry(
            gf,
            search_callback=self._search_groups,
            format_callback=self._format_group,
            select_callback=self._id_of_group,
            width=460, height=36,
            placeholder="🔍 название / ID отдела",
            tooltip_text=("Список отделов появится при фокусе на поле. "
                          "Можно ввести название или ID вручную."),
            show_all_on_focus=True,
        )
        self.group_widget.pack(fill="x")

        # --- кнопки ---
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=20, pady=15)

        ctk.CTkButton(bar, text="Отмена", width=120, height=36,
                      fg_color="#e2e8f0", text_color=config.TEXT_MAIN,
                      hover_color="#cbd5e1",
                      font=ctk.CTkFont(size=12, weight="bold"),
                      corner_radius=6, command=self._on_cancel).pack(side="right", padx=(6, 0))

        ctk.CTkButton(bar, text="Применить", width=140, height=36,
                      fg_color=config.RED_ACCENT, hover_color=config.RED_HOVER,
                      text_color="#ffffff",
                      font=ctk.CTkFont(size=12, weight="bold"),
                      corner_radius=6, command=self._on_apply).pack(side="right")

    # --- поиск: users ---
    @staticmethod
    def _user_fields(u: dict):
        name = str(u.get("name") or u.get("displayName") or u.get("fullName")
                   or (str(u.get("first_name", "")) + " " + str(u.get("last_name", "")))).strip()
        login = str(u.get("login") or u.get("id") or u.get("email") or u.get("username") or "").strip()
        num = str(u.get("ext") or u.get("num") or u.get("extNum")
                  or u.get("extension") or u.get("number") or "").strip()
        pos = str(u.get("position") or u.get("title") or u.get("job") or "").strip()
        return name, login, num, pos

    def _search_users(self, query: str):
        users = getattr(self.app.users_tab, "raw_users_data", None) or []
        if not users:
            return []
        q = query.lower()
        out = []
        for u in users:
            if not isinstance(u, dict):
                continue
            name, login, num, pos = self._user_fields(u)
            if not login:
                continue
            if (q in name.lower() or q in login.lower()
                    or q in num.lower() or q in pos.lower()):
                out.append(u)
                if len(out) >= 30:
                    break
        return out

    def _format_user(self, u: dict) -> str:
        name, login, num, pos = self._user_fields(u)
        text = f"{login or '?'} — {name or 'Без имени'}"
        if pos:
            text += f" ({pos})"
        return text

    def _login_of(self, u: dict) -> str:
        return self._user_fields(u)[1]

    # --- поиск: groups ---
    @staticmethod
    def _group_fields(g: dict):
        gid = str(g.get("id") or "").strip()
        name = str(g.get("name") or "").strip()
        ext = str(g.get("ext") or "").strip()
        return gid, name, ext

    def _search_groups(self, query: str):
        q = query.lower().strip()
        out = []
        for g in self.groups:
            if not isinstance(g, dict):
                continue
            gid, name, ext = self._group_fields(g)
            if not gid:
                continue
            if not q or (q in name.lower() or q in gid.lower() or q in ext.lower()):
                out.append(g)
                if len(out) >= 50:
                    break
        return out

    def _format_group(self, g: dict) -> str:
        gid, name, ext = self._group_fields(g)
        text = f"{name or 'Без имени'} ({gid})"
        if ext:
            text += f" · вн. {ext}"
        return text

    def _id_of_group(self, g: dict) -> str:
        return self._group_fields(g)[0]

    # --- кнопки ---
    def _on_apply(self):
        tab = self.tabview.get()
        if "👤" in tab or "сотрудника" in tab.lower():
            login = self.user_widget.get().strip()
            if not login:
                self.app.show_warning("Валидация", "Укажите логин сотрудника.")
                return
            # Пробуем найти имя по логину
            user_name = ""
            users = getattr(self.app.users_tab, "raw_users_data", None) or []
            for u in users:
                if not isinstance(u, dict):
                    continue
                name, l, _, _ = self._user_fields(u)
                if l == login:
                    user_name = name
                    break
            self.result = {
                "type": "user",
                "user": login,
                "user_name": user_name,
            }
        else:
            gid = self.group_widget.get().strip()
            if not gid:
                self.app.show_warning("Валидация", "Укажите идентификатор отдела.")
                return
            group_name = ""
            for g in self.groups:
                if not isinstance(g, dict):
                    continue
                g_id, g_name, _ = self._group_fields(g)
                if g_id == gid:
                    group_name = g_name
                    break
            self.result = {
                "type": "group",
                "group": gid,
                "group_name": group_name,
            }
        self._close()

    def _on_cancel(self):
        self.result = None
        self._close()

    def _close(self):
        try:
            self.grab_release()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass