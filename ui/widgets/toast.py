"""Всплывающие уведомления в правом-верхнем углу окна.

Поведение:
- info / success — гаснут сами через duration_ms (по умолчанию 3–3.5 с);
- warning / error — НЕ гаснут автоматически, закрываются только вручную;
- закрыть можно крестиком или кликом по самому тосту.
"""
import customtkinter as ctk


_COLORS = {
    # kind: (background, text, accent)
    "info":    ("#dbeafe", "#1e3a8a", "#3b82f6"),
    "success": ("#dcfce7", "#14532d", "#22c55e"),
    "warning": ("#fef3c7", "#78350f", "#f59e0b"),
    "error":   ("#fee2e2", "#7f1d1d", "#ef4444"),
}


class _Toast(ctk.CTkFrame):
    WRAP = 320  # перенос текста в пикселях

    def __init__(self, master, text, kind, on_close):
        bg, fg, accent = _COLORS.get(kind, _COLORS["info"])
        super().__init__(
            master, fg_color=bg, corner_radius=8,
            border_width=2, border_color=accent,
        )
        self._on_close = on_close

        # Кнопка закрытия (сверху справа)
        self._close_btn = ctk.CTkButton(
            self, text="✕", width=22, height=22,
            fg_color="transparent", hover_color=accent,
            text_color=fg, font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=4, command=self._clicked,
        )
        self._close_btn.pack(side="right", padx=(0, 6), pady=6, anchor="n")

        # Текст
        self._label = ctk.CTkLabel(
            self, text=text, text_color=fg,
            font=ctk.CTkFont(size=12),
            wraplength=self.WRAP,
            justify="left", anchor="w",
        )
        self._label.pack(side="left", padx=(12, 4), pady=10, fill="x", expand=True)

        # Клик по фону/тексту — тоже закрыть
        for w in (self, self._label):
            w.bind("<Button-1>", lambda e: self._clicked())

    def _clicked(self):
        self._on_close(self)


class ToastManager:
    """Стек тостов, прижатый к правому-верхнему углу master."""

    def __init__(self, master, top_offset: int = 90):
        self.master = master
        self.toasts = []
        # Отступ сверху (высота хедера + зазор) и справа
        self.top_offset = top_offset
        self.right_offset = 12
        self.gap = 8

    def show(self, text: str, kind: str = "info", duration_ms: int | None = None):
        """Показать тост. Для warning/error авто-закрытие не применяется."""
        toast = _Toast(self.master, text, kind, on_close=self._close)
        self.toasts.append(toast)
        self._reposition()
        toast.lift()

        auto_close = kind in ("info", "success")
        if auto_close:
            if duration_ms is None:
                duration_ms = 3000 if kind == "success" else 3500
            self.master.after(duration_ms, lambda t=toast: self._close(t))

        return toast

    def _close(self, toast):
        if toast in self.toasts:
            self.toasts.remove(toast)
        try:
            if toast.winfo_exists():
                toast.destroy()
        except Exception:
            pass
        self._reposition()

    def _reposition(self):
        y = self.top_offset
        for t in self.toasts:
            try:
                if not t.winfo_exists():
                    continue
            except Exception:
                continue
            t.update_idletasks()
            t.place(relx=1.0, rely=0.0, x=-self.right_offset, y=y, anchor="ne")
            y += t.winfo_reqheight() + self.gap