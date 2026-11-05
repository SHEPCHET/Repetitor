"""Журнал и темы на отдельной базе."""

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
from journal_service import JournalService
from lesson_service import LessonService
from lesson_repository import LessonRepository
from lessons_view import LessonsView, topics_from_text
from main_window import MainWindow

spec = importlib.util.spec_from_file_location("journal_gui", (PROJECT / "main.py"))
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

assert topics_from_text("  Дроби \n\n Уравнения\r\n  ") == ["Дроби", "Уравнения"]
with tempfile.TemporaryDirectory() as folder:
    db = DatabaseManager()
    db.db_path = Path(folder) / "journal.db"
    connection = sqlite3.connect(db.db_path)
    connection.executescript(schema)
    connection.close()
    try:
        students = StudentService(db)
        for name, archived in [
            ("Иванов Иван", False),
            ("Иванов Игорь", False),
            ("Архивный ученик", True),
        ]:
            students.add(
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
        a = lessons.schedule(1, datetime(2026, 11, 1, 10), 90)
        b = lessons.schedule(1, datetime(2026, 11, 2, 10), 60)
        c = lessons.schedule(2, datetime(2026, 11, 3, 10), 60)
        future = lessons.schedule(1, datetime(2026, 11, 10, 10), 60)
        future2 = lessons.schedule(2, datetime(2026, 11, 11, 10), 60)
        archive = lessons.schedule(3, datetime(2026, 10, 30, 10), 60)
        archive_future = lessons.schedule(3, datetime(2026, 11, 12, 10), 60)
        cancelled = lessons.schedule(1, datetime(2026, 11, 13, 10), 60)
        lessons.cancel(cancelled.lesson_id)
        expired = lessons.schedule(1, datetime(2026, 11, 4, 10), 60)
        lessons.set_topics(a.lesson_id, ["Старая тема"])
        with db.connection:
            db.connection.execute(
                "UPDATE lessons SET status = 'Запланировано' WHERE lesson_id = ?",
                [expired.lesson_id],
            )
            db.connection.execute(
                (
                    "INSERT INTO payments (student_id, lesson_id, paid_at, "
                    "amount_kopecks) VALUES (1, ?, '2026-11-01 12:00:00', ?)"
                ),
                [a.lesson_id, a.price_kopecks],
            )
        journal = JournalService(db)

        def snapshot():
            return tuple(db.connection.iterdump())

        before = snapshot()
        items = journal.get_items()
        assert [x["lesson"].lesson_id for x in items] == [
            c.lesson_id,
            b.lesson_id,
            a.lesson_id,
        ]
        assert [x["lesson"].lesson_id for x in journal.get_items("00001")] == [
            b.lesson_id,
            a.lesson_id,
        ]
        assert len(journal.get_items("ИВАНОВ")) == 3
        assert journal.get_items("9999") == []
        assert [x["lesson"].lesson_id for x in journal.get_items(archived=True)] == [
            archive.lesson_id
        ]
        assert [x["lesson"].lesson_id for x in journal.get_items(planned=True)][:2] == [
            expired.lesson_id,
            future.lesson_id,
        ]
        assert [
            x["lesson"].lesson_id
            for x in journal.get_items(planned=True, archived=True)
        ] == [archive_future.lesson_id]
        assert (
            items[-1]["paid"]
            and items[-1]["subject"] == "Математика"
            and items[-1]["goal"] == "ЕГЭ"
        )
        assert snapshot() == before
        changes = {
            a.lesson_id: dict(original=["Старая тема"], topics=["Дроби", "Уравнения"]),
            b.lesson_id: dict(original=[], topics=["Графики"]),
        }
        receipts = db.connection.execute("SELECT * FROM payments").fetchall()
        lesson_rows = db.connection.execute("SELECT * FROM lessons").fetchall()
        with db.connection:
            db.connection.execute(
                (
                    "CREATE TRIGGER stop_topic BEFORE INSERT ON lesson_topics WHEN "
                    "NEW.lesson_id = 2 BEGIN SELECT RAISE(ABORT, 'batch rollback'); "
                    "END;"
                )
            )
        before = snapshot()
        try:
            journal.save_topics(changes)
            raise AssertionError("Topic trigger should fail")
        except sqlite3.Error:
            pass
        assert snapshot() == before and not db.connection.in_transaction
        with db.connection:
            db.connection.execute("DROP TRIGGER stop_topic")
        journal.save_topics(changes)
        assert LessonRepository(db).get_by_id(a.lesson_id).topics == [
            "Дроби",
            "Уравнения",
        ]
        assert LessonRepository(db).get_by_id(b.lesson_id).topics == ["Графики"]
        assert db.connection.execute("SELECT * FROM payments").fetchall() == receipts
        assert db.connection.execute("SELECT * FROM lessons").fetchall() == lesson_rows
        for bad in [
            changes,
            {future.lesson_id: dict(original=[], topics=["Рано"])},
            {cancelled.lesson_id: dict(original=[], topics=["Отмена"])},
            {999: dict(original=[], topics=["Нет урока"])},
            {b.lesson_id: dict(original=["Графики"], topics=[""])},
        ]:
            before = snapshot()
            try:
                journal.save_topics(bad)
                raise AssertionError("Invalid/stale topic update accepted")
            except ValueError:
                pass
            assert snapshot() == before and not db.connection.in_transaction
        journal.save_topics({b.lesson_id: dict(original=["Графики"], topics=[])})
        assert LessonRepository(db).get_by_id(b.lesson_id).topics == []
        app = gui.ApplicationController.__new__(gui.ApplicationController)
        app.db, app.root = db, None
        app.authenticator = SimpleNamespace(current_user_id=None)
        messages, refreshed, opened, pages = [], [], [], []
        gui.messagebox.showerror = lambda *args, **kwargs: messages.append(
            ("error", args)
        )
        gui.messagebox.showinfo = lambda *args, **kwargs: messages.append(
            ("info", args)
        )
        app.schedule_view = SimpleNamespace(refresh=lambda: refreshed.append(1))
        app.lessons_view = SimpleNamespace(
            show_lesson=lambda *args: opened.append(args) or True,
            leave_editing=lambda: False,
        )
        app.main_window = SimpleNamespace(show_page=pages.append)
        before = snapshot()
        assert app.load_journal() == [] and not app.save_journal_topics({})
        app.show_lesson_in_journal(future.lesson_id)
        assert snapshot() == before and not pages
        app.authenticator.current_user_id = 1
        loaded = app.load_journal()
        assert loaded[0]["lesson"].lesson_id == expired.lesson_id and refreshed == [1]
        assert db.connection.execute("SELECT * FROM payments").fetchall() == receipts
        before = snapshot()
        app.load_journal()
        assert snapshot() == before and refreshed == [1]
        for lesson, planned, archived in [
            (a, False, False),
            (future, True, False),
            (archive, False, True),
            (archive_future, True, True),
        ]:
            app.show_lesson_in_journal(lesson.lesson_id)
            assert opened[-1] == (
                lesson.lesson_id,
                3 if archived else 1,
                planned,
                archived,
            )
            assert pages[-1] == "Занятия"
        count = len(pages)
        app.show_lesson_in_journal(cancelled.lesson_id)
        assert len(pages) == count and messages[-1][0] == "error"
        assert not app.before_page_change("Ученики") and app.before_page_change(
            "Занятия"
        )
        # Незавершённая чужая транзакция не теряется.
        db.connection.execute("UPDATE students SET phone = '123' WHERE student_id = 1")
        before = snapshot()
        count = len(messages)
        assert app.load_journal(silent=True) is None
        assert (
            snapshot() == before
            and db.connection.in_transaction
            and len(messages) == count
        )
        db.connection.rollback()
    finally:
        db.close()


# Редактирование не пишет до Save; отказ выйти и ошибка Save сохраняют черновик.
class Text:
    def __init__(self, text):
        self.text = text

    def get(self, *args):
        return self.text

    def configure(self, **kwargs):
        self.options = kwargs


class View:
    changes = LessonsView.changes
    leave_editing = LessonsView.leave_editing

    def __init__(self):
        self.editing = True
        self.editors = {1: Text(" Дроби\nУравнения\n")}
        self.original = {1: ["Старая тема"]}
        self.reloads = 0
        self.saved = []
        self.on_save = lambda data: self.saved.append(data) or False

    def refresh(self, **kwargs):
        self.reloads += 1


import lessons_view

view = View()
lessons_view.messagebox.askyesno = lambda *args, **kwargs: False
assert not view.leave_editing() and view.editing and view.editors
LessonsView.save(view)
assert view.editing and view.editors and view.reloads == 0
view.on_save = lambda data: view.saved.append(data) or True
LessonsView.save(view)
assert not view.editing and view.saved[-1][1]["topics"] == ["Дроби", "Уравнения"]
view = View()
LessonsView.cancel_edit(view)
assert not view.editing and not view.saved
view = View()
lessons_view.messagebox.askyesno = lambda *args, **kwargs: True
assert view.leave_editing() and not view.editors and not view.editing
view = SimpleNamespace(highlighted_id=1, pending_id=1, row_widgets={1: [Text("")]})
LessonsView._any_click(view)
assert view.highlighted_id is None and view.pending_id is None
assert view.row_widgets[1][0].options["bg"] == "#ededed"


class Query:
    def __init__(self, owner):
        self.owner, self.value = owner, "старый поиск"

    def get(self):
        return self.value

    def set(self, value):
        self.value = value
        LessonsView._search_changed(self.owner)


class Modes:
    toggle_group = LessonsView.toggle_group

    def __init__(self):
        self.editing = False
        self.planned, self.archived, self.group_students = False, False, False
        self.student_id, self.selected_id = None, 22
        self.pending_id, self.highlighted_id = None, None
        self.items = [
            dict(
                lesson=SimpleNamespace(lesson_id=22),
                student=SimpleNamespace(student_id=2),
            )
        ]
        self.query = Query(self)
        self.calls = []

    def leave_editing(self):
        return not self.editing

    def _hint(self):
        pass

    def refresh(self, **kwargs):
        self.calls.append(
            (
                self.student_id,
                self.planned,
                self.archived,
                self.group_students,
                self.query.get(),
            )
        )


mode = Modes()
mode.toggle_group()
assert mode.group_students and mode.student_id == 2
mode.toggle_group()
assert not mode.group_students and mode.student_id is None and mode.query.get() == ""
LessonsView.show_lesson(mode, 10, 3, True, True)
assert mode.calls[-1] == (3, True, True, True, "")
assert mode.pending_id == 10 and mode.highlighted_id == 10
mode.editing = True
before = list(mode.calls)
assert not LessonsView.show_lesson(mode, 11, 1, False, False)
assert mode.calls == before
mode.editing = False
LessonsView.toggle_archive(mode)
assert not mode.archived and not mode.planned and mode.student_id is None
LessonsView.toggle_period(mode)
assert mode.planned


class Page:
    def __init__(self):
        self.shown, self.hidden = 0, 0

    def pack(self, **kwargs):
        self.shown += 1

    def pack_forget(self):
        self.hidden += 1

    def configure(self, **kwargs):
        pass


nav = SimpleNamespace(
    current_page="Занятия",
    before_change=lambda page: False,
    pages={"Занятия": Page(), "Ученики": Page()},
    buttons={"Занятия": Page(), "Ученики": Page()},
)
assert MainWindow.show_page(nav, "Ученики") is False
assert nav.current_page == "Занятия" and nav.pages["Занятия"].hidden == 0
nav.before_change = lambda page: True
assert MainWindow.show_page(nav, "Ученики") is True
assert nav.current_page == "Ученики" and nav.pages["Ученики"].shown == 1

loads = []
tick = SimpleNamespace(
    editing=True,
    planned=False,
    archived=False,
    query=SimpleNamespace(get=lambda: ""),
    winfo_ismapped=lambda: True,
    _tick=lambda: None,
    load_items=lambda *args: loads.append(args),
    after=lambda *args: "timer",
    refresh=lambda **kwargs: loads.append(kwargs),
)
LessonsView._tick(tick)
assert loads == [("", False, False, True)] and tick.timer == "timer"
tick.editing = False
LessonsView._tick(tick)
assert loads[-1] == {"silent": True}
print(
    (
        "PASS: all journal modes, case/ID search, ordering, archive/plans, topic "
        "parsing and atomic rollback/stale checks, financial preservation, "
        "auto-completion, exact deep links/auth/navigation guards and draft "
        "save/cancel/highlight lifecycle"
    )
)
