"""Формирование, предпросмотр и сохранение отчёта."""

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
from lesson_service import LessonService
from report_generator import ReportGenerator
from reports_view import ReportsView, student_label, balance_text

spec = importlib.util.spec_from_file_location("reports_gui", (PROJECT / "main.py"))
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
    db.db_path = Path(folder) / "reports_test.db"
    con = sqlite3.connect(db.db_path)
    con.executescript(schema)
    con.close()
    try:
        service = StudentService(db)
        for name, archived in [
            ("Тестовый ученик", True),
            ("Тестовый другой", False),
            ("Без записей", False),
        ]:
            service.add(
                dict(
                    student=dict(
                        full_name=name,
                        phone="",
                        messenger_type="",
                        messenger_contact="",
                        is_archived=archived,
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
        LessonService._now = lambda self: datetime(2026, 11, 5, 12)
        lessons = LessonService(db)
        lesson = lessons.schedule(1, datetime(2026, 11, 2, 10), 60)
        future = lessons.schedule(1, datetime(2026, 12, 1, 10), 60)
        lessons.set_topics(lesson.lesson_id, ["Дроби", "Уравнения"])
        with db.connection:
            db.connection.execute(
                (
                    "INSERT INTO payments (student_id, lesson_id, paid_at, "
                    "amount_kopecks) VALUES (1, ?, '2026-11-03 23:59:59', 140001)"
                ),
                [future.lesson_id],
            )
            db.connection.execute(
                (
                    "UPDATE enrollments SET price_60_kopecks = 299900 WHERE "
                    "enrollment_id = 1"
                )
            )
        app = gui.ApplicationController.__new__(gui.ApplicationController)
        app.db, app.root = db, None
        app.authenticator = SimpleNamespace(current_user_id=None)
        messages, refreshes = [], []
        app.schedule_view = SimpleNamespace(
            refresh=lambda: refreshes.append("schedule")
        )
        app.lessons_view = SimpleNamespace(refresh=lambda: refreshes.append("journal"))
        app.payments_view = SimpleNamespace(
            refresh=lambda: refreshes.append("payments")
        )
        gui.messagebox.showerror = lambda *args, **kwargs: messages.append(
            ("error", args)
        )
        gui.messagebox.showinfo = lambda *args, **kwargs: messages.append(
            ("info", args)
        )
        assert app.load_report_students() == []
        assert app.generate_report("1", "01.11.2026", "30.11.2026") is None
        assert not app.save_generated_report("text", "report.txt")
        app.authenticator.current_user_id = 1
        students = app.load_report_students()
        assert len(students) == 3 and any(s.is_archived for s in students)

        def snapshot():
            return tuple(db.connection.iterdump())

        before = snapshot()
        for query, first, last in [
            ("", "01.11.2026", "30.11.2026"),
            ("ТЕСТОВЫЙ", "01.11.2026", "30.11.2026"),
            ("999", "01.11.2026", "30.11.2026"),
            ("1", "31.02.2026", "30.11.2026"),
            ("1", "01.12.2026", "30.11.2026"),
            ("1", "", "30.11.2026"),
        ]:
            assert app.generate_report(query, first, last) is None
            assert snapshot() == before
        result = app.generate_report("00001", "01.11.2026", "30.11.2026")
        data = result["data"]
        assert data["charged"] == data["received"] == 140001 and data["closing"] == 0
        assert len(data["lessons"]) == 1 and data["student"].is_archived
        assert result["text"] == ReportGenerator(db).make_text(data)
        assert snapshot() == before and not refreshes
        # Предпросмотр показывает те же суммы/темы и платежи, что и TXT.
        rendered_text, tables = [], []
        preview = SimpleNamespace(
            _text=lambda text, *args: rendered_text.append(text),
            _table=lambda *args: tables.append(args),
            _resize=lambda: None,
        )
        ReportsView._render(preview, data)
        assert tables[0][1][0][4] == "Дроби; Уравнения"
        assert tables[0][1][0][5] == "1400,01 ₽"
        assert tables[1][1][0][1] == "23:59:59"
        assert "Баланс на конец периода: 0,00 ₽" in rendered_text
        # Сохраняется именно показанная версия отчёта.
        lessons.set_topics(lesson.lesson_id, ["Новая тема"])
        saved_dialogs = []

        def cancelled_dialog(**kwargs):
            saved_dialogs.append(kwargs)
            return ""

        gui.filedialog.asksaveasfilename = cancelled_dialog
        assert not app.save_generated_report(result["text"], "report.txt")
        assert not list((Path(folder) / "reports").iterdir())
        assert saved_dialogs[-1]["confirmoverwrite"]
        output = Path(folder) / "reports" / "Отчёт.txt"
        gui.filedialog.asksaveasfilename = lambda **kwargs: str(output)
        assert app.save_generated_report(result["text"], "report.txt")
        assert output.read_text(encoding="utf-8") == result["text"]
        assert "Дроби; Уравнения" in output.read_text(encoding="utf-8")
        assert (
            "Новая тема" in app.generate_report("1", "01.11.2026", "30.11.2026")["text"]
        )
        gui.filedialog.asksaveasfilename = lambda **kwargs: str(db.db_path)
        before = snapshot()
        assert not app.save_generated_report(result["text"], "report.txt")
        assert snapshot() == before
        gui.filedialog.asksaveasfilename = lambda **kwargs: str(
            Path(folder) / "missing" / "report.txt"
        )
        assert not app.save_generated_report(result["text"], "report.txt")
        assert messages[-1][0] == "error"
        empty = app.generate_report("3", "01.11.2026", "30.11.2026")
        assert empty["data"]["lessons"] == [] and empty["data"]["payments"] == []
    finally:
        db.close()


class Widget:
    def __init__(self):
        self.options = {}

    def configure(self, **kwargs):
        self.options.update(kwargs)

    def place(self, **kwargs):
        pass

    def place_forget(self):
        pass

    def lift(self):
        pass

    def winfo_children(self):
        return []


class View:
    _clear_report = ReportsView._clear_report

    def __init__(self):
        self.report = None
        self.shown_students = [
            SimpleNamespace(student_id=1, full_name="Тестовый ученик", is_archived=True)
        ]
        self.students = list(self.shown_students)
        self.student_combo = SimpleNamespace(
            current=lambda: 0, configure=lambda **kwargs: None
        )
        self.query = SimpleNamespace(get=lambda: student_label(self.students[0]))
        self.date_from = SimpleNamespace(get=lambda: "01.11.2026")
        self.date_to = SimpleNamespace(get=lambda: "30.11.2026")
        self.body, self.empty, self.save_button, self.scroll_hint, self.status = [
            Widget() for n in range(5)
        ]
        self.canvas = SimpleNamespace(
            yview_moveto=lambda value: None, xview_moveto=lambda value: None
        )
        self.calls, self.saved = [], []
        self.on_generate = lambda *args: self.calls.append(args) or result
        self.on_save = lambda *args: self.saved.append(args) or True

    def _render(self, data):
        self.rendered = data

    def _student_hint(self):
        pass

    def _filter_students(self):
        pass


view = View()
ReportsView.generate(view)
assert view.calls[-1] == ("1", "01.11.2026", "30.11.2026")
assert view.save_button.options["state"] == "normal"
ReportsView.save(view)
assert view.saved[-1][0] == result["text"]
assert view.saved[-1][1] == "report_1_20261101_20261130.txt"
ReportsView._parameters_changed(view)
assert view.report is None and view.save_button.options["state"] == "disabled"
before = len(view.saved)
ReportsView.save(view)
assert len(view.saved) == before
view.on_generate = lambda *args: None
ReportsView.generate(view)
assert view.report is None and view.save_button.options["state"] == "disabled"
assert balance_text(1) == "Долг: 0,01 ₽" and balance_text(-1) == "Переплата: 0,01 ₽"
print(
    (
        "PASS: archive/ID/FIO selection, ambiguity/date/auth guards, matching "
        "preview/TXT and saved price, frozen snapshot, cancel/save "
        "UTF-8/errors/extension safety, empty states and parameter invalidation "
        "preventing stale export"
    )
)
