"""Отмена занятий на отдельной базе."""

import ast
import importlib.util
import sqlite3
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

sys.dont_write_bytecode = True
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from database import DatabaseManager
from student_service import StudentService
from billing_service import BillingService
from schedule_view import (
    cancelled_rows,
    lesson_parts,
    lesson_color,
    ScheduleView,
    CANCELLED_LEGEND_IMAGE,
)
import base64
import struct

assert struct.unpack(">II", base64.b64decode(CANCELLED_LEGEND_IMAGE)[16:24]) == (33, 30)
assert (
    base64.b64decode(CANCELLED_LEGEND_IMAGE)
    == Path(__file__)
    .with_name("schedule-assets")
    .joinpath("cancelled.png")
    .read_bytes()
)

spec = importlib.util.spec_from_file_location("cancel_gui", (PROJECT / "main.py"))
gui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gui)
tree = ast.parse((PROJECT / "init_db.py").read_text(encoding="utf-8-sig"))
schema = next(
    ast.literal_eval(node.args[0])
    for node in ast.walk(tree)
    if isinstance(node, ast.Call)
    and isinstance(node.func, ast.Attribute)
    and node.func.attr == "executescript"
)

with tempfile.TemporaryDirectory() as folder:
    db = DatabaseManager()
    db.db_path = Path(folder) / "cancel.db"
    connection = sqlite3.connect(db.db_path)
    connection.executescript(schema)
    connection.close()
    try:
        StudentService(db).add(
            dict(
                student=dict(
                    full_name="Тестовый ученик",
                    phone="",
                    messenger_type="",
                    messenger_contact="",
                    is_archived=False,
                ),
                parents=[],
                enrollments=[
                    dict(
                        subject_name="Математика", preparation_goal="ЕГЭ", price="1400"
                    )
                ],
            )
        )
        gui.LessonService._now = lambda self: datetime(2026, 11, 20, 12)
        service = gui.LessonService(db)
        paid = service.schedule(1, datetime(2026, 11, 10, 10), 90)
        unpaid = service.schedule(1, datetime(2026, 11, 11, 10), 90)
        with db.connection:
            db.connection.execute(
                (
                    "INSERT INTO payments (student_id, lesson_id, paid_at, "
                    "amount_kopecks) VALUES (1, ?, '2026-11-03 12:00:00', 210000)"
                ),
                [paid.lesson_id],
            )
            db.connection.execute(
                "INSERT INTO lesson_topics (lesson_id, topic_name) VALUES (?, 'Дроби')",
                [paid.lesson_id],
            )
        app = gui.ApplicationController.__new__(gui.ApplicationController)
        app.db = db
        app.root = None
        app.authenticator = SimpleNamespace(current_user_id=1)
        refreshes = []
        app.schedule_view = SimpleNamespace(
            selected_lesson_id=paid.lesson_id, refresh=lambda: refreshes.append(1)
        )
        messages = []
        confirmations = []
        answer = False

        def confirm(*args, **kwargs):
            confirmations.append(args)
            return answer

        gui.messagebox.askyesno = confirm
        gui.messagebox.showerror = lambda *args, **kwargs: messages.append(
            ("error", args)
        )
        gui.messagebox.showinfo = lambda *args, **kwargs: messages.append(
            ("info", args)
        )

        def snapshot():
            return tuple(db.connection.iterdump())

        before = snapshot()
        app.cancel_lesson()
        assert snapshot() == before and not refreshes
        assert "10.11.2026 10:00" in confirmations[-1][1]
        receipts = db.connection.execute("SELECT * FROM payments").fetchall()
        topics = db.connection.execute("SELECT * FROM lesson_topics").fetchall()
        old = db.connection.execute(
            "SELECT * FROM lessons WHERE lesson_id = ?", [paid.lesson_id]
        ).fetchone()
        answer = True
        app.cancel_lesson()
        new = db.connection.execute(
            "SELECT * FROM lessons WHERE lesson_id = ?", [paid.lesson_id]
        ).fetchone()
        columns = [
            row[1] for row in db.connection.execute("PRAGMA table_info(lessons)")
        ]
        assert [
            (columns[i], a, b) for i, (a, b) in enumerate(zip(old, new)) if a != b
        ] == [("status", "Проведено", "Отменено")]
        assert db.connection.execute("SELECT * FROM payments").fetchall() == receipts
        assert db.connection.execute("SELECT * FROM lesson_topics").fetchall() == topics
        assert [
            item["lesson"].lesson_id
            for item in app.load_schedule(date(2026, 11, 9), date(2026, 11, 15))
        ] == [unpaid.lesson_id]
        assert len(refreshes) == 1 and messages[-1][0] == "info"
        summary = BillingService(db).get_summary(1)
        assert summary["charged"] == 210000 and summary["received"] == 210000
        # Повторная отмена и несуществующий ID не меняют базу.
        for lesson_id in [paid.lesson_id, 999]:
            app.schedule_view.selected_lesson_id = lesson_id
            before = snapshot()
            app.cancel_lesson()
            assert snapshot() == before and messages[-1][0] == "error"
            assert len(refreshes) == 1
        app.schedule_view.selected_lesson_id = unpaid.lesson_id
        app.cancel_lesson()
        assert len(refreshes) == 2
        summary = BillingService(db).get_summary(1)
        assert summary["charged"] == 0 and summary["advance"] == 210000
        assert app.load_schedule(date(2026, 11, 9), date(2026, 11, 15)) == []
        before = snapshot()
        cancelled_items = app.load_schedule(date(2026, 11, 9), date(2026, 11, 15), True)
        assert {item["lesson"].lesson_id for item in cancelled_items} == {
            paid.lesson_id,
            unpaid.lesson_id,
        }
        assert snapshot() == before
        # Отменённое занятие освобождает время.
        service.schedule(1, datetime(2026, 11, 10, 10), 90)
        for authorized, selected in [(None, 3), (1, None)]:
            app.authenticator.current_user_id = authorized
            app.schedule_view.selected_lesson_id = selected
            before = snapshot()
            count = len(confirmations)
            app.cancel_lesson()
            assert snapshot() == before and len(confirmations) == count

        mode_changes = []
        focused = []
        app.schedule_view.cancelled_mode = True
        app.schedule_view.set_cancelled_mode = mode_changes.append
        app.schedule_view.show_lesson = focused.append
        app.schedule_view.selected_lesson_id = paid.lesson_id
        before = snapshot()
        app.restore_lesson()
        assert snapshot() == before and messages[-1][0] == "error"
        assert "уже назначено" in messages[-1][1][1] and not mode_changes
        app.schedule_view.selected_lesson_id = unpaid.lesson_id
        app.restore_lesson()
        restored = gui.LessonRepository(db).get_by_id(unpaid.lesson_id)
        assert restored.status == "Проведено" and restored.price_kopecks == 210000
        assert mode_changes == [False] and focused[-1].lesson_id == unpaid.lesson_id
        assert db.connection.execute("SELECT * FROM payments").fetchall() == receipts
        assert db.connection.execute("SELECT * FROM lesson_topics").fetchall() == topics
        for authorized, selected in [
            (1, unpaid.lesson_id),
            (1, 999),
            (None, paid.lesson_id),
        ]:
            app.authenticator.current_user_id = authorized
            app.schedule_view.selected_lesson_id = selected
            before = snapshot()
            app.restore_lesson()
            assert snapshot() == before
        app.authenticator.current_user_id = 1
        future = service.schedule(1, datetime(2026, 11, 24, 16), 60)
        service.cancel(future.lesson_id)
        app.schedule_view.selected_lesson_id = future.lesson_id
        app.restore_lesson()
        assert focused[-1].status == "Запланировано"

        # Отмена, начавшаяся в прошлой неделе, видна в своей части следующей.
        cross_week = service.schedule(1, datetime(2026, 11, 8, 23, 30), 540)
        service.cancel(cross_week.lesson_id)
        items = app.load_schedule(date(2026, 11, 9), date(2026, 11, 15), True)
        cross = next(
            item["lesson"]
            for item in items
            if item["lesson"].lesson_id == cross_week.lesson_id
        )
        assert lesson_parts(cross, date(2026, 11, 9), 1, True) == [(0, 0, 1)]
        assert lesson_parts(cross, date(2026, 11, 9), 1) == []
        assert lesson_color(cross, True) == "#ffa1a2"

        # Совпавшие отмены не перекрывают друг друга, соседние используют ту же полосу.
        examples = []
        for number, hour, minute in [(1, 10, 0), (2, 10, 0), (3, 11, 30)]:
            start = datetime(2026, 11, 10, hour, minute)
            examples.append(
                {
                    "lesson": SimpleNamespace(
                        lesson_id=number,
                        starts_at=start,
                        ends_at=start + timedelta(minutes=90),
                        status="Отменено",
                    )
                }
            )
        entries = cancelled_rows(examples, date(2026, 11, 9), 1)[1]
        assert [
            (item["lesson"].lesson_id, lane) for item, first, last, lane in entries
        ] == [(1, 0), (2, 1), (3, 0)]

        class Button:
            def configure(self, **kwargs):
                self.options = kwargs

        move, restore, delete = Button(), Button(), Button()
        view = SimpleNamespace(
            cancelled_mode=True,
            labels=[],
            items=[{"lesson": SimpleNamespace(lesson_id=1), "paid": False}],
            buttons={
                "Добавить занятие": delete,
                "Перенести занятие": move,
                "Отменить занятие": restore,
            },
        )
        ScheduleView._select(view, 1)
        assert (
            move.options["state"] == "normal" and restore.options["state"] == "normal"
        )
        assert delete.options["state"] == "normal"
        view.items[0]["paid"] = True
        ScheduleView._select(view, 1)
        assert delete.options["state"] == "disabled"
        ScheduleView._select(view, None)
        assert restore.options["state"] == "disabled"
    finally:
        db.close()

print(
    (
        "PASS: cancel/restore with preserved price/payments/topics; read-only "
        "cancelled week including boundaries; occupied-slot rollback, past/future "
        "status, auth guards; overlapping lanes, selection state and exact 33x30 "
        "legend asset"
    )
)
