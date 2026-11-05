"""Учётная запись, пароль и резервная копия."""

import tkinter as tk
from tkinter import ttk


class SettingsView(tk.Frame):
    """Настройки учётной записи и резервные копии."""

    def __init__(self, parent, family, load_account, change_password, backup, logout):
        """Подготовка данных и элементов объекта."""
        super().__init__(parent, bg="#d9d9d9")
        self.family = family
        self.load_account, self.on_change = load_account, change_password
        self.on_backup, self.on_logout = backup, logout
        self.current_password = tk.StringVar(master=self)
        self.new_password = tk.StringVar(master=self)
        self.repeat_password = tk.StringVar(master=self)
        self.show_password = tk.BooleanVar(master=self, value=False)
        self.canvas = tk.Canvas(self, bg="#d9d9d9", highlightthickness=0)
        self.canvas.place(x=0, y=0, relwidth=1, width=-14, relheight=1)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        scrollbar.place(relx=1, x=-14, y=0, width=14, relheight=1)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.body = tk.Frame(self.canvas, bg="#d9d9d9", height=729)
        self.body_window = self.canvas.create_window(
            0, 0, window=self.body, anchor="nw"
        )
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
            tk.Label(
                fields, text=name, font=(family, -14), bg="#d9d9d9", anchor="w", padx=0
            ).grid(row=0, column=column, sticky="ew", padx=padding, pady=(0, 6))
            area = tk.Frame(fields, bg="#a1a1a1", height=32, cursor="xterm")
            area.grid(row=1, column=column, sticky="nsew", padx=padding)
            entry = tk.Entry(
                area,
                textvariable=variable,
                show="*",
                font=(family, -14),
                bg="#a1a1a1",
                fg="white",
                insertbackground="white",
                borderwidth=0,
                relief="flat",
            )
            entry.place(x=10, y=0, relwidth=1, width=-20, relheight=1)
            area.bind("<Button-1>", lambda event, current=entry: current.focus_set())
            self.password_entries.append(entry)
        self.password_entries[-1].bind("<Return>", self.submit_password)
        self._label(
            "Новый пароль: от 8 символов, хотя бы одна буква и одна цифра.",
            116,
            12,
            "#555555",
        )
        tk.Checkbutton(
            self.body,
            text="Показать пароли",
            variable=self.show_password,
            command=self.toggle_passwords,
            font=(family, -14),
            bg="#d9d9d9",
            activebackground="#d9d9d9",
            fg="black",
            activeforeground="black",
            selectcolor="#d9d9d9",
            anchor="w",
            borderwidth=0,
            highlightthickness=0,
            padx=0,
            pady=0,
            cursor="hand2",
        ).place(x=16, y=142, width=244, height=22)
        self.password_button = self._button("Сменить пароль", self.submit_password, 174)
        self._separator(238)
        self._label("Резервная копия базы", 271, 20)
        self._label(
            "Резервная копия базы сохраняется в папку backups.", 313, 14, "#555555"
        )
        self.backup_button = self._button(
            "Создать резервную копию", self.create_backup, 348
        )
        self.backup_status = self._label("", 387, 12, "#555555")
        self._separator(412)
        self._label("Выход из учётной записи", 445, 20)
        self._label("После выхода откроется экран входа.", 487, 14, "#555555")
        self.logout_button = self._button(
            "Выйти из учётной записи", self.on_logout, 522
        )
        self._separator(581)
        self.account_title = self._label("Учётная запись", 595, 20)
        self.name_label = self._label("Имя: —", 631, 14)
        self.login_label = self._label("Логин: —", 653, 14)
        self.email_label = self._label("Электронная почта: —", 675, 14)
        self.bind("<Map>", self.refresh)

    def _label(self, text, y, size, colour="black"):
        """Размещение подписи на форме."""
        label = tk.Label(
            self.body,
            text=text,
            font=(self.family, -size),
            bg="#d9d9d9",
            fg=colour,
            anchor="w",
            padx=0,
            pady=0,
        )
        label.place(x=16, y=y, relwidth=1, width=-32, height=26 if size == 20 else 20)
        label.bind("<MouseWheel>", self._wheel)
        return label

    def _separator(self, y):
        """Разделитель между разделами настроек."""
        tk.Frame(self.body, bg="#a1a1a1", height=1).place(
            x=16, y=y, relwidth=1, width=-32, height=1
        )

    def _button(self, text, command, y):
        """Создание кнопки с обработчиком нажатия."""
        button = tk.Button(
            self.body,
            text=text,
            command=command,
            font=(self.family, -15),
            bg="#787878",
            fg="white",
            disabledforeground="#bdbdbd",
            activebackground="#6b6b6b",
            activeforeground="white",
            borderwidth=0,
            relief="flat",
            cursor="hand2",
            padx=0,
            pady=0,
        )
        button.place(x=16, y=y, width=244, height=32)
        return button

    def refresh(self, event=None):
        """Обновление данных на экране."""
        self.clear_passwords()
        account = self.load_account()
        if account is None:
            self.account_title.configure(text="Учётная запись")
            self.name_label.configure(text="Имя: —")
            self.login_label.configure(text="Логин: —")
            self.email_label.configure(text="Электронная почта: —")
            state = "disabled"
        else:
            self.account_title.configure(
                text="Учётная запись №" + str(account["user_id"])
            )
            self.name_label.configure(text="Имя: " + account["name"])
            self.login_label.configure(text="Логин: " + account["login"])
            self.email_label.configure(text="Электронная почта: " + account["email"])
            state = "normal"
        self.password_button.configure(state=state)
        self.backup_button.configure(state=state)

    def clear_passwords(self):
        """Очистка полей паролей и возврат скрытого показа."""
        for variable in [
            self.current_password,
            self.new_password,
            self.repeat_password,
        ]:
            variable.set("")
        self.show_password.set(False)
        self.toggle_passwords()

    def toggle_passwords(self):
        """Переключение видимости введённых паролей."""
        mask = "*"
        if self.show_password.get():
            mask = ""
        for entry in self.password_entries:
            entry.configure(show=mask)

    def submit_password(self, event=None):
        """Передача паролей обработчику и очистка полей."""
        try:
            self.on_change(
                self.current_password.get(),
                self.new_password.get(),
                self.repeat_password.get(),
            )
        finally:
            self.clear_passwords()
        return "break"

    def create_backup(self):
        """Создание копии и отображение имени нового файла."""
        path = self.on_backup()
        if path is not None:
            self.backup_status.configure(text="Последняя копия: " + path.name)

    def _resize(self, event=None):
        """Подстройка содержимого под размер окна."""
        self.canvas.itemconfigure(
            self.body_window, width=max(780, self.canvas.winfo_width())
        )
        self._scroll_region()

    def _scroll_region(self, event=None):
        """Обновление границ прокрутки содержимого."""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _wheel(self, event):
        """Прокрутка содержимого колесом мыши."""
        if event.delta:
            self.canvas.yview_scroll(-3 if event.delta > 0 else 3, "units")
        return "break"
