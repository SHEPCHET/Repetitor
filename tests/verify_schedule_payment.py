"""Оплата из расписания на отдельной базе."""

import ast
import importlib.util
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

sys.dont_write_bytecode = True
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from database import DatabaseManager
from student_service import StudentService
from billing_service import BillingService
from schedule_view import ScheduleView, lesson_color
import payment_service


class Clock(datetime):
    @classmethod
    def now(cls, tz=None):
        assert tz.utcoffset(None) == timedelta(hours=3)
        return datetime(2026, 11, 5, 12, 34, 56, tzinfo=tz)


payment_service.datetime = Clock
spec = importlib.util.spec_from_file_location("payment_gui", (PROJECT / "main.py"))
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
    db.db_path = Path(folder) / "pay.db"
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
                        subject_name="Математика",
                        preparation_goal="ЕГЭ",
                        price="1400,01",
                    )
                ],
            )
        )
        gui.LessonService._now = lambda self: datetime(2026, 11, 5, 12)
        service = gui.LessonService(db)
        future = service.schedule(1, datetime(2026, 11, 10, 10), 90)
        past = service.schedule(1, datetime(2026, 11, 1, 10), 60)
        cancelled = service.schedule(1, datetime(2026, 11, 11, 10), 60)
        service.cancel(cancelled.lesson_id)
        free = service.schedule(1, datetime(2026, 11, 12, 10), 60)
        changed = service.schedule(1, datetime(2026, 11, 13, 10), 60)
        race = service.schedule(1, datetime(2026, 11, 14, 10), 60)
        with db.connection:
            db.connection.execute(
                "UPDATE lessons SET price_kopecks = 0 WHERE lesson_id = ?",
                [free.lesson_id],
            )
            db.connection.execute(
                (
                    "UPDATE enrollments SET price_60_kopecks = 180000 WHERE "
                    "enrollment_id = 1"
                )
            )
            db.connection.execute(
                "UPDATE students SET is_archived = 1 WHERE student_id = 1"
            )
        app = gui.ApplicationController.__new__(gui.ApplicationController)
        app.db, app.root = db, None
        app.authenticator = SimpleNamespace(current_user_id=1)
        refreshed, selected, confirmations, messages = [], [], [], []
        app.schedule_view = SimpleNamespace(
            refresh=lambda: refreshed.append(1), _select=selected.append
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
        app.pay_lesson(future.lesson_id)
        assert snapshot() == before and not refreshed
        assert (
            "2100,02 руб." in confirmations[-1][1] and "00001" in confirmations[-1][1]
        )
        assert (
            "10.11.2026 10:00" in confirmations[-1][1] and "ЕГЭ" in confirmations[-1][1]
        )
        answer = True
        lessons_before = db.connection.execute("SELECT * FROM lessons").fetchall()
        balance = BillingService(db).get_summary(1)
        app.pay_lesson(future.lesson_id)
        receipt = gui.PaymentRepository(db).get_by_lesson(future.lesson_id)
        assert receipt.amount_kopecks == 210002 and receipt.student_id == 1
        assert receipt.paid_at == datetime(2026, 11, 5, 12, 34, 56)
        assert (
            db.connection.execute("SELECT * FROM lessons").fetchall() == lessons_before
        )
        assert refreshed == [1] and selected == [future.lesson_id]
        after = BillingService(db).get_summary(1)
        assert after["charged"] == balance["charged"] and after["received"] == 210002
        for lesson_id in [future.lesson_id, cancelled.lesson_id, free.lesson_id, 999]:
            before, count = snapshot(), len(confirmations)
            app.pay_lesson(lesson_id)
            assert snapshot() == before and len(confirmations) == count
            assert messages[-1][0] == "error"
        app.authenticator.current_user_id = None
        before = snapshot()
        app.pay_lesson(past.lesson_id)
        assert snapshot() == before
        app.authenticator.current_user_id = 1
        app.pay_lesson(past.lesson_id)
        data = app.load_schedule(past.starts_at.date(), future.starts_at.date())
        colours = {
            item["lesson"].lesson_id: lesson_color(item["lesson"], item["paid"])
            for item in data
        }
        assert (
            colours[past.lesson_id] == "#c7fb72"
            and colours[future.lesson_id] == "#9dfff4"
        )
        # Цена или статус изменились во время подтверждения — платёж не создаётся.
        for status_change in [False, True]:

            def change_during_confirm(*args, **kwargs):
                with db.connection:
                    if status_change:
                        db.connection.execute(
                            (
                                "UPDATE lessons SET status = 'Отменено' WHERE "
                                "lesson_id = ?"
                            ),
                            [changed.lesson_id],
                        )
                    else:
                        db.connection.execute(
                            (
                                "UPDATE lessons SET price_kopecks = price_kopecks + "
                                "100 WHERE lesson_id = ?"
                            ),
                            [changed.lesson_id],
                        )
                return True

            gui.messagebox.askyesno = change_during_confirm
            app.pay_lesson(changed.lesson_id)
            assert gui.PaymentRepository(db).get_by_lesson(changed.lesson_id) is None
            assert messages[-1][0] == "error" and not db.connection.in_transaction

        # Другой обработчик уже записал платёж — второго быть не должно.
        def duplicate_during_confirm(*args, **kwargs):
            gui.PaymentService(db).register_payment(race.lesson_id)
            return True

        gui.messagebox.askyesno = duplicate_during_confirm
        app.pay_lesson(race.lesson_id)
        assert (
            db.connection.execute(
                "SELECT COUNT(*) FROM payments WHERE lesson_id = ?", [race.lesson_id]
            ).fetchone()[0]
            == 1
        )
        assert messages[-1][0] == "error" and not db.connection.in_transaction

        class Menu:
            def __init__(self):
                self.entries = {}

            def entryconfigure(self, index, **kwargs):
                self.entries[index] = kwargs
                if index == 0:
                    self.options = kwargs

            def tk_popup(self, x, y):
                self.position = (x, y)

            def grab_release(self):
                self.released = True

        menu, menu_selections, paid_ids = Menu(), [], []
        record = dict(lesson=future, paid=False)
        view = SimpleNamespace(
            items=[record],
            cancelled_mode=False,
            on_pay=paid_ids.append,
            on_show=None,
            lesson_menu=menu,
            _select=menu_selections.append,
        )
        event = SimpleNamespace(x_root=100, y_root=200)
        assert ScheduleView._show_lesson_menu(view, event, future.lesson_id) == "break"
        assert (
            menu.options["state"] == "normal"
            and menu.released
            and menu.position == (100, 200)
        )
        menu.options["command"]()
        assert paid_ids == [future.lesson_id] and menu_selections == [future.lesson_id]
        shown = []
        view.on_show = shown.append
        ScheduleView._show_lesson_menu(view, event, future.lesson_id)
        assert menu.entries[1]["state"] == "normal"
        menu.entries[1]["command"]()
        assert shown == [future.lesson_id]
        record["paid"] = True
        ScheduleView._show_lesson_menu(view, event, future.lesson_id)
        assert menu.options["state"] == "disabled"
        assert menu.entries[1]["state"] == "normal"
        record["paid"] = False
        view.cancelled_mode = True
        ScheduleView._show_lesson_menu(view, event, future.lesson_id)
        assert menu.options["state"] == "disabled"
        assert menu.entries[1]["state"] == "disabled"
    finally:
        db.close()

print(
    (
        "PASS: confirm/decline, saved cost after tariff edit, exact MSK receipt, "
        "archived/past/future balance and colours; duplicate/cancelled/free/auth "
        "guards; stale cost/status and duplicate race rollback; context menu states "
        "and callbacks"
    )
)
