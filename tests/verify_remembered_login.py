"""Сохранённый вход на временной базе."""

import ast
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
import main as gui
import remembered_login as storage
from authenticator import Authenticator
from database import DatabaseManager

schema_tree = ast.parse((PROJECT / "init_db.py").read_text(encoding="utf-8-sig"))
schema = next(
    ast.literal_eval(node.args[0])
    for node in ast.walk(schema_tree)
    if isinstance(node, ast.Call)
    and isinstance(node.func, ast.Attribute)
    and node.func.attr == "executescript"
)


class Root:
    destroyed = False

    def protocol(self, *args):
        pass

    def minsize(self, *args):
        pass

    def destroy(self):
        self.destroyed = True


class AuthView:
    visible = True

    def __init__(self, *args):
        pass

    def pack(self, **kwargs):
        self.visible = True

    def pack_forget(self):
        self.visible = False

    def clear_password(self):
        pass

    def show_login(self, *args):
        self.username = ""


class Main:
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

    def pack(self, **kwargs):
        pass

    def destroy(self):
        self.destroyed = True


class Page:
    allow_leave = True

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

    def pack(self, **kwargs):
        pass

    def configure(self, **kwargs):
        pass

    def clear_passwords(self):
        pass

    def leave_editing(self):
        return self.allow_leave


messages = []
gui.AuthWindow, gui.MainWindow = AuthView, Main
gui.StudentsView = gui.ScheduleView = gui.LessonsView = gui.PaymentsView = (
    gui.ReportsView
) = gui.SettingsView = Page
gui.messagebox.showinfo = lambda *args, **kwargs: messages.append(("info", args))
gui.messagebox.showerror = lambda *args, **kwargs: messages.append(("error", args))
gui.messagebox.showwarning = lambda *args, **kwargs: messages.append(("warning", args))

