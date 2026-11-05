"""Проверка скорости на отдельной базе со 100 учениками и 10 000 занятиями."""

import argparse
import ast
import json
import platform
import sqlite3
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from time import perf_counter
from types import SimpleNamespace

from database import DatabaseManager
from lesson_repository import LessonRepository
from lesson_service import LessonService
from main import ApplicationController
from report_generator import ReportGenerator
from student_repository import StudentRepository
from student_service import StudentService


def create_data(db):
    """Создание только вымышленных данных во временной папке."""
    source = Path(__file__).with_name("init_db.py").read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    schema = next(
        ast.literal_eval(node.args[0])
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "executescript"
    )
    connection = sqlite3.connect(db.db_path)
    try:
        connection.executescript(schema)
        with connection:
            connection.executemany(
                "INSERT INTO subjects(subject_id, name) VALUES (?, ?)",
                [(number, "Тестовый предмет " + str(number)) for number in range(1, 6)],
            )
            for number in range(1, 101):
                connection.execute(
                    "INSERT INTO students(student_id,full_name) VALUES (?,?)",
                    [number, "Тестовый ученик " + str(number).zfill(3)],
                )
                connection.execute(
                    "INSERT INTO parents(parent_id,full_name) VALUES (?,?)",
                    [number, "Тестовый родитель " + str(number)],
                )
                connection.execute(
                    "INSERT INTO student_parents VALUES (?,?,1)", [number, number]
                )
                connection.execute(
                    "INSERT INTO enrollments VALUES (?,?,?,?,?)",
                    [number, number, number % 5 + 1, "ЕГЭ", 140000],
                )
            for number in range(1, 10001):
                day = (number - 1) // 8
                hour = 8 + (number - 1) % 8
                start = datetime(2022, 1, 1, hour) + timedelta(days=day)
                end = start + timedelta(hours=1)
                student_id = (number - 1) % 100 + 1
                status = "Отменено" if number % 10 == 0 else "Проведено"
                connection.execute(
                    "INSERT INTO lessons VALUES (?,?,?,?,?,?)",
                    [
                        number,
                        student_id,
                        start.strftime("%Y-%m-%d %H:%M:%S"),
                        end.strftime("%Y-%m-%d %H:%M:%S"),
                        140000,
                        status,
                    ],
                )
                connection.executemany(
                    "INSERT INTO lesson_topics(lesson_id,topic_name) VALUES (?,?)",
                    [(number, "Тема 1"), (number, "Тема 2")],
                )
                if number % 3 == 0:
                    connection.execute(
                        "INSERT INTO payments"
                        "(student_id,lesson_id,paid_at,amount_kopecks) "
                        "VALUES (?,?,?,?)",
                        [
                            student_id,
                            number,
                            start.strftime("%Y-%m-%d %H:%M:%S"),
                            140000,
                        ],
                    )
    finally:
        connection.close()
    db.connect()
    assert db.connection.execute("PRAGMA foreign_key_check").fetchall() == []


def measure(name, action, check, limit, repeats=5):
    """Пять замеров вместе с проверкой корректности результата."""
    times = []
    for attempt in range(repeats):
        started = perf_counter()
        result = action(attempt)
        elapsed = perf_counter() - started
        check(result)
        times.append(elapsed)
    result = {
        "operation": name,
        "repeats": repeats,
        "median_seconds": round(median(times), 6),
        "max_seconds": round(max(times), 6),
        "limit_seconds": limit,
        "within_limit": max(times) <= limit,
    }
    print(name, "— максимум", round(max(times), 4), "с", flush=True)
    return result


def expect(condition):
    """Ошибка проверки вместо измерения неправильного результата."""
    if not condition:
        raise AssertionError("Результат операции не соответствует тестовым данным.")


