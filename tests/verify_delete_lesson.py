"""Удаление отменённых на отдельной базе."""

import ast
import importlib.util
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

sys.dont_write_bytecode = True
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from database import DatabaseManager
from student_service import StudentService
from billing_service import BillingService

spec = importlib.util.spec_from_file_location("delete_gui", (PROJECT / "main.py"))
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
    db.db_path = Path(folder) / "delete.db"
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
        gui.LessonService._now = lambda self: datetime(2026, 11, 5, 12)
        service = gui.LessonService(db)
        lessons = [
            service.schedule(1, datetime(2026, 11, day, 10), 90)
            for day in range(10, 14)
        ]
        for lesson in lessons:
            service.set_topics(lesson.lesson_id, ["Тема " + str(lesson.lesson_id)])
        paid, unpaid, active, late_payment = lessons
        for lesson in [paid, unpaid, late_payment]:
            service.cancel(lesson.lesson_id)
        with db.connection:
            db.connection.execute(
                (
                    "INSERT INTO payments (student_id, lesson_id, paid_at, "
                    "amount_kopecks) VALUES (1, ?, '2026-11-03 12:00:00', 210000)"
                ),
                [paid.lesson_id],
            )
        app = gui.ApplicationController.__new__(gui.ApplicationController)
        app.db = db
        app.root = None
        app.authenticator = SimpleNamespace(current_user_id=1)
        refreshes, confirmations, messages = [], [], []

        def refresh():
            refreshes.append(1)
            app.schedule_view.selected_lesson_id = None

        app.schedule_view = SimpleNamespace(
            cancelled_mode=True, selected_lesson_id=unpaid.lesson_id, refresh=refresh
        )
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
        app.add_or_delete_lesson()
        assert snapshot() == before and not refreshes
        assert "11.11.2026 10:00" in confirmations[-1][1]
        assert "Восстановить запись" in confirmations[-1][1]
        answer = True
        for lesson_id in [paid.lesson_id, active.lesson_id, 999]:
            before = snapshot()
            count = len(confirmations)
            app.schedule_view.selected_lesson_id = lesson_id
            app.delete_lesson()
            assert snapshot() == before and messages[-1][0] == "error"
            assert len(confirmations) == count and not refreshes
        for authorized, mode, selected in [
            (None, True, unpaid.lesson_id),
            (1, False, unpaid.lesson_id),
            (1, True, None),
        ]:
            app.authenticator.current_user_id = authorized
            app.schedule_view.cancelled_mode = mode
            app.schedule_view.selected_lesson_id = selected
            before = snapshot()
            count = len(confirmations)
            app.delete_lesson()
            assert snapshot() == before and len(confirmations) == count
        app.authenticator.current_user_id = 1
        app.schedule_view.cancelled_mode = True
        app.schedule_view.selected_lesson_id = unpaid.lesson_id
        # Ошибка удаления родительской строки откатывает удаление её тем.
        with db.connection:
            db.connection.execute(
                (
                    "CREATE TRIGGER stop_delete BEFORE DELETE ON lessons WHEN "
                    "OLD.lesson_id = 2 BEGIN SELECT RAISE(ABORT, 'test rollback'); "
                    "END;"
                )
            )
        before = snapshot()
        app.delete_lesson()
        assert (
            snapshot() == before and not db.connection.in_transaction and not refreshes
        )
        with db.connection:
            db.connection.execute("DROP TRIGGER stop_delete")
        # Чужую незавершённую транзакцию обработчик не сохраняет и не откатывает.
        db.connection.execute("UPDATE students SET phone = '123' WHERE student_id = 1")
        before = snapshot()
        app.delete_lesson()
        assert snapshot() == before and db.connection.in_transaction and not refreshes
        db.connection.rollback()
        payments = db.connection.execute("SELECT * FROM payments").fetchall()
        other_lessons = db.connection.execute(
            "SELECT * FROM lessons WHERE lesson_id != 2"
        ).fetchall()
        other_topics = db.connection.execute(
            "SELECT * FROM lesson_topics WHERE lesson_id != 2"
        ).fetchall()
        balance = BillingService(db).get_summary(1)
        app.add_or_delete_lesson()
        assert gui.LessonRepository(db).get_by_id(unpaid.lesson_id) is None
        assert (
            db.connection.execute(
                "SELECT * FROM lesson_topics WHERE lesson_id = 2"
            ).fetchall()
            == []
        )
        assert db.connection.execute("SELECT * FROM payments").fetchall() == payments
        assert (
            db.connection.execute("SELECT * FROM lessons").fetchall() == other_lessons
        )
        assert (
            db.connection.execute("SELECT * FROM lesson_topics").fetchall()
            == other_topics
        )
        assert BillingService(db).get_summary(1) == balance
        assert refreshes == [1] and app.schedule_view.selected_lesson_id is None
        assert app.schedule_view.cancelled_mode and messages[-1][0] == "info"

        # Оплата, поступившая после показа подтверждения, тоже блокирует удаление.
        def confirm_with_payment(*args, **kwargs):
            with db.connection:
                db.connection.execute(
                    (
                        "INSERT INTO payments (student_id, lesson_id, paid_at, "
                        "amount_kopecks) VALUES (1, ?, '2026-11-05 12:00:00', 210000)"
                    ),
                    [late_payment.lesson_id],
                )
            return True

        gui.messagebox.askyesno = confirm_with_payment
        app.schedule_view.selected_lesson_id = late_payment.lesson_id
        app.delete_lesson()
        assert gui.LessonRepository(db).get_by_id(late_payment.lesson_id).topics
        assert (
            gui.PaymentRepository(db).get_by_lesson(late_payment.lesson_id) is not None
        )
        assert messages[-1][0] == "error" and refreshes == [1]
        opened = []
        app.schedule_view.cancelled_mode = False
        app.open_lesson_form = lambda: opened.append(1)
        app.add_or_delete_lesson()
        assert opened == [1]
    finally:
        db.close()

print(
    (
        "PASS: deletion requires confirmation/cancelled/unpaid/auth; removes own "
        "topics atomically; preserves other history/payments/balance; late-payment "
        "protection, rollback and pending transaction guard; normal Add still routes "
        "correctly"
    )
)
