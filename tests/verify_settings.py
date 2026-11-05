"""Настройки и повторный вход на отдельной базе."""

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
from authenticator import Authenticator
from student_service import StudentService
from settings_view import SettingsView

spec = importlib.util.spec_from_file_location("settings_gui", (PROJECT / "main.py"))
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


class Root:
    def protocol(self, name, callback):
        self.close_callback = callback

    def minsize(self, *args):
        self.minimum = args

    def destroy(self):
        self.destroyed = True


class AuthView:
    def __init__(self, *args):
        self.visible, self.username = True, ""

    def pack(self, **kwargs):
        self.visible = True

    def pack_forget(self):
        self.visible = False

    def show_login(self, username=""):
        self.username = username

    def clear_password(self):
        pass


class Main:
    sessions = []

    def __init__(self, *args):
        self.family = "Arial"
        self.pages = {
            name: object()
            for name in [
                "Расписание",
                "Ученики",
                "Занятия",
                "Оплаты",
                "Отчеты",
                "Настройки",
            ]
        }
        self.destroyed = False
        self.sessions.append(self)

    def pack(self, **kwargs):
        pass

    def destroy(self):
        self.destroyed = True


class BusinessView:
    def __init__(self, *args):
        self.add_button = self.edit_button = self.move_button = self
        self.buttons = {
            name: self
            for name in [
                "Добавить занятие",
                "Перенести занятие",
                "Отменить занятие",
                "К отменённым",
            ]
        }
        self.allow_leave = True
        self.clears = 0
        self.report = None

    def configure(self, **kwargs):
        pass

    def pack(self, **kwargs):
        pass

    def leave_editing(self):
        return self.allow_leave

    def clear_passwords(self):
        self.clears += 1


