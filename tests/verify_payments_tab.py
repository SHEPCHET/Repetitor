"""История платежей, баланс и переходы на отдельной базе."""

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
from enrollment_repository import EnrollmentRepository
from lesson_service import LessonService
from payment_history import PaymentHistory
from payments_view import PaymentsView, money_text
from lessons_view import LessonsView

spec = importlib.util.spec_from_file_location("payments_gui", (PROJECT / "main.py"))
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
assert [money_text(n) for n in [0, 1, 100, 140001, -1]] == [
    "0,00",
    "0,01",
    "1,00",
    "1400,01",
    "-0,01",
]

with tempfile.TemporaryDirectory() as folder:
    db = DatabaseManager()
    db.db_path = Path(folder) / "payments.db"
    connection = sqlite3.connect(db.db_path)
    connection.executescript(schema)
    connection.close()
    try:
        student_service = StudentService(db)
        for name, price, archived in [
            ("Петров Павел", "1000", False),
            ("Петров Пётр", "1400,01", False),
            ("Архивный ученик", "500", True),
            ("Без занятий", None, False),
            ("Только будущие", "1400,01", False),
        ]:
            directions = (
                []
                if price is None
                else [
                    dict(subject_name="Математика", preparation_goal="ЕГЭ", price=price)
                ]
            )
            student_service.add(
                dict(
                    student=dict(
                        full_name=name,
                        phone="",
                        messenger_type="",
                        messenger_contact="",
                        is_archived=archived,
                    ),
                    parents=[],
                    enrollments=directions,
                )
            )
        enrollment_ids = {}
        for student_id in [1, 2, 3, 5]:
            enrollment_ids[student_id] = (
                EnrollmentRepository(db).get_by_student(student_id)[0].enrollment_id
            )
        LessonService._now = lambda self: datetime(2026, 11, 5, 12)
        lessons = LessonService(db)
        past = lessons.schedule(enrollment_ids[1], datetime(2026, 11, 1, 10), 60)
        future = lessons.schedule(enrollment_ids[1], datetime(2026, 11, 10, 10), 60)
        debt = lessons.schedule(enrollment_ids[2], datetime(2026, 11, 2, 10), 60)
        lessons.schedule(enrollment_ids[2], datetime(2026, 11, 11, 10), 60)
        archived = lessons.schedule(enrollment_ids[3], datetime(2026, 10, 30, 10), 60)
        cancelled = lessons.schedule(enrollment_ids[3], datetime(2026, 11, 12, 10), 180)
        lessons.cancel(cancelled.lesson_id)
        only_future = lessons.schedule(
            enrollment_ids[5], datetime(2026, 11, 13, 10), 60
        )
        with db.connection:
            db.connection.executemany(
                (
                    "INSERT INTO payments (student_id, lesson_id, paid_at, "
                    "amount_kopecks) VALUES (?, ?, ?, ?)"
                ),
                [
                    (3, cancelled.lesson_id, "2026-11-02 23:00:00", 150000),
                    (1, future.lesson_id, "2026-11-03 12:00:00", 100000),
                    (5, only_future.lesson_id, "2026-11-03 12:00:00", 140001),
                ],
            )
            db.connection.execute(
                (
                    "UPDATE enrollments SET price_60_kopecks = 299900 WHERE "
                    "enrollment_id = ?"
                ),
                [enrollment_ids[5]],
            )
        data = PaymentHistory(db)

        def snapshot():
            return tuple(db.connection.iterdump())

        before = snapshot()
        history = data.get_history()
        assert [x["payment"].payment_id for x in history] == [3, 2, 1]
        assert history[0]["payment"].amount_kopecks == 140001
        assert history[0]["lesson"].starts_at == datetime(2026, 11, 13, 10)
        assert history[0]["payment"].paid_at == datetime(2026, 11, 3, 12)
        assert (
            history[-1]["student"].is_archived
            and history[-1]["lesson"].status == "Отменено"
        )
        assert history[0]["subject"] == "Математика" and history[0]["goal"] == "ЕГЭ"
        assert [x["student"].student_id for x in data.get_history("ПЕТРОВ")] == [1]
        assert [x["student"].student_id for x in data.get_history("00003")] == [3]
        assert data.get_history("9999") == []
        balances = {x["student"].student_id: x["summary"] for x in data.get_balances()}
        assert len(balances) == 5
        assert balances[1] == dict(
            charged=100000, received=100000, balance=0, debt=0, advance=0
        )
        assert balances[2]["debt"] == 140001 and balances[2]["advance"] == 0
        assert balances[3]["charged"] == 50000 and balances[3]["received"] == 150000
        assert balances[3]["debt"] == 0 and balances[3]["advance"] == 100000
        assert balances[4] == dict(charged=0, received=0, balance=0, debt=0, advance=0)
        assert balances[5]["advance"] == 140001
        assert len(data.get_balances("ПЕТРОВ")) == 2
        assert data.get_balances("00002")[0]["student"].student_id == 2
        assert data.get_balances("999") == [] and snapshot() == before
        app = gui.ApplicationController.__new__(gui.ApplicationController)
        app.db, app.root = db, None
        app.authenticator = SimpleNamespace(current_user_id=None)
        messages, schedule_updates, journal_updates, opened, pages = [], [], [], [], []
        app.schedule_view = SimpleNamespace(refresh=lambda: schedule_updates.append(1))
        allow_open = True

        def open_student(*args):
            opened.append(args)
            return allow_open

        app.lessons_view = SimpleNamespace(
            refresh=lambda: journal_updates.append(1), open_student=open_student
        )
        app.main_window = SimpleNamespace(show_page=pages.append)
        gui.messagebox.showerror = lambda *args, **kwargs: messages.append(args)
        assert app.load_payments() == []
        app.show_student_journal(1)
        assert not opened and snapshot() == before
        app.authenticator.current_user_id = 1
        assert (
            len(app.load_payments()) == 3
            and len(app.load_payments(balance_mode=True)) == 5
        )
        assert snapshot() == before
        for student_id, expected in [
            (1, (1, False, False)),
            (3, (3, True, False)),
            (5, (5, False, True)),
            (4, (4, False, False)),
        ]:
            app.show_student_journal(student_id)
            assert opened[-1] == expected and pages[-1] == "Занятия"
        count = len(pages)
        allow_open = False
        app.show_student_journal(1)
        assert len(pages) == count
        app.show_student_journal(999)
        assert len(pages) == count and messages
        # Окончившийся урок попадает в начисления до показа баланса.
        expired = lessons.schedule(enrollment_ids[2], datetime(2026, 11, 4, 10), 30)
        with db.connection:
            db.connection.execute(
                "UPDATE lessons SET status = 'Запланировано' WHERE lesson_id = ?",
                [expired.lesson_id],
            )
        balances = {
            x["student"].student_id: x["summary"]
            for x in app.load_payments(balance_mode=True)
        }
        assert (
            balances[2]["debt"] == 210002
            and schedule_updates == [1]
            and journal_updates == [1]
        )
        db.connection.execute("UPDATE students SET phone = '123' WHERE student_id = 1")
        before = snapshot()
        assert (
            app.load_payments() is None
            and db.connection.in_transaction
            and snapshot() == before
        )
        db.connection.rollback()
    finally:
        db.close()


