"""Подключение к базе данных и резервные копии."""

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


class DatabaseManager:
    """Работа с подключением и копиями базы."""

    def __init__(self):
        """Начальные настройки."""
        project_folder = Path(__file__).resolve().parent
        self.db_path = project_folder / "repetitor.db"
        self.connection = None

    def connect(self):
        """Открытие базы."""
        if not self.db_path.exists():
            raise FileNotFoundError("База не найдена. Сначала запусти init_db.py.")

        if self.connection is None:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.execute("PRAGMA foreign_keys = ON;")

    def close(self):
        """Закрытие подключения."""
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def backup(self, path=None):
        """Создание резервной копии и получение пути к ней."""
        self.connect()

        if self.connection.in_transaction:
            raise ValueError("Сначала сохрани или отмени предыдущие изменения.")

        if path is None:
            moscow = timezone(timedelta(hours=3))
            stamp = datetime.now(moscow).strftime("%Y%m%d_%H%M%S_%f")

            backup_path = (
                self.db_path.parent / "backups" / ("repetitor_" + stamp + ".db")
            )

        else:
            backup_path = Path(path)

            if not backup_path.is_absolute():
                backup_path = self.db_path.parent / backup_path

        backup_path = backup_path.resolve()

        if backup_path == self.db_path.resolve():
            raise ValueError("Для копии нужен отдельный файл.")

        if backup_path.exists():
            raise FileExistsError("Файл с таким именем уже существует.")

        backup_path.parent.mkdir(parents=True, exist_ok=True)

        # Создание нового файла
        with open(backup_path, "xb"):
            pass

        backup_connection = None
        success = False

        try:
            backup_connection = sqlite3.connect(backup_path)
            self.connection.backup(backup_connection)
            success = True

        finally:
            if backup_connection is not None:
                backup_connection.close()

            if not success:
                backup_path.unlink(missing_ok=True)

        return backup_path


# Проверка резервной копии
if __name__ == "__main__":
    db = DatabaseManager()

    try:
        path = db.backup()
        print("Резервная копия создана:", path)

    except (sqlite3.Error, ValueError, OSError) as error:
        print("Ошибка:", error)

    finally:
        db.close()