def run():
    """Измерения правил и обработчиков без отрисовки настоящих окон."""
    results = []
    with tempfile.TemporaryDirectory() as folder:
        db = DatabaseManager()
        db.db_path = Path(folder) / "benchmark.db"
        create_data(db)
        try:
            counts = {
                table: db.connection.execute(
                    "SELECT COUNT(*) FROM " + table
                ).fetchone()[0]
                for table in ("students", "lessons", "lesson_topics", "payments")
            }
            expect(counts["students"] == 100 and counts["lessons"] == 10000)
            app = ApplicationController.__new__(ApplicationController)
            app.db, app.root = db, None
            app.authenticator = SimpleNamespace(current_user_id=1)
            results.append(
                measure(
                    "Поиск и загрузка 100 карточек",
                    lambda attempt: app.load_students("Тестовый ученик"),
                    lambda rows: expect(len(rows) == 100),
                    2,
                )
            )
            results.append(
                measure(
                    "Поиск ученика по ID",
                    lambda attempt: StudentRepository(db).search("100"),
                    lambda rows: expect(len(rows) == 1 and rows[0].student_id == 100),
                    2,
                )
            )
            results.append(
                measure(
                    "Загрузка недели расписания",
                    lambda attempt: app.load_schedule(
                        date(2024, 3, 4), date(2024, 3, 11)
                    ),
                    lambda rows: expect(bool(rows)),
                    2,
                )
            )
            results.append(
                measure(
                    "Загрузка журнала проведённых занятий",
                    lambda attempt: app.load_journal(),
                    lambda rows: expect(len(rows) == 9000),
                    2,
                )
            )
            results.append(
                measure(
                    "Поиск в журнале по ID",
                    lambda attempt: app.load_journal("1"),
                    lambda rows: expect(len(rows) == 100),
                    2,
                )
            )
            results.append(
                measure(
                    "Загрузка истории оплат",
                    lambda attempt: app.load_payments(),
                    lambda rows: expect(len(rows) == 3333),
                    2,
                )
            )
            results.append(
                measure(
                    "Расчёт балансов 100 учеников",
                    lambda attempt: app.load_payments(balance_mode=True),
                    lambda rows: expect(len(rows) == 100),
                    2,
                )
            )
            results.append(
                measure(
                    "Отчёт за месяц через обработчик",
                    lambda attempt: app.generate_report(
                        "1", "01.03.2024", "31.03.2024"
                    ),
                    lambda report: expect(
                        bool(report and report["text"] and report["data"]["lessons"])
                    ),
                    5,
                )
            )

            def add_student(attempt):
                """Добавление новой карточки стандартным сервисом."""
                return StudentService(db).add(
                    {
                        "student": dict(
                            full_name="Новая карточка " + str(attempt),
                            phone="",
                            messenger_type="",
                            messenger_contact="",
                            is_archived=False,
                        ),
                        "parents": [],
                        "enrollments": [
                            dict(
                                subject_name="Тестовый предмет 1",
                                preparation_goal="ОГЭ",
                                price="1400",
                            )
                        ],
                    }
                )

            results.append(
                measure(
                    "Добавление ученика",
                    add_student,
                    lambda student_id: expect(
                        StudentRepository(db).get_by_id(student_id) is not None
                    ),
                    2,
                )
            )

            def update_student(attempt):
                """Изменение полной карточки без переписывания истории занятий."""
                service = StudentService(db)
                card = service.get_card(1)
                card["student"]["phone"] = "Тест " + str(attempt)
                service.update(1, card)
                return StudentRepository(db).get_by_id(1)

            results.append(
                measure(
                    "Изменение карточки ученика",
                    update_student,
                    lambda student: expect(student.phone.startswith("Тест ")),
                    2,
                )
            )
            lessons = LessonService(db)
            new_lessons = []

            def add_lesson(attempt):
                """Добавление на свободное время после исходного расписания."""
                lesson = lessons.schedule(
                    1, datetime(2030, 1, 1, 10) + timedelta(days=attempt), 60
                )
                new_lessons.append(lesson.lesson_id)
                return lesson

            results.append(
                measure(
                    "Добавление занятия",
                    add_lesson,
                    lambda lesson: expect(lesson.price_kopecks == 140000),
                    2,
                )
            )
            results.append(
                measure(
                    "Перенос занятия",
                    lambda attempt: lessons.reschedule(
                        new_lessons[attempt],
                        datetime(2030, 1, 1, 12) + timedelta(days=attempt),
                        datetime(2030, 1, 1, 13) + timedelta(days=attempt),
                    ),
                    lambda lesson: expect(lesson.starts_at.hour == 12),
                    2,
                )
            )
            report = ReportGenerator(db).generate(
                1, date(2024, 3, 1), date(2024, 3, 31)
            )
            output = Path(folder) / "report.txt"

            def save_report(attempt):
                """Сохранение подготовленного отчёта стандартным генератором."""
                ReportGenerator(db).save(report, output)
                return output

            results.append(
                measure(
                    "Сохранение TXT",
                    save_report,
                    lambda path: expect(path.read_text(encoding="utf-8") == report),
                    5,
                )
            )
            expect(LessonRepository(db).get_by_id(1).price_kopecks == 140000)
            expect(
                db.connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            )
            expect(db.connection.execute("PRAGMA foreign_key_check").fetchall() == [])
        finally:
            db.close()
    return {
        "created_msk": datetime.now(timezone(timedelta(hours=3))).isoformat(),
        "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version,
        "platform": platform.platform(),
        "scope": "data_and_controller_without_native_window_rendering",
        "initial_counts": counts,
        "results": results,
        "all_within_limits": all(result["within_limit"] for result in results),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Файл JSON с результатами")
    args = parser.parse_args()
    summary = run()
    if args.output:
        args.output.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print("Все операции в пределах лимитов:", summary["all_within_limits"])
    raise SystemExit(0 if summary["all_within_limits"] else 1)
