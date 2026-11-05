"""Сохранённый вход на этом компьютере."""

import hashlib
import hmac
import json
import os
import secrets
import tempfile
from pathlib import Path


class RememberedLogin:
    """Сохранение и проверка входа на этом компьютере."""

    def __init__(self, db):
        """Подготовка данных и элементов объекта."""
        self.db = db
        self.path = Path(db.db_path).parent / ".login_session.json"
        columns = self.db.connection.execute("PRAGMA table_info(users);").fetchall()
        if "remember_token_hash" not in [column[1] for column in columns]:
            self._begin()
            with self.db.connection:
                self.db.connection.execute(
                    "ALTER TABLE users ADD COLUMN remember_token_hash TEXT;"
                )

    def _begin(self):
        """Начало операции без сохранения чужих изменений."""
        if self.db.connection.in_transaction:
            raise ValueError("Сначала сохрани или отмени предыдущие изменения.")
        self.db.connection.execute("BEGIN IMMEDIATE;")

    def _digest(self, token, password_hash):
        """Получение проверочного хеша ключа сохранённого входа."""
        return hashlib.sha256((token + ":" + password_hash).encode("utf-8")).hexdigest()

    def restore(self):
        """Проверка сохранённого входа."""
        try:
            with open(self.path, "r", encoding="utf-8") as file:
                data = json.loads(file.read(4096))
        except (OSError, ValueError, UnicodeError):
            return None
        if not isinstance(data, dict):
            return None
        user_id, token = data.get("user_id"), data.get("token")
        if type(user_id) is not int or user_id <= 0:
            return None
        if not isinstance(token, str) or len(token) != 64:
            return None
        row = self.db.connection.execute(
            "SELECT password_hash, remember_token_hash FROM users WHERE user_id = ?;",
            [user_id],
        ).fetchone()
        if row is None or not isinstance(row[1], str):
            return None
        if not hmac.compare_digest(self._digest(token, row[0]), row[1]):
            return None
        return user_id

    def remember(self, user_id):
        """Новый ключ вместо сохранения пароля."""
        token = secrets.token_hex(32)
        self._begin()
        temporary_path = None
        try:
            with self.db.connection:
                row = self.db.connection.execute(
                    "SELECT password_hash FROM users WHERE user_id = ?;", [user_id]
                ).fetchone()
                if row is None:
                    raise ValueError("Учётная запись не найдена.")
                self.db.connection.execute(
                    "UPDATE users SET remember_token_hash = ? WHERE user_id = ?;",
                    [self._digest(token, row[0]), user_id],
                )
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=self.path.parent,
                    prefix=".login_session-",
                    suffix=".tmp",
                    delete=False,
                ) as file:
                    temporary_path = Path(file.name)
                    json.dump({"user_id": user_id, "token": token}, file)
                os.replace(temporary_path, self.path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def forget(self, user_id):
        """Выход по кнопке отменяет сохранённый вход."""
        self._begin()
        with self.db.connection:
            self.db.connection.execute(
                "UPDATE users SET remember_token_hash = NULL WHERE user_id = ?;",
                [user_id],
            )
        self.path.unlink(missing_ok=True)