with tempfile.TemporaryDirectory() as folder:
    db = DatabaseManager()
    db.db_path = Path(folder) / "repetitor.db"
    con = sqlite3.connect(db.db_path)
    con.executescript(schema)
    con.execute("INSERT INTO students(full_name) VALUES ('Проверочный ученик')")
    con.commit()
    con.close()
    gui.DatabaseManager = lambda: db
    try:
        # Существующая база обновляется автоматически и сохраняет таблицы и данные.
        app = gui.ApplicationController(Root())
        assert app.authenticator.current_user_id is None and app.main_window is None
        assert app.view.visible and not app.saved_login.path.exists()
        assert (
            db.connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'"
            ).fetchone()[0]
            == 9
        )
        assert (
            db.connection.execute("SELECT full_name FROM students").fetchone()[0]
            == "Проверочный ученик"
        )
        app.register(
            "Первый", "first", "first@example.com", "Password-123", "Password-123"
        )
        app.register(
            "Второй", "second", "second@example.com", "Password-456", "Password-456"
        )
        assert not app.saved_login.path.exists()
        app.login("first", "wrong")
        assert app.main_window is None and not app.saved_login.path.exists()
        app.login("first", "Password-123")
        assert app.authenticator.current_user_id == 1 and app.saved_login.restore() == 1
        saved_text = app.saved_login.path.read_text(encoding="utf-8")
        saved = json.loads(saved_text)
        assert set(saved) == {"user_id", "token"} and len(saved["token"]) == 64
        row = db.connection.execute(
            "SELECT password_hash, remember_token_hash FROM users WHERE user_id = 1"
        ).fetchone()
        assert (
            "Password-123" not in saved_text
            and row[0] not in saved_text
            and saved["token"] != row[1]
        )
        # Отказ закрыть журнал не сбрасывает вход.
        app.lessons_view.allow_leave = False
        assert not app.logout() and app.saved_login.restore() == 1
        app.lessons_view.allow_leave = True
        app.close()
        assert (
            app.root.destroyed
            and db.connection is None
            and app.saved_login.path.exists()
        )
        assert len(list((Path(folder) / "backups").glob("*.db"))) == 1
        # Новый контроллер восстанавливает аккаунт, пароль повторно не запрашивается.
        app = gui.ApplicationController(Root())
        assert (
            app.authenticator.current_user_id == 1
            and app.main_window is not None
            and not app.view.visible
        )
        assert app.backup_due
        assert app.logout() and app.main_window is None and app.view.visible
        assert not app.saved_login.path.exists() and app.saved_login.restore() is None
        app.saved_login.path.write_text(saved_text, encoding="utf-8")
        assert app.saved_login.restore() is None
        app.saved_login.path.unlink()
        app.close()
        app = gui.ApplicationController(Root())
        assert app.authenticator.current_user_id is None and app.view.visible
        # Другой аккаунт становится сохранённым аккаунтом.
        app.login("second", "Password-456")
        assert app.saved_login.restore() == 2
        old_session = app.saved_login.path.read_bytes()
        app.close()
        app = gui.ApplicationController(Root())
        assert app.load_account()["login"] == "second"
        # После смены пароля старый ключ больше не подходит.
        assert app.change_account_password(
            "Password-456", "NewPassword-789", "NewPassword-789"
        )
        new_session = app.saved_login.path.read_bytes()
        assert new_session != old_session and app.saved_login.restore() == 2
        app.saved_login.path.write_bytes(old_session)
        assert app.saved_login.restore() is None
        app.saved_login.path.write_bytes(new_session)
        # Подмена ID и случайного ключа, повреждённый или удалённый файл не дают вход.
        for content in [
            b"broken",
            b"[]",
            b"{}",
            b'{"user_id": true, "token": "bad"}',
            json.dumps(
                dict(user_id=1, token=json.loads(new_session)["token"])
            ).encode(),
            json.dumps(dict(user_id=2, token="0" * 64)).encode(),
        ]:
            app.saved_login.path.write_bytes(content)
            assert app.saved_login.restore() is None
        app.saved_login.path.unlink()
        assert app.saved_login.restore() is None
        app.saved_login.path.write_bytes(new_session)
        # Ошибка записи ключа не мешает обычному входу.
        real_replace = storage.os.replace
        before = db.connection.execute(
            "SELECT remember_token_hash FROM users WHERE user_id = 2"
        ).fetchone()
        storage.os.replace = lambda *args: (_ for _ in ()).throw(
            OSError("Проверочная ошибка записи")
        )
        app.remember_login()
        storage.os.replace = real_replace
        assert messages[-1][0] == "warning" and app.authenticator.current_user_id == 2
        assert (
            db.connection.execute(
                "SELECT remember_token_hash FROM users WHERE user_id = 2"
            ).fetchone()
            == before
        )
        assert app.saved_login.restore() == 2 and not list(
            Path(folder).glob(".login_session-*.tmp")
        )
        # Смена пароля другим подключением отменяет старый сохранённый вход.
        auth = Authenticator(db)
        assert auth.login("second", "NewPassword-789")
        assert auth.change_password("NewPassword-789", "FinalPassword-999")
        assert app.saved_login.restore() is None
        # Удалённый аккаунт тоже не восстанавливается.
        app.saved_login.remember(2)
        with db.connection:
            db.connection.execute("DELETE FROM users WHERE user_id = 2")
        assert app.saved_login.restore() is None
        # Чужая незавершённая транзакция не сохраняется и не откатывается.
        db.connection.execute("UPDATE students SET phone = '123'")
        try:
            app.saved_login.forget(1)
        except ValueError:
            pass
        else:
            raise AssertionError("Foreign transaction accepted")
        assert db.connection.in_transaction
        db.connection.rollback()
    finally:
        db.close()

print(
    (
        "PASS: schema upgrade, login/restart/close/backup, explicit logout, switching"
        " accounts, password rotation, tampering/corruption, file failure rollback, "
        "removed account and transaction guards"
    )
)
