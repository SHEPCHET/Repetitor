"""Запуск графического интерфейса."""

import sqlite3
import tkinter as tk
from tkinter import messagebox

from authenticator import Authenticator
from auth_view import AuthWindow
from database import DatabaseManager


class ApplicationController:
    """Связь форм с авторизацией."""

    def __init__(self, root):
        """Подключение базы и создание первого экрана."""
        self.root = root
        self.db = DatabaseManager()
        self.authenticator = Authenticator(self.db)

        self.view = AuthWindow(
            root, self.login, self.register
        )
        self.view.pack(fill="both", expand=True)

        root.protocol("WM_DELETE_WINDOW", self.close)

    def login(self, username, password):
        """Проверка данных из формы входа."""
        self.authenticator.logout()

        try:
            if username.strip() == "" or password == "":
                raise ValueError("Введите логин и пароль.")

            if not self.authenticator.login(username, password):
                raise ValueError("Неверный логин или пароль.")

        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror(
                "Вход", str(error), parent=self.root
            )

        else:
            messagebox.showinfo(
                "Вход", "Вход выполнен.", parent=self.root
            )

        finally:
            self.view.clear_password()

    def register(self, name, username, email, password, repeat):
        """Регистрация из графической формы."""
        self.authenticator.logout()

        try:
            if password != repeat:
                raise ValueError("Пароли не совпадают.")

            self.authenticator.register(
                name, username, email, password
            )

        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror(
                "Регистрация", str(error), parent=self.root
            )

        else:
            messagebox.showinfo(
                "Регистрация",
                "Учётная запись создана.",
                parent=self.root
            )
            self.view.show_login(username.strip())

    def close(self):
        """Закрытие приложения."""
        self.authenticator.logout()
        self.db.close()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Репетитор")
    root.geometry("1280x800")
    root.minsize(640, 760)
    root.configure(bg="white")

    controller = None

    try:
        controller = ApplicationController(root)
        root.mainloop()

    except (sqlite3.Error, OSError, ValueError) as error:
        messagebox.showerror(
            "Ошибка запуска", str(error), parent=root
        )
        root.destroy()

    finally:
        if controller is not None:
            controller.db.close()