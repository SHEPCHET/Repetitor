"""Формы входа и регистрации."""

import tkinter as tk
from tkinter import font


class InputField(tk.Frame):
    """Поле ввода с подсказкой."""

    def __init__(self, parent, hint, family, password=False):
        """Создание поля."""
        super().__init__(parent, bg="#d9d9d9", cursor="xterm")
        self.value = tk.StringVar(master=self)

        self.entry = tk.Entry(
            self,
            textvariable=self.value,
            font=(family, -16),
            bg="#d9d9d9",
            fg="black",
            insertbackground="black",
            relief="flat",
            cursor="xterm",
            borderwidth=0,
            highlightthickness=0
        )

        if password:
            self.entry.configure(show="*")

        self.entry.place(x=27, y=0, width=306, height=48)

        self.hint = tk.Label(
            self,
            text=hint,
            font=(family, -16),
            bg="#d9d9d9",
            fg="#6f6f6f",
            anchor="w",
            cursor="xterm",
            borderwidth=0,
            padx=0,
            pady=0
        )

        self.bind("<Button-1>", self._focus)
        self.hint.bind("<Button-1>", self._focus)
        self.entry.bind("<FocusIn>", self._refresh)
        self.entry.bind("<FocusOut>", self._refresh)
        self.value.trace_add("write", self._refresh)
        self._refresh()

    def _focus(self, event=None):
        """Нажатие на серый блок."""
        self.entry.focus_set()
        self.entry.selection_clear()

        if event is not None and event.widget is self and event.x < 27:
            self.entry.icursor(0)
        else:
            self.entry.icursor("end")

        return "break"

    def _refresh(self, *args):
        """Подсказка в пустом поле."""
        if self.value.get() == "" and self.focus_get() != self.entry:
            self.hint.place(x=27, y=14, width=306, height=20)
        else:
            self.hint.place_forget()

    def get(self):
        """Введённый текст."""
        return self.value.get()

    def set(self, value):
        """Заполнение поля."""
        self.value.set(value)


class AuthWindow(tk.Frame):
    """Экраны авторизации по макетам."""

    def __init__(self, parent, on_login, on_register):
        """Создание формы и подключение кнопок."""
        super().__init__(parent, bg="white")
        self.on_login = on_login
        self.on_register = on_register

        if "Inter" in font.families(parent):
            self.family = "Inter"
        else:
            self.family = "Arial"

        self.panel = tk.Frame(self, bg="white")
        self.panel.place(
            relx=0.5, rely=0.5, anchor="center",
            width=600, height=800
        )

        self.fields = {}
        self.show_login()

    def _clear(self):
        """Очистка предыдущей формы."""
        for widget in self.panel.winfo_children():
            widget.destroy()

        self.fields = {}

    def _title(self, text, y):
        """Заголовок формы."""
        title = tk.Label(
            self.panel, text=text, font=(self.family, -32),
            bg="white", fg="black",
            borderwidth=0, padx=0, pady=0
        )
        title.place(x=0, y=y, width=600, height=39)

    def _field(self, key, label, hint, y, password=False):
        """Подпись и поле ввода."""
        caption = tk.Label(
            self.panel, text=label, font=(self.family, -18),
            bg="white", fg="black", anchor="w",
            borderwidth=0, padx=0, pady=0
        )
        caption.place(x=120, y=y, width=360, height=22)

        field = InputField(
            self.panel, hint, self.family, password
        )
        field.place(x=120, y=y + 22, width=360, height=48)
        field.entry.bind("<Return>", self._submit)

        self.fields[key] = field

    def _button(self, text, y):
        """Основная кнопка формы."""
        button = tk.Button(
            self.panel, text=text, command=self._submit,
            font=(self.family, -18),
            bg="#757575", fg="white",
            activebackground="#757575",
            activeforeground="white",
            relief="flat", borderwidth=0,
            highlightthickness=0,
            cursor="hand2", padx=0, pady=0
        )
        button.place(x=120, y=y, width=360, height=48)
        button.bind("<Return>", self._submit)

    def _footer(self, text, link, y, command):
        """Ссылка на другую форму."""
        footer = tk.Frame(self.panel, bg="white")
        footer.place(x=120, y=y, width=360, height=19)

        row = tk.Frame(footer, bg="white")
        row.pack()

        tk.Label(
            row, text=text, font=(self.family, -16),
            bg="white", fg="#6f6f6f",
            padx=0, pady=0, borderwidth=0
        ).pack(side="left")

        button = tk.Button(
            row, text=link, command=command,
            font=(self.family, -16, "underline"),
            bg="white", fg="black",
            activebackground="white",
            activeforeground="black",
            relief="flat", borderwidth=0,
            highlightthickness=0,
            cursor="hand2", padx=0, pady=0
        )
        button.pack(side="left")
        button.bind("<Return>", self._follow_link)

    def _follow_link(self, event):
        """Открытие ссылки клавишей Enter."""
        event.widget.invoke()
        return "break"

    def show_login(self, username=""):
        """Экран входа."""
        self._clear()
        self.mode = "login"

        self._title("Вход в систему", 268)
        self._field(
            "username", "Логин", "Введите логин", 337
        )
        self._field(
            "password", "Пароль", "Введите пароль", 430, True
        )
        self._button("Войти", 537)
        self._footer(
            "Нет аккаунта? ", "Зарегистрироваться", 609,
            self.show_registration
        )

        self.fields["username"].set(username)

    def show_registration(self):
        """Экран регистрации."""
        self._clear()
        self.mode = "registration"

        self._title("Регистрация в системе", 76)
        self._field("name", "Имя", "Введите имя", 145)
        self._field(
            "username", "Логин", "Придумайте логин", 238
        )
        self._field(
            "email", "Электронная почта",
            "Введите адрес электронной почты", 331
        )
        self._field(
            "password", "Пароль", "Придумайте пароль", 424, True
        )
        self._field(
            "repeat", "Подтверждение пароля",
            "Повторите пароль", 517, True
        )
        self._button("Зарегистрироваться", 624)
        self._footer(
            "Уже есть аккаунт? ", "Войти", 696,
            self.show_login
        )

    def clear_password(self):
        """Очистка пароля после проверки входа."""
        self.fields["password"].set("")

    def _submit(self, event=None):
        """Передача введённых данных контроллеру."""
        values = {}

        for key, field in self.fields.items():
            values[key] = field.get()

        if self.mode == "login":
            self.on_login(
                values["username"], values["password"]
            )
        else:
            self.on_register(
                values["name"],
                values["username"],
                values["email"],
                values["password"],
                values["repeat"]
            )

        return "break"