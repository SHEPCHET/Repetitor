"""Check card updates and retained lesson/payment history in an isolated database."""

import ast
import copy
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from database import DatabaseManager
from student_service import StudentService

tree = ast.parse((PROJECT / "init_db.py").read_text(encoding="utf-8"))
schema = next(
    ast.literal_eval(n.args[0])
    for n in ast.walk(tree)
    if isinstance(n, ast.Call)
    and isinstance(n.func, ast.Attribute)
    and n.func.attr == "executescript"
)


def contact(name):
    return dict(full_name=name, phone="", messenger_type="", messenger_contact="")


def new_data(name):
    return dict(
        student=dict(contact(name), is_archived=False), parents=[], enrollments=[]
    )


with tempfile.TemporaryDirectory() as folder:
    db = DatabaseManager()
    db.db_path = Path(folder) / "edit.db"
    con = sqlite3.connect(db.db_path)
    con.executescript(schema)
    con.close()
    service = StudentService(db)

    def snapshot():
        return tuple(db.connection.iterdump())

    def rejected(data):
        before = snapshot()
        try:
            service.update(1, data)
            raise AssertionError("Invalid edit accepted")
        except ValueError:
            pass
        assert snapshot() == before
        assert not db.connection.in_transaction

    try:
        first = new_data("Первый ученик")
        first["parents"] = [
            dict(contact("Первый родитель"), is_primary=True),
            dict(contact("Второй родитель"), is_primary=False),
        ]
        first["enrollments"] = [
            dict(subject_name="Математика", preparation_goal="ЕГЭ", price="1400")
        ]
        service.add(first)
        other = new_data("Другой ученик")
        other["parents"] = [dict(contact("Чужой родитель"), is_primary=True)]
        other["enrollments"] = [
            dict(subject_name="История", preparation_goal="ОГЭ", price="1000")
        ]
        service.add(other)
        with db.connection:
            service.parents.link(2, 1, False)
            db.connection.execute("""INSERT INTO lessons
                (enrollment_id, starts_at, ends_at, price_kopecks, status)
                VALUES (1, '2026-10-10 10:00:00',
                        '2026-10-10 11:00:00', 140000, 'Проведено')""")
            db.connection.execute(
                (
                    "INSERT INTO lesson_topics (lesson_id, topic_name) VALUES (1, "
                    "'Алгебра')"
                )
            )
            db.connection.execute(
                """INSERT INTO payments (student_id, lesson_id, paid_at, amount_kopecks)
                VALUES (1, 1, '2026-10-10 12:00:00', 140000)"""
            )
        before = snapshot()
        record = service.get_card(1)
        assert snapshot() == before
        assert record["parents"][0]["parent_id"] == 1
        assert record["enrollments"][0]["enrollment_id"] == 1
        assert record["enrollments"][0]["price"] == "1400,00"
        record["student"]["full_name"] = "Исправленное ФИО"
        record["student"]["phone"] = "123"
        record["parents"][0]["phone"] = "456"
        record["parents"][0]["is_primary"] = False
        record["parents"][1]["is_primary"] = True
        record["parents"].append(
            dict(contact("Новый родитель"), is_primary=False, parent_id=None)
        )
        record["enrollments"][0]["price"] = "1600,50"
        record["enrollments"].append(
            dict(
                subject_name="Физика",
                preparation_goal="ОГЭ",
                price="1500",
                enrollment_id=None,
            )
        )
        service.update(1, record)
        saved = service.get_card(1)
        assert saved["student"]["full_name"] == "Исправленное ФИО"
        assert (
            saved["parents"][0]["parent_id"] == 2 and saved["parents"][0]["is_primary"]
        )
        assert len(saved["parents"]) == 3 and len(saved["enrollments"]) == 2
        assert saved["enrollments"][0]["enrollment_id"] == 1
        assert saved["enrollments"][0]["price"] == "1600,50"
        assert db.connection.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 2
        assert db.connection.execute("SELECT COUNT(*) FROM parents").fetchone()[0] == 4
        assert (
            db.connection.execute(
                (
                    "SELECT COUNT(*) FROM student_parents WHERE student_id=2 AND "
                    "parent_id=1"
                )
            ).fetchone()[0]
            == 1
        )
        assert (
            db.connection.execute(
                "SELECT price_kopecks FROM lessons WHERE lesson_id=1"
            ).fetchone()[0]
            == 140000
        )
        assert (
            db.connection.execute(
                "SELECT amount_kopecks FROM payments WHERE payment_id=1"
            ).fetchone()[0]
            == 140000
        )
        assert (
            db.connection.execute(
                "SELECT topic_name FROM lesson_topics WHERE lesson_id=1"
            ).fetchone()[0]
            == "Алгебра"
        )

        bad = copy.deepcopy(saved)
        bad["student"]["full_name"] = "Не сохранять"
        bad["parents"][0]["phone"] = "Не сохранять"
        bad["enrollments"][0]["subject_name"] = "Новый запрещённый предмет"
        rejected(bad)
        bad = copy.deepcopy(saved)
        bad["enrollments"] = bad["enrollments"][1:]
        rejected(bad)
        bad = copy.deepcopy(saved)
        bad["parents"][0]["parent_id"] = 3
        rejected(bad)
        bad = copy.deepcopy(saved)
        bad["enrollments"][0]["enrollment_id"] = 2
        rejected(bad)
        bad = copy.deepcopy(saved)
        bad["parents"].append(copy.deepcopy(bad["parents"][1]))
        rejected(bad)

        saved["parents"] = [p for p in saved["parents"] if p["parent_id"] != 1]
        saved["enrollments"] = saved["enrollments"][:1]
        service.update(1, saved)
        assert len(service.get_card(1)["parents"]) == 2
        assert len(service.get_card(1)["enrollments"]) == 1
        assert service.parents.get_by_id(1) is not None
        assert any(p.parent_id == 1 for p, primary in service.parents.get_by_student(2))
        assert db.connection.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        db.close()

print(
    (
        "PASS: prefill and stable IDs, contact and tariff edits, adding rows, primary"
        " change, shared-parent links, retained paid lesson/topics, rollback on "
        "historical/foreign edits, removal of unused rows"
    )
)
