import os
import threading
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

import config
from api import ExolveClient, ExolveApiError
from .header import Header
from .hotkeys import install as install_hotkeys
from .widgets.toast import ToastManager
from .widgets.status_bar import StatusBar
from .tabs.users_tab import UsersTab
from .tabs.nums_tab import NumsTab
from .tabs.replace_tab import ReplaceTab
from .tabs.debug_tab import DebugTab

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class VatsApp(ctk.CTk):
    SAVE_DEBOUNCE_MS = 500

    def __init__(self):
        super().__init__()

        self.title("ВАТС Панель — MTC Exolve")
        self.geometry("1120x780")
        self.minsize(980, 680)
        self.configure(fg_color=config.BG_MAIN)

        self._icon_photo = None
        self._apply_window_icon()

        self._suppress_save = False
        self._save_after_id = None

        self.domain_var = tk.StringVar()
        self.key_var = tk.StringVar()
        self.rps_var = tk.StringVar(value=str(config.DEFAULT_RPS))

        self._load_persisted_credentials()

        self._build_header()
        self._build_tabs()
        self._build_status_bar()

        self.toasts = ToastManager(self, top_offset=90)

        self.domain_var.trace_add("write", self._on_field_change)
        self.key_var.trace_add("write", self._on_field_change)
        self.rps_var.trace_add("write", self._on_field_change)

        install_hotkeys(self)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        if not config.keyring_available():
            self.after(400, lambda: self.show_warning(
                "keyring недоступен",
                "Библиотека keyring не установлена или не работает.\n"
                "Ключ не будет сохраняться между запусками."
            ))

        self.users_tab.load()

    # --- иконка окна ---
    def _apply_window_icon(self):
        ico = config.asset_path("icon.ico")
        if os.path.exists(ico):
            try:
                self.iconbitmap(ico)
                return
            except Exception:
                pass

        if PIL_AVAILABLE:
            png = config.asset_path("logo.png")
            if os.path.exists(png):
                try:
                    img = Image.open(png)
                    self._icon_photo = ImageTk.PhotoImage(img)
                    self.iconphoto(True, self._icon_photo)
                    return
                except Exception:
                    pass

    # --- построение ---
    def _build_header(self):
        self.header = Header(self, self.domain_var, self.key_var, self.rps_var)
        self.header.pack(fill="x", side="top")

    def _build_tabs(self):
        self.tabview = ctk.CTkTabview(
            self,
            corner_radius=12,
            fg_color=config.BG_MAIN,
            segmented_button_fg_color="#1e293b",
            segmented_button_selected_color=config.RED_ACCENT,
            segmented_button_selected_hover_color=config.RED_HOVER,
            segmented_button_unselected_color="#334155",
            segmented_button_unselected_hover_color="#475569",
        )
        self.tabview.pack(fill="both", expand=True, padx=15, pady=(5, 5))

        self.tabview._segmented_button.configure(
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#ffffff",
            height=48,
            corner_radius=8,
        )

        t_users = self.tabview.add(" 👤 Список пользователей ")
        t_nums = self.tabview.add(" 📞 Номера ВАТС ")
        t_replace = self.tabview.add(" 🔄 Замена номеров ")
        t_debug = self.tabview.add(" </> RAW Ответ (Debug) ")

        self.users_tab = UsersTab(t_users, self)
        self.users_tab.pack(fill="both", expand=True)

        self.nums_tab = NumsTab(t_nums, self)
        self.nums_tab.pack(fill="both", expand=True)

        self.replace_tab = ReplaceTab(t_replace, self)
        self.replace_tab.pack(fill="both", expand=True)

        self.debug_tab = DebugTab(t_debug, self)
        self.debug_tab.pack(fill="both", expand=True)

    def _build_status_bar(self):
        self.status_bar = StatusBar(self, height=28)
        self.status_bar.pack(fill="x", side="bottom")

    # --- персистентность ---
    def _load_persisted_credentials(self):
        self._suppress_save = True
        try:
            domain = config.load_domain()
            self.domain_var.set(domain)
            if domain:
                key = config.load_key(domain)
                if key:
                    self.key_var.set(key)
            self.rps_var.set(str(config.load_rps()))
        finally:
            self._suppress_save = False

    def _on_field_change(self, *args):
        if self._suppress_save:
            return
        self._schedule_save()

    def _schedule_save(self):
        if self._save_after_id is not None:
            try:
                self.after_cancel(self._save_after_id)
            except Exception:
                pass
        self._save_after_id = self.after(self.SAVE_DEBOUNCE_MS, self._do_save)

    def _do_save(self):
        self._save_after_id = None
        domain = self.domain_var.get().strip()
        key = self.key_var.get().strip()
        if domain:
            config.save_domain(domain)
        if domain and key:
            config.save_key(domain, key)
        # RPS
        try:
            rps = int(self.rps_var.get().strip())
        except ValueError:
            rps = config.DEFAULT_RPS
        config.save_rps(rps)

    def _on_close(self):
        if self._save_after_id is not None:
            try:
                self.after_cancel(self._save_after_id)
            except Exception:
                pass
            self._save_after_id = None
        self._do_save()
        self.destroy()

    # --- API ---
    def get_client(self):
        domain = self.domain_var.get().strip()
        key = self.key_var.get().strip()
        if not domain or not key:
            self.show_warning("Внимание", "Укажите Домен и X-API-KEY в шапке.")
            return None
        try:
            rps = int(self.rps_var.get().strip())
        except ValueError:
            rps = config.DEFAULT_RPS
        rps = max(config.MIN_RPS, min(rps, config.MAX_RPS))
        try:
            return ExolveClient(domain, key, max_rps=float(rps))
        except ValueError as e:
            self.show_error("Неверные данные", str(e))
            return None

    def run_async(self, fn, on_done=None):
        def wrapper():
            try:
                fn()
            finally:
                if on_done is not None:
                    self.after(0, on_done)
        threading.Thread(target=wrapper, daemon=True).start()

    def handle_api_error(self, e):
        status = getattr(e, "status_code", None)
        if status == 401:
            self.header.flash_key_error()
        text = str(e) if e is not None else "Неизвестная ошибка"

        # Тело ответа сервера (если есть) — в DebugTab для разбора
        body = getattr(e, "body", None)
        if body:
            try:
                self.debug_tab.set_raw(f"=== Ошибка API ===\n{text}\n\n=== Ответ сервера ===\n{body}")
            except Exception:
                pass

        self.show_error("Ошибка API", text)
        self.status_bar.set_status("Ошибка запроса", "error")

    # --- сервисные ---
    def set_debug_raw(self, text: str):
        self.after(0, lambda: self.debug_tab.set_raw(text))

    def copy_to_clipboard(self, text: str):
        self.clipboard_clear()
        self.clipboard_append(text)

    def set_status(self, text: str, kind: str = "info"):
        self.status_bar.set_status(text, kind)

    # --- уведомления ---
    def show_info(self, title, text):
        self.toasts.show(text, kind="success")

    def show_warning(self, title, text):
        self.toasts.show(text, kind="warning")

    def show_error(self, title, text):
        self.toasts.show(text, kind="error")

    # --- модальные диалоги ---
    def show_dialog_info(self, title, text):
        messagebox.showinfo(title, text)

    def show_dialog_warning(self, title, text):
        messagebox.showwarning(title, text)

    def show_dialog_error(self, title, text):
        messagebox.showerror(title, text)