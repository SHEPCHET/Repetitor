"""Check calendar boundaries, clipping, colours and read-only schedule loading."""

import ast
import base64
import importlib.util
import sqlite3
import struct
import sys
import tempfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace

sys.dont_write_bytecode = True
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from database import DatabaseManager
from student_service import StudentService
from schedule_view import month_weeks, lesson_parts, lesson_color, LEGEND_IMAGES

assert month_weeks(2026, 10)[3] == date(2026, 10, 19)
assert month_weeks(2026, 11)[2] == date(2026, 11, 9)
assert month_weeks(2024, 2)[-1] == date(2024, 2, 26)
assert month_weeks(2026, 12)[-1] == month_weeks(2027, 1)[0]
assert month_weeks(1, 1)[0] == date(1, 1, 1)
assert len(LEGEND_IMAGES) == 4
for number, data in LEGEND_IMAGES.items():
    png = base64.b64decode(data)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", png[16:24]) == (33, 30)
    path = [
        "planned_unpaid.png",
        "completed_unpaid.png",
        "completed_paid.png",
        "planned_paid.png",
    ][int(number)]
    assert (
        png == Path(__file__).with_name("schedule-assets").joinpath(path).read_bytes()
    )

spec = importlib.util.spec_from_file_location(
    "schedule_controller", (PROJECT / "main.py")
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

with tempfile.TemporaryDirectory() as folder:
    db = DatabaseManager()
    db.db_path = Path(folder) / "schedule.db"
    con = sqlite3.connect(db.db_path)
    con.executescript(schema)
    con.close()
    service = StudentService(db)
    service.add(
        dict(
            student=dict(
                full_name="Фамилия Имя Отчество",
                phone="",
                messenger_type="",
                messenger_contact="",
                is_archived=True,
            ),
            parents=[],
            enrollments=[
                dict(subject_name="Математика", preparation_goal="ЕГЭ", price="1400")
            ],
        )
    )
    rows = [
        ("2026-11-10 10:00:00", "2026-11-10 11:30:00", "Запланировано"),
        ("2026-11-09 14:30:00", "2026-11-09 15:30:00", "Запланировано"),
        ("2026-11-11 08:00:00", "2026-11-11 09:00:00", "Проведено"),
        ("2026-11-12 15:00:00", "2026-11-12 16:00:00", "Проведено"),
        ("2026-11-13 10:00:00", "2026-11-13 11:00:00", "Отменено"),
        ("2026-11-08 23:30:00", "2026-11-09 08:30:00", "Запланировано"),
        ("2026-11-15 21:30:00", "2026-11-16 08:30:00", "Запланировано"),
        ("2026-11-16 10:00:00", "2026-11-16 11:00:00", "Запланировано"),
        ("2026-11-08 20:00:00", "2026-11-08 21:00:00", "Запланировано"),
    ]
    with db.connection:
        db.connection.executemany(
            """INSERT INTO lessons
            (enrollment_id, starts_at, ends_at, price_kopecks, status)
            VALUES (1, ?, ?, 140000, ?)""",
            rows,
        )
        db.connection.executemany(
            """INSERT INTO payments
            (student_id, lesson_id, paid_at, amount_kopecks)
            VALUES (1, ?, '2026-11-01 12:00:00', 140000)""",
            [(1,), (4,)],
        )
    app = gui.ApplicationController.__new__(gui.ApplicationController)
    app.db = db
    app.root = None
    app.authenticator = SimpleNamespace(current_user_id=1)
    errors = []
    gui.messagebox.showerror = lambda *args, **kwargs: errors.append(args)
    monday = date(2026, 11, 9)
    before = tuple(db.connection.iterdump())
    try:
        items = app.load_schedule(monday, date(2026, 11, 15))
        by_id = {item["lesson"].lesson_id: item for item in items}
        assert set(by_id) == {1, 2, 3, 4, 6, 7}
        assert by_id[1]["paid"] and by_id[4]["paid"]
        assert not by_id[2]["paid"]
        assert by_id[1]["subject"] == "Математика"
        assert by_id[1]["student_name"] == "Фамилия Имя Отчество"
        assert lesson_parts(by_id[1]["lesson"], monday, 1) == [(1, 4, 7)]
        assert lesson_parts(by_id[2]["lesson"], monday, 1) == [(0, 13, 14)]
        assert lesson_parts(by_id[2]["lesson"], monday, 2) == [(0, 0, 1)]
        assert lesson_parts(by_id[6]["lesson"], monday, 1) == [(0, 0, 1)]
        assert lesson_parts(by_id[7]["lesson"], monday, 2) == [(6, 13, 14)]
        assert lesson_color(by_id[1]["lesson"], True) == "#9dfff4"
        assert lesson_color(by_id[2]["lesson"], False) == "#f5f5f5"
        assert lesson_color(by_id[3]["lesson"], False) == "#fcccff"
        assert lesson_color(by_id[4]["lesson"], True) == "#c7fb72"
        next_week = app.load_schedule(date(2026, 11, 16), date(2026, 11, 22))
        assert {item["lesson"].lesson_id for item in next_week} == {7, 8}
        assert tuple(db.connection.iterdump()) == before
        assert not db.connection.in_transaction
        assert app.load_schedule(date(2026, 1, 1), date(2026, 1, 7)) == []
        assert app.load_schedule(date(2026, 11, 15), monday) is None and errors
        app.authenticator.current_user_id = None
        assert app.load_schedule(monday, date(2026, 11, 15)) == []
    finally:
        db.close()

print(
    (
        "PASS: month/year/leap boundaries, 90-minute cells, half/week/midnight "
        "clipping, cancelled exclusion, full colour matrix, prepaid/archive history, "
        "no writes and auth guard; original PNG assets 33x30"
    )
)
