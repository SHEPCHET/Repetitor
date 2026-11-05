"""Verify GUI callbacks with real authentication and a temporary database."""

import ast
import importlib.util
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from database import DatabaseManager

source = PROJECT / "main.py"
spec = importlib.util.spec_from_file_location("candidate_gui", source)
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


class FakeRoot:
    def minsize(self, width, height):
        self.minimum_size = (width, height)

    def protocol(self, name, callback):
        self.close_callback = callback

    def destroy(self):
        self.destroyed = True


class FakeView:
    def __init__(self, parent, on_login, on_register):
        self.on_login = on_login
        self.on_register = on_register
        self.cleared = 0
        self.login_name = None

    def pack(self, **kwargs):
        pass

    def pack_forget(self):
        self.hidden = True

    def clear_password(self):
        self.cleared += 1

    def show_login(self, username=""):
        self.login_name = username


class FakeMainWindow:
    def __init__(self, parent):
        self.parent = parent
        self.family = "Arial"
        self.pages = {
            "Ученики": object(),
            "Расписание": object(),
            "Занятия": object(),
            "Оплаты": object(),
            "Отчеты": object(),
            "Настройки": object(),
        }

    def pack(self, **kwargs):
        self.visible = True


class FakeStudentsView:
    def __init__(self, parent, family, callback):
        self.callback = callback
        self.add_button = self
        self.edit_button = self
        self.move_button = self

    def configure(self, **kwargs):
        pass

    def pack(self, **kwargs):
        pass


class FakeScheduleView:
    def __init__(self, parent, family, callback):
        self.callback = callback
        self.buttons = {
            "Добавить занятие": self,
            "Перенести занятие": self,
            "Отменить занятие": self,
            "К отменённым": self,
        }

    def configure(self, **kwargs):
        pass

    def pack(self, **kwargs):
        pass


class FakeLessonsView:
    def __init__(self, *args):
        self.editing = False

    def pack(self, **kwargs):
        pass

    def leave_editing(self):
        return True


class FakePaymentsView:
    def __init__(self, *args):
        pass

    def pack(self, **kwargs):
        pass


class FakeReportsView:
    def __init__(self, *args):
        pass

    def pack(self, **kwargs):
        pass


class FakeSettingsView:
    def __init__(self, *args):
        pass

    def pack(self, **kwargs):
        pass

    def clear_passwords(self):
        pass


with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / "repetitor.db"
    connection = sqlite3.connect(path)
    connection.executescript(schema)
    connection.close()
    db = DatabaseManager()
    db.db_path = path
    messages = []
    gui.DatabaseManager = lambda: db
    gui.AuthWindow = FakeView
    gui.MainWindow = FakeMainWindow
    gui.StudentsView = FakeStudentsView
    gui.ScheduleView = FakeScheduleView
    gui.LessonsView = FakeLessonsView
    gui.PaymentsView = FakePaymentsView
    gui.ReportsView = FakeReportsView
    gui.SettingsView = FakeSettingsView
    gui.messagebox.showinfo = lambda title, message, **kw: messages.append(
        ("info", message)
    )
    gui.messagebox.showerror = lambda title, message, **kw: messages.append(
        ("error", message)
    )
    root = FakeRoot()
    app = gui.ApplicationController(root)
    assert not app.backup_due
    password = "ПроверочныйПароль-42"
    app.show_main_window()
    assert app.main_window is None
    app.login("ui_tutor", "wrong")
    assert app.main_window is None

    app.register("Тест", "ui_tutor", "ui@example.com", password, "mismatch")
    assert messages[-1] == ("error", "Пароли не совпадают.")
    assert db.connection.execute("SELECT COUNT(*) FROM users;").fetchone()[0] == 0
    app.register("Тест", " ui_tutor ", "ui@example.com", password, password)
    assert app.backup_due
    assert messages[-1] == ("info", "Учётная запись создана.")
    assert app.view.login_name == "ui_tutor"
    assert app.authenticator.current_user_id is None
    app.login("ui_tutor", password)
    assert app.main_window.visible
    assert app.view.hidden
    assert root.minimum_size == (1024, 760)
    assert app.authenticator.current_user_id is not None
    assert app.view.cleared == 2
    app.login("", "")
    assert messages[-1] == ("error", "Введите логин и пароль.")
    assert app.authenticator.current_user_id is None
    assert app.view.cleared == 3
    app.login("ui_tutor", "wrong")
    assert messages[-1] == ("error", "Неверный логин или пароль.")
    assert app.authenticator.current_user_id is None
    app.register("Тест", "ui_tutor", "ui@example.com", password, password)
    assert messages[-1] == ("error", "Этот логин уже занят.")
    assert db.connection.execute("SELECT COUNT(*) FROM users;").fetchone()[0] == 1
    assert db.connection.in_transaction is False
    root.close_callback()
    assert root.destroyed and db.connection is None

print(
    (
        "PASS: main window requires authentication, successful login changes screen, "
        "password clearing, registration, persistence and clean close"
    )
)
