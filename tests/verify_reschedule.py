"""Проверка переноса на отдельной базе."""

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
from schedule_view import ScheduleView
from lesson_form import LessonForm

spec = importlib.util.spec_from_file_location("reschedule_gui", (PROJECT / "main.py"))
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


class Form:
    def __init__(self, *args):
        self.args = args
        self.destroyed = False

    def destroy(self):
        self.destroyed = True

    def lift(self):
        pass


class Value:
    def set(self, value):
        self.value = value


class Button:
    def configure(self, **kwargs):
        self.options = kwargs


with tempfile.TemporaryDirectory() as folder:
    db = DatabaseManager()
    db.db_path = Path(folder) / "reschedule.db"
    connection = sqlite3.connect(db.db_path)
    connection.executescript(schema)
    connection.close()
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
                dict(subject_name="Математика", preparation_goal="ЕГЭ", price="1400")
            ],
        )
    )
    gui.LessonService._now = lambda self: datetime(2026, 11, 5, 12)
    lesson_service = gui.LessonService(db)
    first = lesson_service.schedule(1, datetime(2026, 11, 10, 10), 90)
    second = lesson_service.schedule(1, datetime(2026, 11, 11, 10), 90)
    canceled = lesson_service.schedule(1, datetime(2026, 11, 12, 10), 60)
    lesson_service.cancel(canceled.lesson_id)
    with db.connection:
        db.connection.execute(
            (
                "INSERT INTO payments (student_id, lesson_id, paid_at, "
                "amount_kopecks) VALUES (1, ?, '2026-11-03 12:00:00', 210000)"
            ),
            [first.lesson_id],
        )
        db.connection.execute(
            "INSERT INTO lesson_topics (lesson_id, topic_name) VALUES (?, 'Дроби')",
            [first.lesson_id],
        )
        db.connection.execute(
            "UPDATE enrollments SET price_60_kopecks = 180000 WHERE enrollment_id = 1"
        )
    app = gui.ApplicationController.__new__(gui.ApplicationController)
    app.db = db
    app.root = None
    app.main_window = SimpleNamespace(family="Arial")
    app.authenticator = SimpleNamespace(current_user_id=1)
    focused = []
    app.schedule_view = SimpleNamespace(
        selected_lesson_id=first.lesson_id,
        monday=date(2026, 11, 9),
        cancelled_mode=False,
        half=SimpleNamespace(get=lambda: "1"),
        show_lesson=focused.append,
    )
    app.lesson_form = None
    gui.LessonForm = Form
    messages = []
    gui.messagebox.showerror = lambda *args, **kwargs: messages.append(("error", args))
    gui.messagebox.showinfo = lambda *args, **kwargs: messages.append(("info", args))

    def snapshot():
        return tuple(db.connection.iterdump())

    def rejected(lesson_id, data, cancelled=False):
        before = snapshot()
        app.lesson_form = Form()
        form = app.lesson_form
        app.reschedule_lesson(lesson_id, data, cancelled)
        assert snapshot() == before and app.lesson_form is form and not form.destroyed
        assert messages[-1][0] == "error" and not db.connection.in_transaction

    try:
        before = snapshot()
        app.open_reschedule_form()
        record = app.lesson_form.args[-1]
        assert record["lesson"].lesson_id == first.lesson_id
        assert app.lesson_form.args[2][0].student_id == 1
        app.close_lesson_form()
        assert snapshot() == before
        # Цена в форме соответствует сохранённому занятию, даже после смены тарифа.
        preview = SimpleNamespace(
            record=record,
            directions=[{"enrollment": record["enrollment"]}],
            direction_combo=SimpleNamespace(
                current=lambda: 0, configure=lambda **kwargs: None
            ),
            hours=SimpleNamespace(get=lambda: "1"),
            minutes=SimpleNamespace(get=lambda: "30"),
            price=Value(),
            save_button=Button(),
        )
        LessonForm._preview(preview)
        assert preview.price.value == "2100,00 руб."
        rejected(first.lesson_id, dict(date="11.11.2026", time="10:30"))
        assert "уже назначено" in messages[-1][1][1]
        rejected(first.lesson_id, dict(date="31.02.2026", time="10:00"))
        rejected(first.lesson_id, dict(date="11.11.2026", time="10:15"))
        rejected(canceled.lesson_id, dict(date="12.11.2026", time="12:00"))
        rejected(999, dict(date="12.11.2026", time="12:00"))
        payments = db.connection.execute("SELECT * FROM payments").fetchall()
        topics = db.connection.execute("SELECT * FROM lesson_topics").fetchall()
        # Вплотную к другому уроку разрешено. Другая неделя/половина также работают.
        for day, time in [("11.11.2026", "11:30"), ("17.11.2026", "16:00")]:
            app.lesson_form = Form()
            app.reschedule_lesson(
                first.lesson_id, dict(date=day, time=time, hours="9", minutes="00")
            )
            saved = gui.LessonRepository(db).get_by_id(first.lesson_id)
            assert (saved.ends_at - saved.starts_at).total_seconds() == 90 * 60
            assert saved.price_kopecks == 210000 and saved.status == "Запланировано"
            assert app.lesson_form is None and focused[-1].lesson_id == first.lesson_id
            assert (
                db.connection.execute("SELECT * FROM payments").fetchall() == payments
            )
            assert (
                db.connection.execute("SELECT * FROM lesson_topics").fetchall()
                == topics
            )
        assert saved.starts_at == datetime(2026, 11, 17, 16)
        assert gui.LessonRepository(db).get_by_id(
            second.lesson_id
        ).starts_at == datetime(2026, 11, 11, 10)

        # Перенос отменённого меняет время без восстановления и без смены суммы.
        lesson_service.cancel(first.lesson_id)
        app.schedule_view.cancelled_mode = True
        app.schedule_view.selected_lesson_id = first.lesson_id
        app.lesson_form = None
        before = snapshot()
        app.open_reschedule_form()
        assert app.lesson_form.args[-1]["lesson"].status == "Отменено"
        app.close_lesson_form()
        assert snapshot() == before
        payments = db.connection.execute("SELECT * FROM payments").fetchall()
        topics = db.connection.execute("SELECT * FROM lesson_topics").fetchall()
        app.open_reschedule_form()
        callback = app.lesson_form.args[6]
        callback(dict(date="11.11.2026", time="10:00"))
        moved = gui.LessonRepository(db).get_by_id(first.lesson_id)
        assert moved.status == "Отменено" and moved.price_kopecks == 210000
        assert moved.starts_at == datetime(2026, 11, 11, 10)
        assert moved.ends_at == datetime(2026, 11, 11, 11, 30)
        assert app.lesson_form is None and app.schedule_view.cancelled_mode
        assert focused[-1].status == "Отменено"
        assert db.connection.execute("SELECT * FROM payments").fetchall() == payments
        assert db.connection.execute("SELECT * FROM lesson_topics").fetchall() == topics
        # Пока отменено, может совпадать с активным; восстановление конфликтует.
        before = snapshot()
        try:
            lesson_service.restore(first.lesson_id)
            raise AssertionError("Overlapping restoration accepted")
        except ValueError:
            pass
        assert snapshot() == before
        rejected(first.lesson_id, dict(date="31.02.2026", time="10:00"), True)
        rejected(first.lesson_id, dict(date="01.12.2026", time="10:15"), True)
        app.reschedule_lesson(
            first.lesson_id, dict(date="01.12.2026", time="15:00"), True
        )
        moved = gui.LessonRepository(db).get_by_id(first.lesson_id)
        assert moved.starts_at == datetime(2026, 12, 1, 15)
        assert moved.status == "Отменено" and moved.price_kopecks == 210000
        assert (moved.ends_at - moved.starts_at).total_seconds() == 5400
        # Статус проверяется снова при сохранении ранее открытой формы.
        app.open_reschedule_form()
        callback = app.lesson_form.args[6]
        lesson_service.restore(first.lesson_id)
        before = snapshot()
        form = app.lesson_form
        callback(dict(date="02.12.2026", time="15:00"))
        assert snapshot() == before and app.lesson_form is form
        assert messages[-1][0] == "error"
        app.close_lesson_form()
        app.open_reschedule_form()
        assert app.lesson_form is None and messages[-1][0] == "error"

        app.authenticator.current_user_id = None
        before = snapshot()
        app.reschedule_lesson(first.lesson_id, dict(date="18.11.2026", time="16:00"))
        app.reschedule_lesson(
            canceled.lesson_id, dict(date="18.11.2026", time="16:00"), True
        )
        assert snapshot() == before
        # Выбор включает кнопку, смена периода снимает выделение и выключает её.
        button = Button()
        view = SimpleNamespace(
            buttons={
                "Добавить занятие": Button(),
                "Перенести занятие": button,
                "Отменить занятие": button,
            },
            labels=[],
            cancelled_mode=False,
        )
        ScheduleView._select(view, first.lesson_id)
        assert button.options["state"] == "normal"
        ScheduleView._select(view, None)
        assert button.options["state"] == "disabled"
    finally:
        db.close()

print(
    (
        "PASS: normal/cancelled move with same "
        "identity/duration/price/payment/topics; cancelled status persists, conflict "
        "checked on restore; cross-month focus, stale-status/input/auth guards, "
        "cancel without writes and selection states"
    )
)
