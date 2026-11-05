"""Добавление и изменение карточки ученика."""

import tkinter as tk
from tkinter import ttk


class FormInput(tk.Frame):
    """Поле с подсказкой."""

    def __init__(self, parent, family, hint, choices=None):
        """Подготовка данных и элементов объекта."""
        super().__init__(parent, bg="#d9d9d9", height=32, cursor="xterm")
        self.value = tk.StringVar(master=self)
        if choices is None:
            self.entry = tk.Entry(
                self,
                textvariable=self.value,
                font=(family, -14),
                bg="#d9d9d9",
                relief="flat",
                borderwidth=0,
                highlightthickness=0,
            )
            self.entry.place(x=8, y=0, relwidth=1, width=-16, relheight=1)
        else:
            self.entry = ttk.Combobox(
                self,
                textvariable=self.value,
                values=choices,
                font=(family, -14),
                state="readonly",
                style="Card.TCombobox",
            )
            self.entry.place(x=0, y=0, relwidth=1, relheight=1)

        self.hint = tk.Label(
            self,
            text=hint,
            bg="#d9d9d9",
            fg="#6b6b6b",
            font=(family, -14),
            anchor="w",
            cursor="xterm",
            padx=0,
        )
        self.hint.bind("<Button-1>", self._focus)
        self.bind("<Button-1>", self._focus)
        self.entry.bind("<FocusIn>", self._refresh)
        self.entry.bind("<FocusOut>", self._refresh)
        self.value.trace_add("write", self._refresh)
        self._refresh()

    def _focus(self, event=None):
        """Передача фокуса полю при нажатии на серый блок."""
        self.entry.focus_set()
        if isinstance(self.entry, ttk.Combobox):
            self.entry.event_generate(
                "<Button-1>", x=self.entry.winfo_width() - 10, y=16
            )

    def _refresh(self, *args):
        """Обновление подсказки пустого поля."""
        if self.value.get() == "" and self.focus_get() != self.entry:
            self.hint.place(x=8, y=0, relwidth=1, width=-32, height=32)
        else:
            self.hint.place_forget()

    def get(self):
        """Получение текущего значения поля."""
        return self.value.get().strip()

    def set(self, value):
        """Заполнение существующими данными."""
        value = value or ""
        if isinstance(self.entry, ttk.Combobox):
            choices = list(self.entry.cget("values"))
            if value and value not in choices:
                choices.append(value)
                self.entry.configure(values=choices)
        self.value.set(value)


