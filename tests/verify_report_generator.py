"""Verify inclusive reporting, historic balances and UTF-8 TXT export."""

import ast
import sqlite3
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.dont_write_bytecode = True
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from database import DatabaseManager

namespace = {"__name__": "candidate_report_generator"}
candidate = PROJECT / "report_generator.py"
exec(compile(candidate.read_text(encoding="utf-8"), str(candidate), "exec"), namespace)
ReportGenerator = namespace["ReportGenerator"]
tree = ast.parse((PROJECT / "init_db.py").read_text(encoding="utf-8"))
schema = next(
    ast.literal_eval(n.args[0])
    for n in ast.walk(tree)
    if isinstance(n, ast.Call)
    and isinstance(n.func, ast.Attribute)
    and n.func.attr == "executescript"
)


def reject(action):
    try:
        action()
    except ValueError:
        return
    raise AssertionError("Invalid operation accepted")


with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / "repetitor.db"
    connection = sqlite3.connect(path)
    connection.executescript(schema)
    connection.close()
    db = DatabaseManager()
    db.db_path = path
    generator = ReportGenerator(db)
    subjects = generator.subject_repository
    db.connection.executemany(
        "INSERT INTO students (full_name, is_archived) VALUES (?, ?);",
        [["Тестовый ученик", 1], ["Другой ученик", 0], ["Нет записей", 0]],
    )
    subject_id = subjects.add("  Математика ")
    spare = subjects.add("Физика")
    subjects.update(spare, "Астрономия")
    assert subjects.get_by_id(spare)[1] == "Астрономия"
    assert len(subjects.get_all()) == 2
    subjects.delete(spare)
    assert subjects.get_by_id(spare) is None
    reject(lambda: subjects.add(" "))
    reject(lambda: subjects.update(9999, "Нет такого"))
    reject(lambda: subjects.delete(9999))
    db.connection.executemany(
        """INSERT INTO enrollments
        (student_id, subject_id, preparation_goal, price_60_kopecks)
        VALUES (?, ?, 'ЕГЭ', 999999);""",
        [[1, subject_id], [2, subject_id]],
    )
    reject(lambda: subjects.delete(subject_id))
    db.connection.executemany(
        """INSERT INTO lessons
        (enrollment_id, starts_at, ends_at, price_kopecks, status)
        VALUES (?, ?, ?, ?, ?);""",
        [
            [1, "2026-11-02 10:00:00", "2026-11-02 11:00:00", 140000, "Проведено"],
            [1, "2026-11-04 10:00:00", "2026-11-04 10:30:00", 70000, "Проведено"],
            [1, "2026-12-01 10:00:00", "2026-12-01 11:30:00", 210000, "Запланировано"],
            [1, "2026-11-06 10:00:00", "2026-11-06 11:00:00", 140000, "Отменено"],
            [2, "2026-11-04 12:00:00", "2026-11-04 13:00:00", 5000, "Проведено"],
        ],
    )
    db.connection.executemany(
        """INSERT INTO payments
        (student_id, lesson_id, paid_at, amount_kopecks) VALUES (1, ?, ?, ?);""",
        [
            [1, "2026-11-01 23:59:59", 140000],
            [3, "2026-11-05 00:00:00", 210000],
            [4, "2026-11-07 23:59:59", 140000],
        ],
    )
    db.connection.executemany(
        "INSERT INTO lesson_topics (lesson_id, topic_name) VALUES (1, ?);",
        [["Дроби"], ["Уравнения"]],
    )
    db.connection.commit()

    report = generator.generate(1, date(2026, 11, 3), date(2026, 11, 6))
    assert "Ученик: Тестовый ученик" in report
    assert "Количество занятий: 1" in report
    assert "Предмет: Математика" in report
    assert "Цель подготовки: ЕГЭ" in report
    assert "Темы не указаны" in report
    assert "Начислено за период: 700,00 руб." in report
    assert "Получено за период: 2100,00 руб." in report
    assert "Баланс на начало периода: 0,00 руб." in report
    assert "Баланс на конец периода: Переплата: 1400,00 руб." in report
    assert "занятие №3" in report  # Prepayment for next month's lesson.
    assert "занятие №4" not in report  # Receipt is after the selected end date.
    assert (
        "Стоимость: 9999,99" not in report
    )  # Current tariff does not reprice history.

    before_later_receipts = generator.generate(1, date(2026, 11, 1), date(2026, 11, 4))
    assert "Баланс на конец периода: Долг: 700,00 руб." in before_later_receipts
    assert "Темы: Дроби; Уравнения" in before_later_receipts
    assert "Количество занятий: 2" in before_later_receipts
    single_day = generator.generate(1, date(2026, 11, 2), date(2026, 11, 2))
    assert "Баланс на начало периода: Переплата: 1400,00 руб." in single_day
    assert "Баланс на конец периода: 0,00 руб." in single_day
    canceled_payment = generator.generate(1, date(2026, 11, 5), date(2026, 11, 7))
    assert "Количество занятий: 0" in canceled_payment
    assert "Получено за период: 3500,00 руб." in canceled_payment
    assert "Баланс на начало периода: Долг: 700,00 руб." in canceled_payment
    assert "Баланс на конец периода: Переплата: 2800,00 руб." in canceled_payment
    empty = generator.generate(3, date(2026, 11, 1), date(2026, 11, 30))
    assert "Проведённых занятий за период нет." in empty
    assert "Оплат за период нет." in empty
    assert "Баланс на конец периода: 0,00 руб." in empty
    assert generator._money(1) == "0,01 руб."
    reject(lambda: generator.generate(9999, date(2026, 11, 1), date(2026, 11, 30)))
    reject(lambda: generator.generate(1, date(2026, 11, 30), date(2026, 11, 1)))
    reject(lambda: generator.generate(1, "01.11.2026", date(2026, 11, 30)))
    output = Path(directory) / "Отчёт.txt"
    generator.save(report, output)
    assert output.read_text(encoding="utf-8") == report
    assert db.connection.in_transaction is False
    assert db.connection.execute("PRAGMA foreign_key_check;").fetchall() == []
    db.close()

print(
    (
        "PASS: subject CRUD, inclusive reporting, historical balances, "
        "prepaid/canceled receipts, saved prices, topics/empty states, archived "
        "pupils, validation and UTF-8 export"
    )
)
