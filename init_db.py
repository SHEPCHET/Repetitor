"""Создание базы данных."""

import sqlite3
from pathlib import Path

# Папка программы и путь к базе
project_folder = Path(__file__).resolve().parent
db_path = project_folder / "repetitor.db"

connection = sqlite3.connect(db_path)

# Проверка связей между таблицами
connection.execute("PRAGMA foreign_keys = ON;")

try:
    connection.executescript("""
        BEGIN;

        -- Предметы
        CREATE TABLE IF NOT EXISTS subjects (
            subject_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
        );

        -- Ученики
        CREATE TABLE IF NOT EXISTS students (
            student_id INTEGER PRIMARY KEY,
            full_name TEXT NOT NULL,
            phone TEXT,
            messenger_type TEXT,
            messenger_contact TEXT,
            is_archived INTEGER NOT NULL DEFAULT 0
                CHECK (is_archived IN (0, 1))
        );

        -- Родители
        CREATE TABLE IF NOT EXISTS parents (
            parent_id INTEGER PRIMARY KEY,
            full_name TEXT NOT NULL,
            phone TEXT,
            messenger_type TEXT,
            messenger_contact TEXT
        );

        -- Пользователи
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            login TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            password_salt TEXT NOT NULL
        );

        -- Ученики и родители
        CREATE TABLE IF NOT EXISTS student_parents (
            student_id INTEGER NOT NULL,
            parent_id INTEGER NOT NULL,
            is_primary INTEGER NOT NULL DEFAULT 0
                CHECK (is_primary IN (0, 1)),
            PRIMARY KEY (student_id, parent_id),
            FOREIGN KEY (student_id)
                REFERENCES students (student_id) ON DELETE RESTRICT,
            FOREIGN KEY (parent_id)
                REFERENCES parents (parent_id) ON DELETE RESTRICT
        );

        -- Один основной родитель на ученика
        CREATE UNIQUE INDEX IF NOT EXISTS idx_one_primary_parent
            ON student_parents (student_id)
            WHERE is_primary = 1;

        -- Направления обучения
        CREATE TABLE IF NOT EXISTS enrollments (
            enrollment_id INTEGER PRIMARY KEY,
            student_id INTEGER NOT NULL,
            subject_id INTEGER NOT NULL,
            preparation_goal TEXT NOT NULL,
            price_60_kopecks INTEGER NOT NULL
                CHECK (price_60_kopecks >= 0),
            FOREIGN KEY (student_id)
                REFERENCES students (student_id) ON DELETE RESTRICT,
            FOREIGN KEY (subject_id)
                REFERENCES subjects (subject_id) ON DELETE RESTRICT
        );

        -- Занятия
        CREATE TABLE IF NOT EXISTS lessons (
            lesson_id INTEGER PRIMARY KEY,
            enrollment_id INTEGER NOT NULL,
            starts_at TEXT NOT NULL,
            ends_at TEXT NOT NULL,
            price_kopecks INTEGER NOT NULL
                CHECK (price_kopecks >= 0),
            status TEXT NOT NULL DEFAULT 'Запланировано'
                CHECK (status IN (
                    'Запланировано', 'Проведено', 'Отменено'
                )),
            CHECK (ends_at > starts_at),
            FOREIGN KEY (enrollment_id)
                REFERENCES enrollments (enrollment_id) ON DELETE RESTRICT
        );

        -- Темы занятий
        CREATE TABLE IF NOT EXISTS lesson_topics (
            lesson_topic_id INTEGER PRIMARY KEY,
            lesson_id INTEGER NOT NULL,
            topic_name TEXT NOT NULL,
            FOREIGN KEY (lesson_id)
                REFERENCES lessons (lesson_id) ON DELETE RESTRICT
        );

        -- Оплаты
        CREATE TABLE IF NOT EXISTS payments (
            payment_id INTEGER PRIMARY KEY,
            student_id INTEGER NOT NULL,
            lesson_id INTEGER NOT NULL UNIQUE,
            paid_at TEXT NOT NULL,
            amount_kopecks INTEGER NOT NULL
                CHECK (amount_kopecks > 0),
            FOREIGN KEY (student_id)
                REFERENCES students (student_id) ON DELETE RESTRICT,
            FOREIGN KEY (lesson_id)
                REFERENCES lessons (lesson_id) ON DELETE RESTRICT
        );

        -- Индексы для поиска
        CREATE INDEX IF NOT EXISTS idx_students_name
            ON students (full_name);

        CREATE INDEX IF NOT EXISTS idx_enrollments_student
            ON enrollments (student_id);

        CREATE INDEX IF NOT EXISTS idx_enrollments_subject
            ON enrollments (subject_id);

        CREATE INDEX IF NOT EXISTS idx_lessons_enrollment_date
            ON lessons (enrollment_id, starts_at);

        CREATE INDEX IF NOT EXISTS idx_lessons_date
            ON lessons (starts_at);

        CREATE INDEX IF NOT EXISTS idx_payments_student_date
            ON payments (student_id, paid_at);

        CREATE INDEX IF NOT EXISTS idx_topics_lesson
            ON lesson_topics (lesson_id);

        CREATE INDEX IF NOT EXISTS idx_student_parents_parent
            ON student_parents (parent_id);

        COMMIT;
    """)

    # Список созданных таблиц
    tables = connection.execute("""
        SELECT name FROM sqlite_master
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name;
    """).fetchall()

except sqlite3.Error:
    connection.rollback()
    raise

finally:
    connection.close()

print("База данных готова:", db_path)
print("Количество таблиц:", len(tables))

for table in tables:
    print(table[0])