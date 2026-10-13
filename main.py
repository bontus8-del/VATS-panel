import sys

try:
    import customtkinter as ctk
except ImportError:
    print("Ошибка: Не найдена библиотека customtkinter.")
    print("Установите её командой: pip install customtkinter")
    sys.exit(1)

from ui.app import VatsApp


def main():
    ctk.set_appearance_mode("Light")
    app = VatsApp()
    app.mainloop()


if __name__ == "__main__":
    main()