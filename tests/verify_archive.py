"""Check archive/restore callbacks, filtering, and unchanged financial history."""

import ast
import importlib.util
import sqlite3
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.dont_write_bytecode = True
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from database import DatabaseManager
from student_service import StudentService
from billing_service import BillingService

spec = importlib.util.spec_from_file_location(
    "archive_controller", (PROJECT / "main.py")
)
gui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gui)
tree = ast.parse((PROJECT / "init_db.py").read_text(encoding="utf-8"))
schema = next(
    ast.literal_eval(n.args[0])
    for n in ast.walk(tree)
    if isinstance(n, ast.Call)
    and isinstance(n.func, ast.Attribute)
    and n.func.attr == "executescript"
)


class View:
    selected_id = 1
    archive_mode = False

    def refresh(self):
        self.rows = app.load_students("", self.archive_mode)
        if self.selected_id not in [row["student"].student_id for row in self.rows]:
            self.selected_id = None


def contact(name):
    return dict(full_name=name, phone="", messenger_type="", messenger_contact="")


with tempfile.TemporaryDirectory() as folder:
    db = DatabaseManager()
    db.db_path = Path(folder) / "archive.db"
    con = sqlite3.connect(db.db_path)
    con.executescript(schema)
    con.close()
    service = StudentService(db)
    service.add(
        dict(
            student=dict(contact("Архивируемый ученик"), is_archived=False),
            parents=[dict(contact("Родитель"), is_primary=True)],
            enrollments=[
                dict(subject_name="Математика", preparation_goal="ЕГЭ", price="1400")
            ],
        )
    )
    service.add(
        dict(
            student=dict(contact("Другой ученик"), is_archived=False),
            parents=[],
            enrollments=[],
        )
    )
    with db.connection:
        db.connection.executemany(
            """INSERT INTO lessons
            (enrollment_id, starts_at, ends_at, price_kopecks, status)
            VALUES (1, ?, ?, 140000, ?)""",
            [
                ("2026-10-10 10:00:00", "2026-10-10 11:00:00", "Проведено"),
                ("2026-10-11 10:00:00", "2026-10-11 11:00:00", "Проведено"),
                ("2026-12-10 10:00:00", "2026-12-10 11:00:00", "Запланировано"),
            ],
        )
        db.connection.execute(
            "INSERT INTO lesson_topics (lesson_id, topic_name) VALUES (1, 'Тема')"
        )
        db.connection.execute("""INSERT INTO payments
            (student_id, lesson_id, paid_at, amount_kopecks)
            VALUES (1, 1, '2026-10-10 12:00:00', 140000)""")
    tables = (
        "parents",
        "student_parents",
        "subjects",
        "enrollments",
        "lessons",
        "lesson_topics",
        "payments",
    )

    def history():
        return [
            db.connection.execute("SELECT * FROM " + table).fetchall()
            for table in tables
        ]

    before = history()
    balance = BillingService(db).get_summary(1)
    assert balance["debt"] == 140000
    student_before = db.connection.execute(
        (
            "SELECT student_id, full_name, phone, messenger_type, messenger_contact "
            "FROM students WHERE student_id=1"
        )
    ).fetchone()
    app = gui.ApplicationController.__new__(gui.ApplicationController)
    app.db = db
    app.root = None
    app.authenticator = SimpleNamespace(current_user_id=1)
    app.students_view = View()
    messages = []
    gui.messagebox.showinfo = lambda *args, **kwargs: messages.append(args)

    def unexpected_error(*args, **kwargs):
        raise AssertionError(args)

    gui.messagebox.showerror = unexpected_error
    try:
        app.move_student()
        assert service.get_card(1)["student"]["is_archived"]
        assert [row["student"].student_id for row in app.students_view.rows] == [2]
        assert app.students_view.selected_id is None
        assert [
            row["student"].student_id for row in app.load_students("АРХИВИРУ", True)
        ] == [1]
        assert app.load_students("00001", False) == []
        assert len(app.load_students("00001", True)) == 1
        assert history() == before and BillingService(db).get_summary(1) == balance
        app.students_view.archive_mode = True
        app.students_view.selected_id = 1
        app.move_student()
        assert not service.get_card(1)["student"]["is_archived"]
        assert app.students_view.rows == [] and app.students_view.selected_id is None
        assert history() == before and BillingService(db).get_summary(1) == balance
        assert (
            db.connection.execute(
                (
                    "SELECT student_id, full_name, phone, messenger_type, "
                    "messenger_contact FROM students WHERE student_id=1"
                )
            ).fetchone()
            == student_before
        )
        service.set_archived(1, False)
        for student_id, state in ((999, True), (True, True), (1, "True")):
            try:
                service.set_archived(student_id, state)
                raise AssertionError("Invalid input accepted")
            except ValueError:
                pass
            assert not db.connection.in_transaction
        app.authenticator.current_user_id = None
        app.students_view.archive_mode = False
        app.students_view.selected_id = 1
        app.move_student()
        assert not service.get_card(1)["student"]["is_archived"]
        db.connection.execute("INSERT INTO subjects (name) VALUES ('Чужая транзакция')")
        try:
            service.set_archived(1, True)
            raise AssertionError("Foreign transaction accepted")
        except ValueError:
            pass
        assert db.connection.in_transaction
        db.connection.rollback()
        assert db.connection.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        db.close()

print(
    (
        "PASS: archive/restore and search isolation, preserved paid/unpaid/planned "
        "lessons and balance, stable contacts/IDs, auth guard, transaction "
        "rollback/ownership"
    )
)
