"""Глобальные Ctrl+C/V/X/A с учётом раскладки.

Почему так:
- Нативные class-bindings Tk для Ctrl+C/V/X/A срабатывают только на латинской
  раскладке (keysym = 'v'), на русской — нет (keysym = 'м').
- Если ставить свой bind_all, он срабатывает ПОСЛЕ class bindings → на латинице
  получаем двойное действие.

Решение:
1) Снимаем нативные биндинги Ctrl+C/V/X/A у текстовых классов.
2) Ставим свой bind_class на <Control-KeyPress> — матчим по event.keycode
   (он одинаков независимо от раскладки: C=67, V=86, X=88, A=65).
3) bind_all — отдельно, для Ctrl+C вне полей ввода (копирование строки).
"""
import tkinter as tk
import customtkinter as ctk


_KEYCODE_TO_VIRTUAL = {
    67: "<<Copy>>",       # C
    86: "<<Paste>>",      # V
    88: "<<Cut>>",        # X
    65: "<<SelectAll>>",  # A
}

_KEYSYM_TO_VIRTUAL = {
    "c": "<<Copy>>",  "с": "<<Copy>>",
    "v": "<<Paste>>", "м": "<<Paste>>",
    "x": "<<Cut>>",   "ч": "<<Cut>>",
    "a": "<<SelectAll>>", "ф": "<<SelectAll>>",
}

_TEXT_CLASSES = ("Entry", "Text", "TEntry", "TCombobox")


def install(app):
    _strip_native_bindings(app)
    for cls in _TEXT_CLASSES:
        app.bind_class(cls, "<Control-KeyPress>", _on_ctrl_key)
    app.bind_all("<Key>", lambda e: _on_global(app, e))


def _strip_native_bindings(app):
    """Убираем штатные Ctrl+C/V/X/A у текстовых классов — иначе дубль с нашим."""
    seqs = (
        "<Control-c>", "<Control-v>", "<Control-x>", "<Control-a>",
        "<Control-C>", "<Control-V>", "<Control-X>", "<Control-A>",
        "<Control-Key-c>", "<Control-Key-v>",
        "<Control-Key-x>", "<Control-Key-a>",
        "<Control-Key-C>", "<Control-Key-V>",
        "<Control-Key-X>", "<Control-Key-A>",
    )
    for cls in _TEXT_CLASSES:
        for seq in seqs:
            try:
                app.bind_class(cls, seq, "")
            except tk.TclError:
                pass


def _on_ctrl_key(event):
    action = _KEYCODE_TO_VIRTUAL.get(event.keycode)
    if action is None:
        action = _KEYSYM_TO_VIRTUAL.get((event.keysym or "").lower())
    if action is None:
        # Ctrl+что-то другое — не мешаем штатным биндингам (Ctrl+Left и т.п.)
        return None
    event.widget.event_generate(action)
    return "break"


def _on_global(app, event):
    """Ctrl+C вне полей ввода — копируем выделенную строку активной вкладки."""
    if (event.state & 0x4) == 0:
        return

    is_c = event.keycode == 67 or (event.keysym or "").lower() in ("c", "с")
    if not is_c:
        return

    widget = event.widget
    # Если фокус в текстовом поле — это уже обработал class-хендлер выше
    if isinstance(widget, (tk.Entry, tk.Text, ctk.CTkEntry, ctk.CTkTextbox)):
        return

    tab = app.tabview.get()
    if "пользователей" in tab and app.users_tab.copy_selected():
        return "break"
    if "Номера" in tab and app.nums_tab.copy_selected():
        return "break"