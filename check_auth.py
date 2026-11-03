"""Проверка регистрации и входа."""

import sqlite3
from getpass import getpass

from authenticator import Authenticator
from database import DatabaseManager


db = DatabaseManager()

try:
    authenticator = Authenticator(db)

    while True:
        print("\n1 — Регистрация")
        print("2 — Вход")
        print("3 — Сведения об учётной записи")
        print("4 — Смена пароля")
        print("5 — Выход из учётной записи")
        print("0 — Завершить проверку")

        action = input("Выбери действие: ").strip()

        if action == "0":
            break

        try:
            if action == "1":
                name = input("Имя: ")
                username = input("Логин: ")
                email = input("Электронная почта: ")
                password = getpass("Пароль: ")
                repeat = getpass("Повтори пароль: ")

                if password != repeat:
                    raise ValueError("Пароли не совпадают.")

                authenticator.register(
                    name, username, email, password
                )
                print("Учётная запись создана. Теперь можно войти.")

            elif action == "2":
                username = input("Логин: ")
                password = getpass("Пароль: ")

                if authenticator.login(username, password):
                    print("Вход выполнен.")
                else:
                    print("Неверный логин или пароль.")

            elif action == "3":
                user = authenticator.get_current_user()

                if user is None:
                    print("Сначала войди в учётную запись.")
                else:
                    print("ID:", user["user_id"])
                    print("Имя:", user["name"])
                    print("Логин:", user["login"])
                    print("Электронная почта:", user["email"])

            elif action == "4":
                if authenticator.current_user_id is None:
                    raise ValueError(
                        "Сначала войди в учётную запись."
                    )

                current_password = getpass("Текущий пароль: ")
                new_password = getpass("Новый пароль: ")
                repeat = getpass("Повтори новый пароль: ")

                if new_password != repeat:
                    raise ValueError("Новые пароли не совпадают.")

                changed = authenticator.change_password(
                    current_password, new_password
                )

                if changed:
                    print("Пароль изменён.")
                else:
                    print("Текущий пароль указан неверно.")

            elif action == "5":
                authenticator.logout()
                print("Выход из учётной записи выполнен.")

            else:
                print("Выбери номер из меню.")

        except (sqlite3.Error, ValueError) as error:
            print("Ошибка:", error)

except (EOFError, KeyboardInterrupt):
    print("\nПроверка завершена.")

finally:
    db.close()