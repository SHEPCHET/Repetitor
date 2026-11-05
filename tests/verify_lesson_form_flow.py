"""Check adding from GUI data with real lesson rules and an isolated database."""

import ast
import importlib.util
import sqlite3
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

sys.dont_write_bytecode = True
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from database import DatabaseManager
from student_service import StudentService
from lesson_form import duration_minutes

assert duration_minutes("1", "30") == 90
assert duration_minutes("0", "30") == 30
for hours, minutes in (("0", "00"), ("-1", "00"), ("1", "15"), ("", "30")):
    try:
        duration_minutes(hours, minutes)
        raise AssertionError("Invalid duration accepted")
    except ValueError:
        pass

spec = importlib.util.spec_from_file_location(
    "lesson_form_controller", (PROJECT / "main.py")
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


class FakeForm:
    def __init__(self, *args):
        self.destroyed = False
        self.students = args[2] if args else []

    def destroy(self):
        self.destroyed = True

    def lift(self):
        pass


class FakeSchedule:
    monday = date(2026, 11, 9)
    half = SimpleNamespace(get=lambda: "1")
    last = None

    def show_lesson(self, lesson):
        self.last = lesson


with tempfile.TemporaryDirectory() as folder:
    db = DatabaseManager()
    db.db_path = Path(folder) / "add_lesson.db"
    con = sqlite3.connect(db.db_path)
    con.executescript(schema)
    con.close()
    service = StudentService(db)
    for number, price in enumerate(("1400,01", "1800", "1000"), 1):
        service.add(
            dict(
                student=dict(
                    full_name="Ученик " + str(number),
                    phone="",
                    messenger_type="",
                    messenger_contact="",
                    is_archived=number == 3,
                ),
                parents=[],
                enrollments=[
                    dict(subject_name="Математика", preparation_goal="ЕГЭ", price=price)
                ],
            )
        )
    app = gui.ApplicationController.__new__(gui.ApplicationController)
    app.db = db
    app.root = None
    app.authenticator = SimpleNamespace(current_user_id=1)
    app.main_window = SimpleNamespace(family="Arial")
    app.schedule_view = FakeSchedule()
    app.lesson_form = None
    gui.LessonForm = FakeForm
    gui.LessonService._now = lambda self: datetime(2026, 11, 5, 12)
    messages = []
    gui.messagebox.showinfo = lambda *args, **kwargs: messages.append(("info", args))
    gui.messagebox.showerror = lambda *args, **kwargs: messages.append(("error", args))
    payload = dict(
        student_id=1,
        enrollment_id=1,
        date="11.11.2026",
        time="10:00",
        hours="1",
        minutes="30",
    )

    def count():
        return db.connection.execute("SELECT COUNT(*) FROM lessons").fetchone()[0]

    def rejected(data):
        form = FakeForm()
        app.lesson_form = form
        before = tuple(db.connection.iterdump())
        app.save_lesson(data)
        assert tuple(db.connection.iterdump()) == before
        assert app.lesson_form is form and not form.destroyed
        assert messages[-1][0] == "error"
        assert not db.connection.in_transaction

    try:
        before = tuple(db.connection.iterdump())
        app.open_lesson_form()
        assert [row.student_id for row in app.lesson_form.students] == [1, 2]
        app.close_lesson_form()
        assert tuple(db.connection.iterdump()) == before
        directions = app.load_lesson_directions(1)
        assert directions[0]["subject"] == "Математика"
        assert directions[0]["enrollment"].calculate_price(90) == 210002
        assert app.load_lesson_directions(3) is None
        form = FakeForm()
        app.lesson_form = form
        app.save_lesson(payload)
        assert count() == 1 and form.destroyed and app.lesson_form is None
        assert app.schedule_view.last.price_kopecks == 210002
        assert app.schedule_view.last.status == "Запланировано"
        assert app.schedule_view.last.ends_at == datetime(2026, 11, 11, 11, 30)
        assert db.connection.execute("SELECT COUNT(*) FROM payments").fetchone()[0] == 0
        rejected(dict(payload, student_id=2, enrollment_id=2, time="10:30"))
        assert "уже назначено" in messages[-1][1][1]
        rejected(dict(payload, student_id=1, enrollment_id=2))
        rejected(dict(payload, student_id=3, enrollment_id=3))
        rejected(dict(payload, date="31.02.2026"))
        rejected(dict(payload, time="10:15"))
        rejected(dict(payload, hours="0", minutes="00"))
        app.lesson_form = FakeForm()
        app.save_lesson(
            dict(
                payload,
                student_id=2,
                enrollment_id=2,
                time="11:30",
                hours="1",
                minutes="00",
            )
        )
        assert count() == 2 and app.schedule_view.last.price_kopecks == 180000
        app.lesson_form = FakeForm()
        app.save_lesson(
            dict(payload, date="01.11.2026", time="08:00", hours="0", minutes="30")
        )
        assert count() == 3 and app.schedule_view.last.status == "Проведено"
        app.authenticator.current_user_id = None
        before = tuple(db.connection.iterdump())
        app.save_lesson(payload)
        assert tuple(db.connection.iterdump()) == before
    finally:
        db.close()

print(
    (
        "PASS: active students/directions, cancel without writes, 90-minute "
        "pricing/rounding, overlap rollback across students, adjacency, "
        "input/ownership/archive/auth guards, saved-date focus and historical status"
    )
)
