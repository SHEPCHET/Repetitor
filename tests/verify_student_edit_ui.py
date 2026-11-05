"""Check edit routing, cancel and inline lookup without constructing Tk windows."""

import ast
import copy
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
from student_service import StudentService

spec = importlib.util.spec_from_file_location("edit_controller", (PROJECT / "main.py"))
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


class Form:
    def __init__(self, parent, family, on_save, on_cancel, record=None, on_lookup=None):
        self.record = record
        self.student_id = None if record is None else record["student_id"]
        self.dirty = False
        self.destroyed = False

    def pack(self, **kwargs):
        pass

    def destroy(self):
        self.destroyed = True

    def has_changes(self):
        return self.dirty


class View:
    selected_id = 1
    query = SimpleNamespace(set=lambda value: None)

    def pack(self, **kwargs):
        pass

    def pack_forget(self):
        pass

    def select_student(self, student_id):
        self.selected_id = student_id

    def set_archive_mode(self, archived):
        self.archive_mode = archived


with tempfile.TemporaryDirectory() as folder:
    db = DatabaseManager()
    db.db_path = Path(folder) / "controller.db"
    con = sqlite3.connect(db.db_path)
    con.executescript(schema)
    con.close()
    service = StudentService(db)
    for name in ("Ученик А", "Ученик Б"):
        service.add(
            dict(
                student=dict(
                    full_name=name,
                    phone="",
                    messenger_type="",
                    messenger_contact="",
                    is_archived=False,
                ),
                parents=[],
                enrollments=[],
            )
        )
    app = gui.ApplicationController.__new__(gui.ApplicationController)
    app.db = db
    app.root = None
    app.authenticator = SimpleNamespace(current_user_id=1)
    app.main_window = SimpleNamespace(pages={"Ученики": object()}, family="Arial")
    app.students_view = View()
    app.student_form = None
    gui.StudentForm = Form
    messages = []
    gui.messagebox.showinfo = lambda *args, **kwargs: messages.append(args)
    gui.messagebox.showerror = lambda *args, **kwargs: messages.append(args)
    gui.messagebox.askyesno = lambda *args, **kwargs: False
    try:
        before = tuple(db.connection.iterdump())
        app.edit_student()
        assert app.student_form.student_id == 1
        app.close_student_form()
        assert tuple(db.connection.iterdump()) == before
        app.edit_student()
        first_form = app.student_form
        app.find_student_for_edit("Ученик")
        assert app.student_form is first_form
        assert "несколько" in messages[-1][1]
        app.find_student_for_edit("2")
        assert first_form.destroyed and app.student_form.student_id == 2
        second_form = app.student_form
        second_form.dirty = True
        app.find_student_for_edit("1")
        assert app.student_form is second_form and not second_form.destroyed
        data = copy.deepcopy(second_form.record)
        data["student"]["phone"] = "555"
        app.save_student(data)
        assert app.student_form is None and second_form.destroyed
        assert service.get_card(2)["student"]["phone"] == "555"
        assert service.get_card(1)["student"]["phone"] == ""
        assert db.connection.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 2
        assert app.students_view.selected_id == 2
    finally:
        db.close()

print(
    (
        "PASS: cancel performs no writes, ambiguous lookup preserves form, "
        "pending-change rejection, inline lookup saves correct student without "
        "duplicate"
    )
)
