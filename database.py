"""Подключение к базе данных."""

import sqlite3
from pathlib import Path


class DatabaseManager:
    """Работа с подключением."""

    def __init__(self):
        """Начальные настройки."""
        project_folder = Path(__file__).resolve().parent
        self.db_path = project_folder / "repetitor.db"
        self.connection = None

    def connect(self):
        """Открытие базы."""
        if not self.db_path.exists():
            raise FileNotFoundError(
                "База не найдена. Сначала запусти init_db.py."
            )

        if self.connection is None:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.execute("PRAGMA foreign_keys = ON;")

    def close(self):
        """Закрытие подключения."""
        if self.connection is not None:
            self.connection.close()
            self.connection = None


# Проверка подключения
if __name__ == "__main__":
    db = DatabaseManager()

    try:
        db.connect()
        print("Подключение открыто:", db.db_path)
    finally:
        db.close()