class StudentForm(tk.Frame):
    """Данные ученика, родителей и предметов."""

    def __init__(self, parent, family, on_save, on_cancel, record=None, on_lookup=None):
        """Подготовка данных и элементов объекта."""
        super().__init__(parent, bg="#d9d9d9")
        self.family = family
        self.on_save = on_save
        self.on_lookup = on_lookup
        self.student_id = None
        self.parents = []
        self.directions = []
        self.parent_ids = []
        self.enrollment_ids = []
        self.primary = tk.IntVar(master=self, value=0)

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Card.TCombobox",
            padding=(8, 0),
            borderwidth=0,
            relief="flat",
            background="#d9d9d9",
            fieldbackground="#d9d9d9",
            bordercolor="#d9d9d9",
            lightcolor="#d9d9d9",
            darkcolor="#d9d9d9",
            arrowcolor="black",
        )
        style.map(
            "Card.TCombobox",
            fieldbackground=[("readonly", "#d9d9d9")],
            background=[("active", "#d9d9d9"), ("readonly", "#d9d9d9")],
            foreground=[("readonly", "black")],
            selectbackground=[("readonly", "#d9d9d9")],
            selectforeground=[("readonly", "black")],
            bordercolor=[("focus", "#d9d9d9")],
            lightcolor=[("focus", "#d9d9d9")],
            darkcolor=[("focus", "#d9d9d9")],
        )
        self.option_add("*TCombobox*Listbox.background", "#d9d9d9")
        self.option_add("*TCombobox*Listbox.foreground", "black")
        self.option_add("*TCombobox*Listbox.selectBackground", "#a1a1a1")
        self.option_add("*TCombobox*Listbox.selectForeground", "black")

        panel = tk.Frame(self, bg="#6b6b6b")
        panel.place(x=23, y=15, relwidth=1, width=-46, relheight=1, height=-30)
        title = "Добавление ученика"
        status_y = 91
        body_y = 159
        if on_lookup is not None:
            title = "Изменить карточку"
            status_y = 113
            body_y = 187
            self._label(panel, "Поиск ученика по ФИО или ID").place(x=20, y=49)
            self.lookup = FormInput(panel, family, "Введите ID или имя")
            self.lookup.place(x=20, y=73, width=212, height=32)
            self.lookup.entry.bind("<Return>", self._lookup)
        else:
            self._label(panel, "ID ученика: Присваивается автоматически").place(
                x=20, y=61
            )
        self._label(panel, title, 24).place(x=20, y=20)
        self._label(panel, "Статус").place(x=20, y=status_y)
        self.status = FormInput(panel, family, "Выберите", ["Активный", "Архивный"])
        self.status.value.set("Активный")
        self.status.place(x=20, y=status_y + 24, width=190, height=32)

        self.canvas = tk.Canvas(panel, bg="#6b6b6b", highlightthickness=0)
        self.canvas.place(
            x=20, y=body_y, relwidth=1, width=-54, relheight=1, height=-body_y - 61
        )
        scrollbar = tk.Scrollbar(panel, command=self.canvas.yview)
        scrollbar.place(
            relx=1, x=-32, y=body_y, width=12, relheight=1, height=-body_y - 61
        )
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.body = tk.Frame(self.canvas, bg="#6b6b6b")
        self.window = self.canvas.create_window(0, 0, window=self.body, anchor="nw")
        self.body.bind("<Configure>", self._scroll)
        self.canvas.bind("<Configure>", self._resize)

        if on_lookup is None:
            self._heading(self.body, "Данные ученика")
        self.student = self._contacts(self.body, False)
        self._label(
            self.body, "Основным контактом может быть только один родитель"
        ).pack(anchor="w", pady=(16, 8))
        self._heading(self.body, "Родители")
        self.parent_area = tk.Frame(self.body, bg="#6b6b6b")
        self.parent_area.pack(fill="x")
        self.add_parent()
        self._button(self.body, "Добавить родителя", self.add_parent).pack(
            anchor="w", pady=(8, 16), ipadx=20
        )
        self._heading(self.body, "Направления обучения")
        self.direction_area = tk.Frame(self.body, bg="#6b6b6b")
        self.direction_area.pack(fill="x")
        self.add_direction()
        self._button(self.body, "Добавить направление", self.add_direction).pack(
            anchor="w", pady=8, ipadx=20
        )
        save_text = "Сохранить"
        save_width = 141
        if on_lookup is not None:
            save_text = "Сохранить изменения"
            save_width = 172
        self._button(panel, save_text, self._save).place(
            relx=1, x=-171 - save_width, rely=1, y=-45, width=save_width, height=32
        )
        self._button(panel, "Отмена", on_cancel).place(
            relx=1, x=-161, rely=1, y=-45, width=141, height=32
        )
        if record is not None:
            self._fill(record)
        self.original_data = self._get_data()

    def _label(self, parent, text, size=14):
        """Размещение подписи на форме."""
        return tk.Label(
            parent,
            text=text,
            font=(self.family, -size),
            bg="#6b6b6b",
            fg="white",
            anchor="w",
            padx=0,
            pady=0,
        )

    def _heading(self, parent, text):
        """Размещение заголовка раздела формы."""
        self._label(parent, text, 16).pack(anchor="w", pady=(0, 8))

    def _button(self, parent, text, command):
        """Создание кнопки с обработчиком нажатия."""
        return tk.Button(
            parent,
            text=text,
            command=command,
            font=(self.family, -14),
            bg="#d9d9d9",
            fg="black",
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            pady=6,
        )

    def _scroll(self, event=None):
        """Обновление области прокрутки формы."""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _resize(self, event):
        """Подстройка содержимого под размер окна."""
        self.canvas.itemconfigure(self.window, width=event.width)

    def _contacts(self, parent, is_parent):
        """Создание полей имени, телефона и мессенджера."""
        row = tk.Frame(parent, bg="#6b6b6b")
        row.pack(fill="x", pady=(0, 8))
        names = ["ФИО", "Телефон ученика", "Мессенджер", "Контакт в мессенджере"]
        widths = [318, 218, 190, 330]
        if is_parent:
            names = [
                "ФИО родителя",
                "Телефон родителя",
                "Мессенджер",
                "Контакт в мессенджере",
            ]
            widths = [318, 196, 130, 260]
        hints = [
            "Введите ФИО",
            "Номер телефона",
            "Выберите",
            "Имя пользователя или телефон",
        ]
        keys = ["full_name", "phone", "messenger_type", "messenger_contact"]
        fields = {}
        for column in range(4):
            row.columnconfigure(column, weight=widths[column], uniform="fields")
            self._label(row, names[column]).grid(
                row=0, column=column, sticky="w", pady=(0, 6)
            )
            choices = None
            if column == 2:
                choices = ["", "Telegram", "MAX", "WhatsApp", "Viber", "Другое"]
            field = FormInput(row, self.family, hints[column], choices)
            field.grid(row=1, column=column, sticky="ew", padx=(0, 12))
            fields[keys[column]] = field
        if is_parent:
            row.columnconfigure(4, weight=140, uniform="fields")
            self._label(row, "Основной контакт").grid(row=0, column=4, sticky="w")
            tk.Radiobutton(
                row,
                text="Да",
                variable=self.primary,
                value=len(self.parents),
                bg="#6b6b6b",
                fg="white",
                selectcolor="#6b6b6b",
                activebackground="#6b6b6b",
                activeforeground="white",
                font=(self.family, -14),
                highlightthickness=0,
            ).grid(row=1, column=4, sticky="w")
        return fields

    def add_parent(self, data=None):
        """Добавление строки контактов родителя."""
        fields = self._contacts(self.parent_area, True)
        self.parents.append(fields)
        self.parent_ids.append(None if data is None else data["parent_id"])
        if data is not None:
            for key, field in fields.items():
                field.set(data[key])
            if data["is_primary"]:
                self.primary.set(len(self.parents) - 1)

    def add_direction(self, data=None):
        """Добавление строки предмета, цели и тарифа."""
        row = tk.Frame(self.direction_area, bg="#6b6b6b")
        row.pack(fill="x", pady=(0, 8))
        labels = ["Предмет", "Цель подготовки", "Цена за 60 минут, ₽"]
        hints = [
            "Введите название предмета",
            "Выберите цель подготовки",
            "Введите цену в рублях",
        ]
        widths = [396, 396, 276]
        fields = []
        for column in range(3):
            row.columnconfigure(column, weight=widths[column], uniform="fields")
            self._label(row, labels[column]).grid(
                row=0, column=column, sticky="w", pady=(0, 6)
            )
            choices = None
            if column == 1:
                choices = [
                    "",
                    "ОГЭ",
                    "ЕГЭ",
                    "Повышение успеваемости (ПУ)",
                    "Подготовка к олимпиаде",
                    "Другое",
                ]
            field = FormInput(row, self.family, hints[column], choices)
            field.grid(row=1, column=column, sticky="ew", padx=(0, 12))
            fields.append(field)
        self.directions.append(fields)
        self.enrollment_ids.append(None if data is None else data["enrollment_id"])
        if data is not None:
            fields[0].set(data["subject_name"])
            fields[1].set(data["preparation_goal"])
            fields[2].set(data["price"])

    def _get_data(self):
        """Сбор значений формы для сохранения карточки."""
        student = {}
        for key, field in self.student.items():
            student[key] = field.get()
        student["is_archived"] = self.status.get() == "Архивный"
        parents = []
        for number, fields in enumerate(self.parents):
            parent = {}
            for key, field in fields.items():
                parent[key] = field.get()
            parent["is_primary"] = self.primary.get() == number
            parent["parent_id"] = self.parent_ids[number]
            parents.append(parent)
        directions = []
        for number, fields in enumerate(self.directions):
            directions.append(
                {
                    "subject_name": fields[0].get(),
                    "enrollment_id": self.enrollment_ids[number],
                    "preparation_goal": fields[1].get(),
                    "price": fields[2].get(),
                }
            )
        return {"student": student, "parents": parents, "enrollments": directions}

    def _save(self):
        """Передача заполненных данных обработчику сохранения."""
        self.on_save(self._get_data())

    def _lookup(self, event=None):
        """Поиск существующей карточки по введённому ID."""
        self.on_lookup(self.lookup.get())

    def has_changes(self):
        """Проверка изменений относительно исходной карточки."""
        return self._get_data() != self.original_data

    def _fill(self, record):
        """Загрузка карточки в поля формы."""
        self.student_id = record["student_id"]
        for key, field in self.student.items():
            field.set(record["student"][key])
        status = "Активный"
        if record["student"]["is_archived"]:
            status = "Архивный"
        self.status.set(status)
        if self.on_lookup is not None:
            self.lookup.set(str(self.student_id))

        for widget in self.parent_area.winfo_children():
            widget.destroy()
        self.parents = []
        self.parent_ids = []
        self.primary.set(-1)
        for row in record["parents"]:
            self.add_parent(row)
        if not self.parents:
            self.add_parent()

        for widget in self.direction_area.winfo_children():
            widget.destroy()
        self.directions = []
        self.enrollment_ids = []
        for row in record["enrollments"]:
            self.add_direction(row)
        if not self.directions:
            self.add_direction()
