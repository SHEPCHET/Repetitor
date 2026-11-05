"""Check atomic student-card saves in a temporary database."""

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


data = dict(
    student=dict(contact("Ученик"), is_archived=False),
    parents=[dict(contact("Родитель"), is_primary=True)],
    enrollments=[
        dict(subject_name="Математика", preparation_goal="ЕГЭ", price="1 400,50")
    ],
)

with tempfile.TemporaryDirectory() as folder:
    db = DatabaseManager()
    db.db_path = Path(folder) / "isolated.db"
    connection = sqlite3.connect(db.db_path)
    connection.executescript(schema)
    connection.execute("INSERT INTO subjects (name) VALUES ('Математика')")
    connection.commit()
    connection.close()
    service = StudentService(db)
    db.connection.executescript("""
        CREATE TRIGGER reject_test_enrollment BEFORE INSERT ON enrollments
        WHEN NEW.preparation_goal = 'Отклонить'
        BEGIN SELECT RAISE(ABORT, 'test dependent failure'); END;
    """)

    def counts():
        return tuple(
            db.connection.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
            for table in ("students", "parents", "student_parents", "enrollments")
        )

    try:
        student_id = service.add(data)
        assert student_id == 1 and counts() == (1, 1, 1, 1)
        assert (
            db.connection.execute(
                "SELECT price_60_kopecks FROM enrollments"
            ).fetchone()[0]
            == 140050
        )
        assert not db.connection.in_transaction
        before = counts()
        bad = copy.deepcopy(data)
        bad["enrollments"].append(
            dict(
                subject_name="Несохранённый предмет",
                preparation_goal="Отклонить",
                price="100",
            )
        )
        try:
            service.add(bad)
            raise AssertionError("Missing FK error")
        except sqlite3.IntegrityError:
            pass
        assert counts() == before and not db.connection.in_transaction
        assert db.connection.execute("SELECT COUNT(*) FROM subjects").fetchone()[0] == 1
        for price in ("-1", "1,001", "nan", "", "1.2.3"):
            bad = copy.deepcopy(data)
            bad["enrollments"][0]["price"] = price
            try:
                service.add(bad)
                raise AssertionError("Invalid price accepted")
            except ValueError:
                pass
            assert counts() == before
        bad = copy.deepcopy(data)
        bad["parents"].append(dict(contact("Другой родитель"), is_primary=True))
        try:
            service.add(bad)
            raise AssertionError("Two primary contacts accepted")
        except ValueError:
            pass
        assert counts() == before
        empty = dict(
            student=dict(contact("Без родителей"), is_archived=True),
            parents=[dict(contact(""), is_primary=True)],
            enrollments=[dict(subject_name="", preparation_goal="", price="")],
        )
        assert service.add(empty) == 2
        assert counts() == (2, 1, 1, 1)
        assert (
            db.connection.execute(
                "SELECT is_archived FROM students WHERE student_id=2"
            ).fetchone()[0]
            == 1
        )
        db.connection.execute(
            "INSERT INTO subjects (name) VALUES ('Незавершённая запись')"
        )
        try:
            service.add(data)
            raise AssertionError("Foreign transaction accepted")
        except ValueError:
            pass
        assert db.connection.in_transaction and counts() == (2, 1, 1, 1)
        db.connection.rollback()
        new = copy.deepcopy(data)
        new["enrollments"][0]["subject_name"] = "  Физика  "
        assert service.add(new) == 3
        assert (
            db.connection.execute(
                "SELECT name FROM subjects WHERE subject_id=2"
            ).fetchone()[0]
            == "Физика"
        )
        new["enrollments"][0]["subject_name"] = "фИзИкА"
        assert service.add(new) == 4
        assert db.connection.execute("SELECT COUNT(*) FROM subjects").fetchone()[0] == 2
        assert (
            db.connection.execute(
                (
                    "SELECT COUNT(DISTINCT subject_id) FROM enrollments WHERE "
                    "student_id IN (3,4)"
                )
            ).fetchone()[0]
            == 1
        )
    finally:
        db.close()

print(
    (
        "PASS: typed subject create and Cyrillic reuse, subject rollback with whole "
        "card, exact kopecks, validation, optional rows, archive flag, foreign "
        "transaction preserved"
    )
)
