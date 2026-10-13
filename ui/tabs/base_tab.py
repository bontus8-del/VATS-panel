"""Общая логика вкладки: выделение строки, копирование, debounce поиска, сброс скролла."""
import customtkinter as ctk

import config


class BaseTab(ctk.CTkFrame):
    """Базовая вкладка.

    SEARCH_DEBOUNCE_MS — задержка между последним нажатием в поле поиска
    и фактическим пересчётом/отрисовкой.
    """
    SEARCH_DEBOUNCE_MS = 350

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.selected_row = None
        self.selected_data = None
        self._search_after_id = None

    # --- выделение / копирование ---
    def select_row(self, row_frame, data):
        if self.selected_row and self.selected_row.winfo_exists():
            self.selected_row.configure(fg_color=config.ROW_BG_NORMAL, border_width=0)
        self.selected_row = row_frame
        self.selected_data = data
        row_frame.configure(
            fg_color=config.ROW_BG_SELECTED,
            border_color=config.ROW_BORDER_SELECTED,
            border_width=1,
        )

    def copy_selected(self) -> bool:
        if self.selected_data:
            self.app.copy_to_clipboard(self.selected_data)
            return True
        return False

    # --- поиск с debounce ---
    def _schedule_search(self, callback):
        """Отложить вызов callback; новый вызов сбрасывает таймер."""
        if self._search_after_id is not None:
            try:
                self.after_cancel(self._search_after_id)
            except Exception:
                pass
        self._search_after_id = self.after(self.SEARCH_DEBOUNCE_MS, callback)

    # --- скролл ---
    @staticmethod
    def _reset_scroll(scroll_widget):
        """Сбросить CTkScrollableFrame в начало.

        Внутри CTkScrollableFrame спрятан Canvas (_parent_canvas); после
        очистки детей scrollregion сжимается, а canvas остаётся прокрученным —
        новые строки не видны. yview_moveto(0) возвращает вид наверх.
        """
        try:
            scroll_widget._parent_canvas.yview_moveto(0)
        except Exception:
            pass