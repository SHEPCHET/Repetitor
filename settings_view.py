"""Учётная запись, пароль и резервная копия."""

import tkinter as tk
from tkinter import ttk


class SettingsView(tk.Frame):
    def __init__(self, parent, family, load_account, change_password, backup, logout):
        super().__init__(parent, bg="#d9d9d9")
        self.family = family
        self.load_account, self.on_change = load_account, change_password
        self.on_backup, self.on_logout = backup, logout
        self.current_password = tk.StringVar(master=self)
        self.new_password = tk.StringVar(master=self)
        self.repeat_password = tk.StringVar(master=self)
        self.canvas = tk.Canvas(self, bg="#d9d9d9", highlightthickness=0)
        self.canvas.place(x=0, y=0, relwidth=1, width=-14, relheight=1)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        scrollbar.place(relx=1, x=-14, y=0, width=14, relheight=1)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.body = tk.Frame(self.canvas, bg="#d9d9d9", height=684)
        self.body_window = self.canvas.create_window(0, 0, window=self.body, anchor="nw")
        self.canvas.bind("<Configure>", self._resize)
        self.body.bind("<Configure>", self._scroll_region)
        self.canvas.bind("<MouseWheel>", self._wheel)
        self._label("Смена пароля", 14, 20)

        fields = tk.Frame(self.body, bg="#d9d9d9")
        fields.place(x=16, y=56, relwidth=1, width=-32, height=56)
        self.password_entries = []
        names = ["Текущий пароль", "Новый пароль", "Повтор нового пароля"]
        variables = [self.current_password, self.new_password, self.repeat_password]
        for column, (name, variable) in enumerate(zip(names, variables)):
            fields.columnconfigure(column, weight=1, uniform="passwords")
            padding = (0, 18) if column < 2 else (0, 0)
            tk.Label(fields, text=name, font=(family, -14), bg="#d9d9d9", anchor="w", padx=0).grid(
                row=0, column=column, sticky="ew", padx=padding, pady=(0, 6))
            area = tk.Frame(fields, bg="#a1a1a1", height=32, cursor="xterm")
            area.grid(row=1, column=column, sticky="nsew", padx=padding)
            entry = tk.Entry(area, textvariable=variable, show="*", font=(family, -14),
                             bg="#a1a1a1", fg="white", insertbackground="white",
                             borderwidth=0, relief="flat")
            entry.place(x=10, y=0, relwidth=1, width=-20, relheight=1)
            area.bind("<Button-1>", lambda event, current=entry: current.focus_set())
            self.password_entries.append(entry)
        self.password_entries[-1].bind("<Return>", self.submit_password)
        self.password_button = self._button("Сменить пароль", self.submit_password, 129)
        self._separator(193)
        self._label("Резервная копия базы", 226, 20)
        self._label("Резервная копия базы сохраняется в папку backups.", 268, 14, "#555555")
        self.backup_button = self._button("Создать резервную копию", self.create_backup, 303)
        self.backup_status = self._label("", 342, 12, "#555555")
        self._separator(367)
        self._label("Выход из учётной записи", 400, 20)
        self._label("После выхода откроется экран входа.", 442, 14, "#555555")
        self.logout_button = self._button("Выйти из учётной записи", self.on_logout, 477)
        self._separator(536)
        self.account_title = self._label("Учётная запись", 550, 20)
        self.name_label = self._label("Имя: —", 586, 14)
        self.login_label = self._label("Логин: —", 608, 14)
        self.email_label = self._label("Электронная почта: —", 630, 14)
        self.bind("<Map>", self.refresh)

    def _label(self, text, y, size, colour="black"):
        label = tk.Label(self.body, text=text, font=(self.family, -size),
                         bg="#d9d9d9", fg=colour, anchor="w", padx=0, pady=0)
        label.place(x=16, y=y, relwidth=1, width=-32, height=26 if size == 20 else 20)
        label.bind("<MouseWheel>", self._wheel)
        return label

    def _separator(self, y):
        tk.Frame(self.body, bg="#a1a1a1", height=1).place(x=16, y=y, relwidth=1, width=-32, height=1)

    def _button(self, text, command, y):
        button = tk.Button(self.body, text=text, command=command, font=(self.family, -15),
                           bg="#787878", fg="white", disabledforeground="#bdbdbd",
                           activebackground="#6b6b6b", activeforeground="white",
                           borderwidth=0, relief="flat", cursor="hand2", padx=0, pady=0)
        button.place(x=16, y=y, width=244, height=32)
        return button

    def refresh(self, event=None):
        self.clear_passwords()
        account = self.load_account()
        if account is None:
            self.account_title.configure(text="Учётная запись")
            self.name_label.configure(text="Имя: —")
            self.login_label.configure(text="Логин: —")
            self.email_label.configure(text="Электронная почта: —")
            state = "disabled"
        else:
            self.account_title.configure(text="Учётная запись №" + str(account["user_id"]))
            self.name_label.configure(text="Имя: " + account["name"])
            self.login_label.configure(text="Логин: " + account["login"])
            self.email_label.configure(text="Электронная почта: " + account["email"])
            state = "normal"
        self.password_button.configure(state=state)
        self.backup_button.configure(state=state)

    def clear_passwords(self):
        for variable in [self.current_password, self.new_password, self.repeat_password]:
            variable.set("")

    def submit_password(self, event=None):
        try:
            self.on_change(self.current_password.get(), self.new_password.get(), self.repeat_password.get())
        finally:
            self.clear_passwords()
        return "break"

    def create_backup(self):
        path = self.on_backup()
        if path is not None:
            self.backup_status.configure(text="Последняя копия: " + path.name)

    def _resize(self, event=None):
        self.canvas.itemconfigure(self.body_window, width=max(780, self.canvas.winfo_width()))
        self._scroll_region()

    def _scroll_region(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _wheel(self, event):
        if event.delta:
            self.canvas.yview_scroll(-3 if event.delta > 0 else 3, "units")
        return "break"
