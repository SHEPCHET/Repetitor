"""Копия при закрытии на отдельной базе."""

import ast
import sqlite3
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
import main as gui
from database import DatabaseManager

tree = ast.parse((PROJECT / "init_db.py").read_text(encoding="utf-8-sig"))
schema = next(
    ast.literal_eval(node.args[0])
    for node in ast.walk(tree)
    if isinstance(node, ast.Call)
    and isinstance(node.func, ast.Attribute)
    and node.func.attr == "executescript"
)


class Root:
    destroyed = False

    def destroy(self):
        self.destroyed = True


def controller(db, due=True):
    app = gui.ApplicationController.__new__(gui.ApplicationController)
    app.db = db
    app.backup_due = due
    app.root = Root()
    app.authenticator = SimpleNamespace(current_user_id=1)
    app.authenticator.logout = lambda: setattr(
        app.authenticator, "current_user_id", None
    )
    app.lessons_view = SimpleNamespace(leave_editing=lambda: True)
    return app


with tempfile.TemporaryDirectory() as folder:
    db = DatabaseManager()
    db.db_path = Path(folder) / "repetitor.db"
    connection = sqlite3.connect(db.db_path)
    connection.executescript(schema)
    connection.execute("INSERT INTO subjects(name) VALUES (?)", ["Проверочный предмет"])
    connection.commit()
    connection.close()
    db.connect()
    original = list(db.connection.iterdump())
    app = controller(db)
    # Отказ закрыть журнал не создаёт копию.
    app.lessons_view.leave_editing = lambda: False
    app.close()
    assert not app.root.destroyed and not (Path(folder) / "backups").exists()
    app.lessons_view.leave_editing = lambda: True
    # Ошибка записи и Отмена оставляют сессию и подключение.
    backup = db.backup
    calls = []

    def failure():
        raise OSError("Нет места для копии")

    db.backup = failure
    gui.messagebox.askretrycancel = lambda *args, **kwargs: calls.append(args) or False
    app.close()
    assert len(calls) == 1 and app.backup_due and not app.root.destroyed
    assert app.authenticator.current_user_id == 1 and db.connection is not None
    # Повтор после временной ошибки.
    attempts = []

    def temporary_failure():
        attempts.append(1)
        if len(attempts) == 1:
            raise sqlite3.OperationalError("Временная ошибка")
        return backup()

    db.backup = temporary_failure
    gui.messagebox.askretrycancel = lambda *args, **kwargs: True
    app.close()
    assert len(attempts) == 2 and app.root.destroyed and not app.backup_due
    assert app.authenticator.current_user_id is None and db.connection is None
    copies = list((Path(folder) / "backups").glob("*.db"))
    assert len(copies) == 1
    copy = sqlite3.connect(copies[0])
    try:
        assert list(copy.iterdump()) == original
        assert copy.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert copy.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        copy.close()
    # После выхода из аккаунта копия всё равно нужна.
    db.backup = backup
    app = controller(db)
    app.authenticator.logout()
    app.close()
    assert app.root.destroyed and len(list(copies[0].parent.glob("*.db"))) == 2
    # Без входа и регистрации лишняя копия не создаётся.
    app = controller(db, due=False)
    app.close()
    assert app.root.destroyed and len(list(copies[0].parent.glob("*.db"))) == 2

    # Восстановление проверяется на новом файле, рабочая база не заменяется.
    restored = Path(folder) / "restored.db"
    restored.write_bytes(copies[0].read_bytes())
    connection = sqlite3.connect(restored)
    try:
        assert list(connection.iterdump()) == original
    finally:
        connection.close()

print(
    (
        "PASS: automatic close backup, declined close, failure/cancel/retry, logout, "
        "unique copies, integrity and restore"
    )
)
