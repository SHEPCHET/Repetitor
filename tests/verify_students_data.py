"""Check student-card data using an isolated database."""

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

spec = importlib.util.spec_from_file_location(
    "candidate_students", (PROJECT / "main.py")
)
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

with tempfile.TemporaryDirectory() as folder:
    db = DatabaseManager()
    db.db_path = Path(folder) / "isolated.db"
    connection = sqlite3.connect(db.db_path)
    connection.executescript(schema)
    connection.executemany(
        "INSERT INTO students (full_name, is_archived) VALUES (?, ?)",
        [("Иванов Иван", 0), ("Иванов Архив", 1), ("Петров Пётр", 0)],
    )
    connection.execute("INSERT INTO parents (full_name) VALUES ('Родитель')")
    connection.execute("INSERT INTO student_parents VALUES (1, 1, 1)")
    connection.execute("INSERT INTO subjects (name) VALUES ('Математика')")
    connection.execute("""INSERT INTO enrollments
        (student_id, subject_id, preparation_goal, price_60_kopecks)
        VALUES (1, 1, 'ЕГЭ', 140050)""")
    connection.commit()
    connection.close()

    app = gui.ApplicationController.__new__(gui.ApplicationController)
    app.db = db
    app.root = None
    app.authenticator = SimpleNamespace(current_user_id=1)

    def unexpected_error(*args, **kwargs):
        raise AssertionError(args)

    gui.messagebox.showerror = unexpected_error
    try:
        assert len(app.load_students("")) == 2
        card = app.load_students("иВаНоВ")[0]
        assert card["student"].student_id == 1
        assert card["parents"][0][0].full_name == "Родитель"
        assert card["parents"][0][1] is True
        assert card["enrollments"][0][1] == "Математика"
        assert card["enrollments"][0][0].price_60_kopecks == 140050
        assert len(app.load_students("00001")) == 1
        assert app.load_students("нет совпадений") == []
        assert app.load_students("2") == []
        assert not db.connection.in_transaction
        assert db.connection.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 3
        app.authenticator.current_user_id = None
        assert app.load_students("") == []
    finally:
        db.close()

print(
    (
        "PASS: Cyrillic and ID search, archived exclusion, parent and subject links, "
        "exact kopecks, no writes, authentication guard"
    )
)
