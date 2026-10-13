import json
from datetime import datetime

import customtkinter as ctk

import config
from .base_tab import BaseTab
from ..widgets.autocomplete import AutocompleteEntry
from api import ExolveApiError


class ReplaceTab(BaseTab):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.rows = []
        self._build()
        self.add_row()

    def _build(self):
        top_card = ctk.CTkFrame(self, fg_color=config.CARD_BG, corner_radius=10,
                                border_color=config.BORDER_COLOR, border_width=1)
        top_card.pack(fill="x", pady=(5, 10), ipady=4, padx=15)

        title_box = ctk.CTkFrame(top_card, fg_color="transparent")
        title_box.pack(side="left", padx=15)
        ctk.CTkLabel(title_box, text="Массовая привязка номеров к логинам",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=config.TEXT_MAIN).pack(anchor="w")
        ctk.CTkLabel(title_box,
                     text="💡 Начните вводить логин или номер — появятся подсказки. "
                          "Ручной ввод тоже работает.",
                     font=ctk.CTkFont(size=10),
                     text_color=config.TEXT_MUTED).pack(anchor="w")

        self.btn_run = ctk.CTkButton(
            top_card, text="🚀 Поменять номера", fg_color=config.RED_ACCENT,
            hover_color=config.RED_HOVER, font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=6, height=36, command=self.execute,
        )
        self.btn_run.pack(side="right", padx=15, pady=8)

        card = ctk.CTkFrame(self, fg_color=config.CARD_BG, corner_radius=10,
                            border_color=config.BORDER_COLOR, border_width=1)
        card.pack(fill="both", expand=True, padx=15, pady=2)

        self.scroll = ctk.CTkScrollableFrame(card, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=10, pady=10)

        self.btn_add = ctk.CTkButton(
            self.scroll, text="➕ Добавить строку", fg_color="#e2e8f0",
            text_color=config.TEXT_MAIN, hover_color="#cbd5e1",
            font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=6, height=32, command=self.add_row,
        )

    def add_row(self):
        idx = len(self.rows)
        frame = ctk.CTkFrame(self.scroll, fg_color="#f8fafc", corner_radius=8,
                             border_color=config.BORDER_COLOR, border_width=1)
        frame.pack(fill="x", pady=4, padx=2)

        ctk.CTkLabel(frame, text=f"#{idx + 1}", font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=config.TEXT_MUTED, width=30).pack(side="left", padx=10)

        ctk.CTkLabel(frame, text="Логин:", font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=config.TEXT_MAIN).pack(side="left", padx=(5, 2))
        login_widget = AutocompleteEntry(
            frame,
            search_callback=self._search_users,
            format_callback=self._format_user,
            select_callback=self._login_of,
            width=220, height=34,
            placeholder="🔍 логин / имя / должность",
            tooltip_text=(
                "Начните вводить логин, имя, должность или внутренний номер — "
                "появятся совпадения из списка пользователей (вкладка «Пользователи»).\n\n"
                "Кликните на подсказку, чтобы подставить логин, "
                "или впишите значение вручную."
            ),
        )
        login_widget.pack(side="left", padx=(0, 15), pady=8)

        ctk.CTkLabel(frame, text="Номер:", font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=config.TEXT_MAIN).pack(side="left", padx=(5, 2))
        num_widget = AutocompleteEntry(
            frame,
            search_callback=self._search_nums,
            format_callback=self._format_num,
            select_callback=self._num_of,
            width=200, height=34,
            placeholder="🔍 номер",
            tooltip_text=(
                "Начните вводить номер — появятся совпадения из списка номеров ВАТС "
                "(вкладка «Номера ВАТС»).\n\n"
                "Кликните на подсказку, чтобы подставить номер, "
                "или впишите значение вручную."
            ),
        )
        num_widget.pack(side="left", padx=(0, 15), pady=8)

        row_data = {"frame": frame, "login_widget": login_widget, "num_widget": num_widget}

        if idx > 0:
            ctk.CTkButton(frame, text="🗑", width=34, height=34, fg_color="#fee2e2",
                          text_color="#dc2626", hover_color="#fca5a5", corner_radius=6,
                          command=lambda: self.remove_row(frame, row_data)).pack(side="left", padx=5)

        self.rows.append(row_data)

        self.btn_add.pack_forget()
        self.btn_add.pack(anchor="w", pady=10, padx=2)

    def remove_row(self, frame, row_data):
        if row_data in self.rows:
            self.rows.remove(row_data)
            frame.destroy()
            for i, r in enumerate(self.rows):
                for child in r["frame"].winfo_children():
                    if isinstance(child, ctk.CTkLabel) and child.cget("text").startswith("#"):
                        child.configure(text=f"#{i + 1}")

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

    @staticmethod
    def _telnum_of(item: dict) -> str:
        return str(item.get("telnum", item.get("phone", item.get("number", ""))))

    def _search_nums(self, query: str):
        nums = getattr(self.app.nums_tab, "raw_nums_data", None) or []
        if not nums:
            return []
        q = query.lower()
        out = []
        for n in nums:
            if not isinstance(n, dict):
                continue
            telnum = self._telnum_of(n)
            if q in telnum.lower():
                out.append(n)
                if len(out) >= 30:
                    break
        return out

    def _format_num(self, n: dict) -> str:
        return self._telnum_of(n) or "?"

    def _num_of(self, n: dict) -> str:
        return self._telnum_of(n)

    def execute(self):
        client = self.app.get_client()
        if not client:
            return

        tasks = []
        for idx, row in enumerate(self.rows):
            l = row["login_widget"].get().strip()
            n = row["num_widget"].get().strip()
            if not l or not n:
                self.app.show_warning("Валидация", f"Заполните поля в строке #{idx + 1}")
                return
            tasks.append({"login": l, "telnum": n})

        self._set_busy(True)

        def process():
            results = []
            for task in tasks:
                entry = {
                    "login": task["login"],
                    "telnum": task["telnum"],
                    "status": "ok",
                    "error": None,
                }
                try:
                    client.bind_telnum(task["login"], task["telnum"])
                except ExolveApiError as e:
                    entry["status"] = "error"
                    entry["error"] = str(e)
                except Exception as e:
                    entry["status"] = "error"
                    entry["error"] = f"Неожиданная ошибка: {e}"
                results.append(entry)
                # Частоту регулирует rate-limiter клиента (см. max_rps)

            ok = sum(1 for r in results if r["status"] == "ok")
            report = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "domain": client.domain,
                "total": len(results),
                "ok": ok,
                "failed": len(results) - ok,
                "items": results,
            }

            self.app.after(0, lambda r=report: self.app.set_debug_raw(
                json.dumps(r, ensure_ascii=False, indent=2)))
            self.app.after(0, lambda r=report: self._show_summary(r))

        def done():
            self._set_busy(False)

        self.app.run_async(process, on_done=done)

    def _set_busy(self, busy: bool):
        if busy:
            self.btn_run.configure(state="disabled", text="⏳ Идёт замена…")
            self.btn_add.configure(state="disabled")
        else:
            self.btn_run.configure(state="normal", text="🚀 Поменять номера")
            self.btn_add.configure(state="normal")

    def _show_summary(self, report: dict):
        total = report["total"]
        ok = report["ok"]
        failed = report["failed"]
        if failed == 0:
            self.app.show_info(
                "Готово",
                f"Успешно обработано: {ok} из {total}.\n\n"
                f"Подробности — во вкладке «RAW Ответ (Debug)»."
            )
        else:
            self.app.show_warning(
                "Завершено с ошибками",
                f"Успешно: {ok}, с ошибками: {failed} (всего {total}).\n\n"
                f"Подробности — во вкладке «RAW Ответ (Debug)»."
            )