class Button:
    def configure(self, **kwargs):
        self.options = kwargs


class View:
    _key = PaymentsView._key
    select_row = PaymentsView.select_row
    show_selected = PaymentsView.show_selected
    toggle_mode = PaymentsView.toggle_mode
    refresh = PaymentsView.refresh

    def __init__(self):
        self.balance_mode, self.selected_id = False, None
        self.query = SimpleNamespace(get=lambda: "Петров")
        self.items = []
        self.row_widgets = {}
        self.main_button = Button()
        self.search_resets, self.visited, self.loaded = [], [], []
        self.show_student = self.visited.append
        self.canvas = SimpleNamespace(yview_moveto=self.search_resets.append)
        self.load_items = self.load

    def load(self, query, balance_mode):
        self.loaded.append((query, balance_mode))
        if balance_mode:
            return [{"student": SimpleNamespace(student_id=42)}]
        return [
            {
                "payment": SimpleNamespace(payment_id=99),
                "student": SimpleNamespace(student_id=42),
            }
        ]

    def _render(self):
        self.select_row(self.selected_id)

    def _hint(self):
        pass


view = View()
view.refresh()
assert view._key(view.items[0]) == 99
PaymentsView.main_action(view)
assert view.balance_mode and view.main_button.options["state"] == "disabled"
assert view.loaded[-1] == ("Петров", True)
PaymentsView.open_row(view, 42)
assert view.visited == [42] and view.main_button.options["state"] == "normal"
PaymentsView._search_changed(view)
assert view.selected_id is None and view.main_button.options["state"] == "disabled"
view.toggle_mode()
assert not view.balance_mode and view._key(view.items[0]) == 99
view.toggle_mode()
view.load_items = lambda *args: None
view.refresh()
assert view.items == [] and view.main_button.options["state"] == "disabled"


class Journal:
    def __init__(self):
        self.query = SimpleNamespace(set=lambda value: None)
        self.canvas = SimpleNamespace(yview_moveto=lambda value: None)

    def leave_editing(self):
        return True

    def refresh(self):
        pass


journal = Journal()
assert LessonsView.open_student(journal, 42, True, True)
assert (
    journal.student_id,
    journal.archived,
    journal.planned,
    journal.group_students,
) == (42, True, True, True)
print(
    (
        "PASS: receipt chronology/search/archive/cancelled history; exact "
        "debt/advance/prepayments/zero balances and saved tariff; read-only data, "
        "auth/auto-status/transaction guards; exact student links incl "
        "future-only/archived, decline navigation and UI mode/selection/search states"
    )
)