with tempfile.TemporaryDirectory() as folder:
    db = DatabaseManager()
    db.db_path = Path(folder) / "settings.db"
    con = sqlite3.connect(db.db_path)
    con.executescript(schema)
    con.close()
    try:
        auth = Authenticator(db)
        old, new, second = "СтарыйПароль-123", " НовыйПароль-456 ", "ВторойПароль-789"
        auth.register("Первый репетитор", "first", "first@example.com", old)
        auth.register("Второй репетитор", "second", "second@example.com", second)
        StudentService(db).add(
            dict(
                student=dict(
                    full_name="Ученик",
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
        gui.DatabaseManager = lambda: db
        gui.AuthWindow, gui.MainWindow = AuthView, Main
        gui.StudentsView = gui.ScheduleView = gui.LessonsView = gui.PaymentsView = (
            gui.ReportsView
        ) = gui.SettingsView = BusinessView
        messages = []
        gui.messagebox.showerror = lambda *args, **kwargs: messages.append(
            ("error", args)
        )
        gui.messagebox.showinfo = lambda *args, **kwargs: messages.append(
            ("info", args)
        )
        root = Root()
        app = gui.ApplicationController(root)
        assert app.load_account() is None and app.create_backup() is None
        assert not app.change_account_password(old, new, new)
        app.login("first", old)
        assert not app.view.visible and app.authenticator.current_user_id == 1
        account = app.load_account()
        assert account == dict(
            user_id=1, name="Первый репетитор", login="first", email="first@example.com"
        )

        def snapshot():
            return tuple(db.connection.iterdump())

        def account_and_business():
            result = {}
            tables = [
                row[0]
                for row in db.connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            ]
            for table in tables:
                columns = [
                    row[1]
                    for row in db.connection.execute(
                        'PRAGMA table_info("' + table + '")'
                    )
                    if row[1] != "remember_token_hash"
                ]
                names = ", ".join('"' + column + '"' for column in columns)
                result[table] = db.connection.execute(
                    "SELECT " + names + ' FROM "' + table + '"'
                ).fetchall()
            return result

        for current, password, repeat in [
            ("", new, new),
            (old, new, "другое"),
            (old, "short", "short"),
            ("неверный", new, new),
        ]:
            before = snapshot()
            assert not app.change_account_password(current, password, repeat)
            assert snapshot() == before and app.authenticator.current_user_id == 1
        assert app.change_account_password(old, new, new)
        verifier = Authenticator(db)
        assert not verifier.login("first", old) and verifier.login("first", new)
        stored = db.connection.execute(
            "SELECT password_hash, password_salt FROM users WHERE user_id = 1"
        ).fetchone()
        assert (
            new not in stored
            and old not in stored
            and stored[0].startswith("pbkdf2_sha256$")
        )
        assert app.authenticator.current_user_id == 1
        backup = app.create_backup()
        assert backup.parent == Path(folder) / "backups" and backup.exists()
        copy = sqlite3.connect(backup)
        try:
            assert copy.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert copy.execute("PRAGMA foreign_key_check").fetchall() == []
            assert tuple(copy.iterdump()) == snapshot()
        finally:
            copy.close()
        assert app.create_backup() != backup
        # Ошибка копирования или пароля не изменяет чужую транзакцию.
        db.connection.execute("UPDATE students SET phone = '123' WHERE student_id = 1")
        before = snapshot()
        files = list(backup.parent.iterdir())
        assert app.create_backup() is None
        assert not app.change_account_password(
            new, "ТретийПароль-123", "ТретийПароль-123"
        )
        assert snapshot() == before and db.connection.in_transaction
        assert list(backup.parent.iterdir()) == files
        db.connection.rollback()
        real_backup = db.backup

        def fail_backup():
            raise OSError("Проверочная ошибка записи")

        db.backup = fail_backup
        assert app.create_backup() is None and messages[-1][0] == "error"
        db.backup = real_backup
        # Отказ терять темы оставляет рабочую сессию открытой.
        first_window = app.main_window
        app.lessons_view.allow_leave = False
        assert not app.logout() and app.main_window is first_window
        assert not first_window.destroyed and app.authenticator.current_user_id == 1
        app.lessons_view.allow_leave = True
        settings = app.settings_view
        form = SimpleNamespace(destroyed=False)
        form.destroy = lambda: setattr(form, "destroyed", True)
        app.lesson_form = form
        app.reports_view.report = "Старый предпросмотр"
        data_before = account_and_business()
        assert app.logout()
        assert first_window.destroyed and form.destroyed and settings.clears == 1
        assert (
            app.main_window is None
            and app.lesson_form is None
            and app.authenticator.current_user_id is None
        )
        assert all(
            getattr(app, name) is None
            for name in [
                "students_view",
                "schedule_view",
                "lessons_view",
                "payments_view",
                "reports_view",
                "settings_view",
            ]
        )
        assert (
            app.view.visible and app.view.username == "" and root.minimum == (640, 760)
        )
        assert account_and_business() == data_before
        assert app.saved_login.restore() is None
        assert (
            db.connection.execute(
                "SELECT remember_token_hash FROM users WHERE user_id = 1"
            ).fetchone()[0]
            is None
        )
        assert (
            app.load_report_students() == []
            and app.load_payments() == []
            and app.create_backup() is None
        )
        app.login("first", old)
        assert app.main_window is None and app.view.visible
        app.login("second", second)
        assert app.main_window is not first_window and len(Main.sessions) == 2
        assert app.load_account()["name"] == "Второй репетитор"
        assert app.reports_view.report is None and root.minimum == (1024, 760)
        assert account_and_business() == data_before
        assert app.saved_login.restore() == 2
        app.before_page_change("Расписание")
        assert app.settings_view.clears == 1
        app.close()
        assert root.destroyed and db.connection is None
    finally:
        db.close()


class Value:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class Label:
    def configure(self, **kwargs):
        self.options = kwargs


class Settings:
    clear_passwords = SettingsView.clear_passwords
    toggle_passwords = SettingsView.toggle_passwords

    def __init__(self):
        self.current_password, self.new_password, self.repeat_password = [
            Value(value) for value in ["старый", " новый123 ", " новый123 "]
        ]
        self.show_password = Value(True)
        self.password_entries = [Label() for n in range(3)]
        (
            self.account_title,
            self.name_label,
            self.login_label,
            self.email_label,
            self.password_button,
            self.backup_button,
        ) = [Label() for n in range(6)]
        self.load_account = lambda: dict(
            user_id=2, name="Имя", login="логин", email="mail@example.com"
        )


settings = Settings()
calls = []
settings.on_change = lambda *args: calls.append(args) or False
assert SettingsView.submit_password(settings) == "break"
assert calls == [("старый", " новый123 ", " новый123 ")]
assert all(
    variable.get() == ""
    for variable in [
        settings.current_password,
        settings.new_password,
        settings.repeat_password,
    ]
)
SettingsView.refresh(settings)
assert (
    settings.name_label.options["text"] == "Имя: Имя"
    and settings.password_button.options["state"] == "normal"
)
settings.load_account = lambda: None
SettingsView.refresh(settings)
assert (
    settings.backup_button.options["state"] == "disabled"
    and settings.email_label.options["text"] == "Электронная почта: —"
)
print(
    (
        "PASS: account metadata, password validation/hash/old-new login and field "
        "clearing; complete SQLite backup/integrity/error guards; logout "
        "decline/cleanup and fresh second-user login with no old UI cache; previous "
        "data preserved"
    )
)
