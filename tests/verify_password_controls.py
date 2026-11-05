"""Переключатели и очистка паролей без запуска настоящего окна."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace, ModuleType

PROJECT = Path(__file__).resolve().parents[1]


class Value:
    def __init__(self, master=None, value=""):
        self.value, self.callbacks = value, []

    def get(self):
        return self.value

    def set(self, value):
        self.value = value
        for callback in self.callbacks:
            callback()

    def trace_add(self, mode, callback):
        self.callbacks.append(callback)


class Widget:
    def __init__(self, parent=None, **kwargs):
        self.parent, self.options, self.children = parent, kwargs, []
        self.placement = {}
        if parent is not None:
            parent.children.append(self)

    def place(self, **kwargs):
        self.placement = kwargs

    def place_forget(self):
        self.placement = {}

    def pack(self, **kwargs):
        pass

    def grid(self, **kwargs):
        pass

    def columnconfigure(self, *args, **kwargs):
        pass

    def bind(self, *args):
        pass

    def configure(self, **kwargs):
        self.options.update(kwargs)

    def winfo_children(self):
        return list(self.children)

    def destroy(self):
        for child in list(self.children):
            child.destroy()
        if self.parent is not None:
            self.parent.children.remove(self)

    def focus_get(self):
        return None

    def create_window(self, *args, **kwargs):
        return 1

    def yview(self, *args):
        pass

    def set(self, *args):
        pass


tk = ModuleType("tkinter")
tk.Frame = tk.Label = tk.Entry = tk.Button = tk.Checkbutton = tk.Canvas = Widget
tk.StringVar = tk.BooleanVar = Value
tk.font = SimpleNamespace(families=lambda parent: [])
tk.ttk = SimpleNamespace(Scrollbar=Widget)
sys.modules["tkinter"] = tk


def load(name):
    spec = importlib.util.spec_from_file_location(
        "test_" + name, PROJECT / (name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


auth = load("auth_view")
settings = load("settings_view")
calls = []
view = auth.AuthWindow(
    Widget(), lambda *args: calls.append(args), lambda *args: calls.append(args)
)
view.fields["password"].set(" Legacy password ")
view.show_password.set(True)
view._toggle_passwords()
assert view.fields["password"].entry.options["show"] == ""
assert view.fields["password"].get() == " Legacy password "
view.clear_password()
assert (
    not view.show_password.get()
    and view.fields["password"].entry.options["show"] == "*"
)
assert view.fields["password"].get() == ""
view.show_registration()
assert not view.show_password.get()
for key in ("password", "repeat"):
    view.fields[key].set(" abcde1 ")
view.show_password.set(True)
view._toggle_passwords()
assert all(
    view.fields[key].entry.options["show"] == "" for key in ("password", "repeat")
)
view._submit()
assert calls[-1][-2:] == (" abcde1 ", " abcde1 ")
rules = next(
    child
    for child in view.panel.children
    if child.options.get("text", "").startswith("От 8")
)
switch = next(
    child
    for child in view.panel.children
    if child.options.get("text") == "Показать пароль"
)
assert (
    rules.placement["y"] >= 424 + 70
    and rules.placement["y"] + rules.placement["height"] <= 517
)
assert (
    switch.placement["y"] >= 517 + 70
    and switch.placement["y"] + switch.placement["height"] <= 624
)
view.show_login()
assert (
    not view.show_password.get()
    and view.fields["password"].entry.options["show"] == "*"
)

page = settings.SettingsView(
    Widget(),
    "Arial",
    lambda: dict(user_id=1, name="Имя", login="login", email="a@example.com"),
    lambda *args: calls.append(args),
    lambda: None,
    lambda: None,
)
for value in (page.current_password, page.new_password, page.repeat_password):
    value.set(" abcde1 ")
page.show_password.set(True)
page.toggle_passwords()
assert all(entry.options["show"] == "" for entry in page.password_entries)
page.submit_password()
assert calls[-1] == (" abcde1 ", " abcde1 ", " abcde1 ")
assert not page.show_password.get() and all(
    entry.options["show"] == "*" for entry in page.password_entries
)
assert all(
    value.get() == ""
    for value in (page.current_password, page.new_password, page.repeat_password)
)


def fail(*args):
    raise ValueError("Проверочная ошибка")


page.on_change = fail
page.show_password.set(True)
try:
    page.submit_password()
except ValueError:
    pass
assert not page.show_password.get()
rules = next(
    child
    for child in page.body.children
    if child.options.get("text", "").startswith("Новый пароль:")
)
switch = next(
    child
    for child in page.body.children
    if child.options.get("text") == "Показать пароли"
)
assert (
    rules.placement["y"] >= 112
    and rules.placement["y"] + rules.placement["height"] <= switch.placement["y"]
)
assert (
    switch.placement["y"] + switch.placement["height"]
    <= page.password_button.placement["y"]
)
assert (
    page.email_label.placement["y"] + page.email_label.placement["height"]
    < page.body.options["height"]
)
print(
    (
        "PASS: show/hide login and both registration fields, unchanged submitted "
        "values, hints/switch layout bounds, visibility reset on navigation, settings"
        " success/failure clearing and scrolling content bounds"
    )
)
