"""Проверка записи и чтения."""

import sqlite3
from pathlib import Path

project_folder = Path(__file__).resolve().parent
db_path = project_folder / "repetitor.db"

connection = sqlite3.connect(db_path)
connection.execute("PRAGMA foreign_keys = ON;")

subject_name = "Математика"

try:
    # Добавление предмета
    connection.execute(
        """
        INSERT INTO subjects (name)
        VALUES (?)
        ON CONFLICT(name) DO NOTHING;
    """,
        [subject_name],
    )

    connection.commit()

    # Получение списка предметов
    subjects = connection.execute("""
        SELECT subject_id, name
        FROM subjects
        ORDER BY subject_id;
    """).fetchall()

except sqlite3.Error:
    connection.rollback()
    raise

finally:
    connection.close()

# Вывод списка
for subject in subjects:
    print("ID:", subject[0], "Предмет:", subject[1])
