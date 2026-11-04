"""Список учеников и поиск."""

import tkinter as tk


class StudentsView(tk.Frame):
    """Карточки учеников из базы."""

    def __init__(self, parent, family, load_students):
        """Создание вкладки."""
        super().__init__(parent, bg="#d9d9d9")
        self.family = family
        self.load_students = load_students
        self.query = tk.StringVar(master=self)
        self.selected_id = None
        self.headers = {}
        self.archive_mode = False
        self.search_y = 8

        actions = [
            ("Добавить ученика", 11, 30),
            ("Изменить карточку", 52, 30),
            ("Переместить в\nАрхив", 93, 35)
        ]
        for text, y, height in actions:
            button = self._button(text)
            if text == "Добавить ученика":
                self.add_button = button
            elif text == "Изменить карточку":
                self.edit_button = button
            else:
                self.move_button = button
                button.configure(fg="white", activeforeground="white",
                                 activebackground="#787878", cursor="hand2")
            button.place(x=6, y=y, width=151, height=height)

        self.archive_button = self._button("К архиву")
        self.archive_button.configure(
            state="normal", command=self.toggle_archive, fg="white",
            activeforeground="white", activebackground="#787878", cursor="hand2"
        )
        self.archive_button.place(x=6, rely=1, y=-46, width=151, height=30)

        area = tk.Frame(self, bg="white")
        area.place(x=165, y=0, relwidth=1, width=-165, relheight=1)
        self.archive_title = tk.Label(
            area, text="Архив", font=(family, -20), bg="white",
            fg="black", anchor="w", padx=0, pady=0
        )

        self.entry = tk.Entry(
            area, textvariable=self.query, font=(family, -14),
            bg="#a2a2a2", fg="white", insertbackground="white",
            relief="flat", borderwidth=0, highlightthickness=0
        )
        self.entry.place(x=14, y=8, relwidth=1, width=-28, height=27)

        self.hint = tk.Label(
            area, text="Поиск по ФИО или ID", font=(family, -14),
            bg="#a2a2a2", fg="#cacaca", anchor="w", cursor="xterm"
        )
        self.hint.bind("<Button-1>", lambda event: self.entry.focus_set())
        self.entry.bind("<FocusIn>", self._hint)
        self.entry.bind("<FocusOut>", self._hint)

        holder = tk.Frame(area, bg="white")
        self.holder = holder
        holder.place(x=10, y=48, relwidth=1, width=-10,
                     relheight=1, height=-48)
        holder.rowconfigure(0, weight=1)
        holder.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(holder, bg="white", highlightthickness=0)
        vertical = tk.Scrollbar(holder, command=self.canvas.yview)
        horizontal = tk.Scrollbar(
            holder, orient="horizontal", command=self.canvas.xview
        )
        self.canvas.configure(
            yscrollcommand=vertical.set, xscrollcommand=horizontal.set
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")

        self.cards = tk.Frame(self.canvas, bg="white")
        self.canvas.create_window(0, 0, window=self.cards, anchor="nw")
        self.cards.bind("<Configure>", self._scroll)
        self.query.trace_add("write", self.refresh)
        self.bind("<Map>", self.refresh)
        self._hint()

    def _button(self, text):
        """Кнопки для следующих шагов."""
        return tk.Button(
            self, text=text, font=(self.family, -15), bg="#787878",
            disabledforeground="white", relief="flat",
            borderwidth=0, state="disabled"
        )

    def _hint(self, event=None):
        """Подсказка поиска."""
        if self.query.get() == "" and self.focus_get() != self.entry:
            self.hint.place(x=18, y=self.search_y, width=175, height=27)
        else:
            self.hint.place_forget()

    def _scroll(self, event=None):
        """Размер прокручиваемой области."""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _text(self, value):
        """Пустые значения."""
        if value is None or value == "":
            return "Не указан"
        return str(value)

    def _column(self, parent, number, rows, student_id):
        """Один столбец карточки."""
        column = tk.Frame(parent, bg="black", width=204, height=296)
        column.grid(row=0, column=number, sticky="nw")

        colors = ["#a1a1a1", "#d9d9d9", "#f5f5f5",
                  "#d9d9d9", "#f5f5f5", "#d9d9d9"]
        for row, text in enumerate(rows):
            label = tk.Label(
                column, text=text, font=(self.family, -14),
                bg=colors[row], fg="black", wraplength=194,
                borderwidth=0, padx=3, pady=0, cursor="hand2",
                takefocus=(row == 0)
            )
            label.place(x=1, y=1 + row * 49, width=202, height=48)
            label.bind("<Button-1>", lambda event, sid=student_id: self.select_student(sid))
            label.bind("<Return>", lambda event, sid=student_id: self.select_student(sid))
            label.bind("<space>", lambda event, sid=student_id: self.select_student(sid))
            if row == 0:
                self.headers.setdefault(student_id, []).append(label)

    def select_student(self, student_id):
        """Выбор карточки для изменения."""
        self.selected_id = student_id if student_id in self.headers else None
        for sid, labels in self.headers.items():
            for label in labels:
                if sid == self.selected_id:
                    label.configure(bg="#787878", fg="white")
                else:
                    label.configure(bg="#a1a1a1", fg="black")
        state = "disabled" if self.selected_id is None else "normal"
        self.edit_button.configure(state=state)
        self.move_button.configure(state=state)

    def toggle_archive(self):
        """Переход между учениками и архивом."""
        self.set_archive_mode(not self.archive_mode)

    def set_archive_mode(self, archived):
        """Обновление вида и списка."""
        self.archive_mode = archived
        self.selected_id = None
        self.search_y = 8
        if archived:
            self.archive_title.place(x=14, y=10, height=28)
            self.search_y = 41
            self.move_button.configure(text="Восстановить\nученика")
            self.archive_button.configure(
                text="К ученикам", highlightthickness=1,
                highlightbackground="#dd1eb4", highlightcolor="#dd1eb4"
            )
        else:
            self.archive_title.place_forget()
            self.move_button.configure(text="Переместить в\nАрхив")
            self.archive_button.configure(text="К архиву", highlightthickness=0)
        self.entry.place_configure(y=self.search_y)
        top = self.search_y + 40
        self.holder.place_configure(y=top, height=-top)
        self.query.set("")

    def refresh(self, *args):
        """Обновление списка."""
        self._hint()
        items = self.load_students(self.query.get(), self.archive_mode)
        if items is None:
            return

        for widget in self.cards.winfo_children():
            widget.destroy()
        self.headers = {}

        if not items:
            text = "Ученики не найдены."
            if self.query.get().strip() == "":
                text = "Активных учеников пока нет."
                if self.archive_mode:
                    text = "Архив пуст."
            tk.Label(
                self.cards, text=text, font=(self.family, -16), bg="white"
            ).pack(padx=10, pady=10)

        for item in items:
            self._card(item)
        self.select_student(self.selected_id)

        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)
        self.cards.update_idletasks()
        self._scroll()

    def _card(self, item):
        """Ученик, родители и предметы."""
        student = item["student"]
        card = tk.Frame(self.cards, bg="white")
        card.pack(anchor="nw", pady=(0, 8))
        status = "Активный"
        if student.is_archived:
            status = "В архиве"

        self._column(card, 0, [
            "ID: " + str(student.student_id).zfill(5),
            "ФИО: " + student.full_name,
            "Телефон: " + self._text(student.phone),
            "Мессенджер: " + self._text(student.messenger_type),
            "Контакт в мессенджере: " + self._text(student.messenger_contact),
            "Статус: " + status
        ], student.student_id)

        column = 1
        for number, (parent, is_primary) in enumerate(item["parents"], 1):
            primary = "Нет"
            if is_primary:
                primary = "Да"
            self._column(card, column, [
                "Родитель " + str(number),
                "ФИО родителя: " + parent.full_name,
                "Телефон родителя: " + self._text(parent.phone),
                "Мессенджер родителя: " + self._text(parent.messenger_type),
                "Контакт в мессенджере: " + self._text(parent.messenger_contact),
                "Основной контакт: " + primary
            ], student.student_id)
            column += 1

        for number, (enrollment, subject) in enumerate(item["enrollments"], 1):
            price = enrollment.price_60_kopecks
            money = str(price // 100) + "," + str(price % 100).zfill(2)
            self._column(card, column, [
                "Предмет " + str(number),
                "Предмет: " + subject,
                "Цель: " + enrollment.preparation_goal,
                "Цена за 60 мин.: " + money + " руб.",
                "", ""
            ], student.student_id)
            column += 1
