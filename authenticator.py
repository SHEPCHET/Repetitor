"""Регистрация и вход в учётную запись."""

import hashlib
import hmac
import secrets

from database import DatabaseManager


class Authenticator:
    """Работа с учётной записью репетитора."""

    def __init__(self, db):
        """Подключение к базе."""
        self.db = db
        self.db.connect()
        self.current_user_id = None

    def _begin(self):
        """Начало отдельной операции."""
        if self.db.connection.in_transaction:
            raise ValueError("Сначала сохрани или отмени предыдущие изменения.")

        self.db.connection.execute("BEGIN IMMEDIATE;")

    def _check_new_password(self, password):
        """Проверка нового пароля."""
        if len(password) < 8:
            raise ValueError("Пароль должен содержать не менее 8 символов.")

        has_letter = False
        has_digit = False
        for character in password:
            if character.isalpha():
                has_letter = True
            if character.isdigit():
                has_digit = True

        if not has_letter:
            raise ValueError("Добавь в пароль хотя бы одну букву.")
        if not has_digit:
            raise ValueError("Добавь в пароль хотя бы одну цифру.")

    def _hash_password(self, password, salt, iterations):
        """Получение хеша средствами Python."""
        return hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt), iterations
        ).hex()

    def _make_password(self, password):
        """Создание хеша и случайной соли."""
        salt = secrets.token_hex(16)
        iterations = 600000

        digest = self._hash_password(password, salt, iterations)
        stored_hash = "pbkdf2_sha256$" + str(iterations) + "$" + digest

        return stored_hash, salt

    def _verify_password(self, password, stored_hash, salt):
        """Проверка введённого пароля."""
        try:
            method, rounds_text, digest = stored_hash.split("$")

            if method != "pbkdf2_sha256":
                return False

            iterations = int(rounds_text)

            if iterations <= 0 or iterations > 2000000:
                return False

            candidate = self._hash_password(password, salt, iterations)

            return hmac.compare_digest(candidate, digest)

        except (ValueError, TypeError, OverflowError):
            return False

    def register(self, name, username, email, password):
        """Регистрация новой учётной записи."""
        name = name.strip()
        username = username.strip()
        email = email.strip()

        if name == "" or username == "" or email == "":
            raise ValueError("Заполни имя, логин и электронную почту.")

        parts = email.split("@")

        if len(parts) != 2 or parts[0] == "" or "." not in parts[1]:
            raise ValueError("Проверь адрес электронной почты.")

        if parts[1].startswith(".") or parts[1].endswith("."):
            raise ValueError("Проверь адрес электронной почты.")

        for character in email:
            if character.isspace():
                raise ValueError("В электронной почте не должно быть пробелов.")

        self._check_new_password(password)
        self._begin()

        with self.db.connection:
            existing = self.db.connection.execute(
                """
                SELECT user_id FROM users WHERE login = ?;
            """,
                [username],
            ).fetchone()

            if existing is not None:
                raise ValueError("Этот логин уже занят.")

            stored_hash, salt = self._make_password(password)

            self.db.connection.execute(
                """
                INSERT INTO users (
                    login, name, email, password_hash, password_salt
                )
                VALUES (?, ?, ?, ?, ?);
            """,
                [username, name, email, stored_hash, salt],
            )

        return True

    def login(self, username, password):
        """Вход по логину и паролю."""
        self.current_user_id = None
        username = username.strip()

        row = self.db.connection.execute(
            """
            SELECT user_id, password_hash, password_salt
            FROM users WHERE login = ?;
        """,
            [username],
        ).fetchone()

        if row is None:
            return False

        if not self._verify_password(password, row[1], row[2]):
            return False

        self.current_user_id = row[0]
        return True

    def logout(self):
        """Выход из учётной записи."""
        self.current_user_id = None

    def get_current_user(self):
        """Сведения об учётной записи для настроек."""
        if self.current_user_id is None:
            return None

        row = self.db.connection.execute(
            """
            SELECT user_id, name, login, email
            FROM users WHERE user_id = ?;
        """,
            [self.current_user_id],
        ).fetchone()

        if row is None:
            self.logout()
            return None

        return {"user_id": row[0], "name": row[1], "login": row[2], "email": row[3]}

    def change_password(self, current_password, new_password):
        """Смена пароля после проверки текущего."""
        if self.current_user_id is None:
            raise ValueError("Сначала войди в учётную запись.")

        self._check_new_password(new_password)
        self._begin()

        with self.db.connection:
            row = self.db.connection.execute(
                """
                SELECT password_hash, password_salt
                FROM users WHERE user_id = ?;
            """,
                [self.current_user_id],
            ).fetchone()

            if row is None:
                self.logout()
                raise ValueError("Учётная запись не найдена.")

            if not self._verify_password(current_password, row[0], row[1]):
                return False

            stored_hash, salt = self._make_password(new_password)

            self.db.connection.execute(
                """
                UPDATE users
                SET password_hash = ?, password_salt = ?
                WHERE user_id = ?;
            """,
                [stored_hash, salt, self.current_user_id],
            )

        return True


# Проверка подключения
if __name__ == "__main__":
    db = DatabaseManager()

    try:
        authenticator = Authenticator(db)
        print("Модуль авторизации готов.")
    finally:
        db.close()
