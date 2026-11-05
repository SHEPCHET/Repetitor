"""История, планы и темы занятий."""

import tkinter as tk
from tkinter import ttk, messagebox, font


def topics_from_text(text):
    """Одна тема на строку, пустые строки пропускаются."""
    return [line.strip() for line in text.splitlines() if line.strip()]


class LessonsView(tk.Frame):
    """Журнал занятий и редактирование пройденных тем."""

    def __init__(self, parent, family, load_items, save_topics, on_pay):
        """Подготовка данных и элементов объекта."""
        super().__init__(parent, bg="#d9d9d9")
        self.family = family
        self.load_items, self.on_save, self.on_pay = load_items, save_topics, on_pay
        self.planned = False
        self.archived = False
        self.group_students = False
        self.student_id = None
        self.selected_id = None
        self.highlighted_id = None
        self.pending_id = None
        self.editing = False
        self.items = []
        self.editors = {}
        self.original = {}
        self.row_widgets = {}
        self.positions = {}
        self.query = tk.StringVar(master=self)
        self.text_font = font.Font(self, family=family, size=-14)

        self.group_button = self._button("По ученикам", self.toggle_group)
        self.group_button.place(x=6, y=8, width=151, height=30)
        self.topics_button = self._button("Темы занятия", self.edit_topics)
        self.topics_button.place(x=6, y=46, width=151, height=30)
        self.period_button = self._button("К запланированным", self.toggle_period)
        self.period_button.place(x=6, rely=1, y=-94, width=151, height=30)
        self.archive_button = self._button("К архиву", self.toggle_archive)
        self.archive_button.place(x=6, rely=1, y=-38, width=151, height=30)

        right = tk.Frame(self, bg="white")
        right.place(x=166, y=0, relwidth=1, width=-166, relheight=1)
        self.search = tk.Entry(
            right,
            textvariable=self.query,
            font=(family, -14),
            bg="#a1a1a1",
            fg="white",
            insertbackground="white",
            borderwidth=0,
            relief="flat",
        )
        self.search.place(x=9, y=9, relwidth=1, width=-18, height=27)
        self.hint = tk.Label(
            right,
            text="Поиск ученика по ФИО или ID",
            font=(family, -14),
            bg="#a1a1a1",
            fg="#d9d9d9",
            anchor="w",
            padx=0,
        )
        self.hint.bind("<Button-1>", lambda event: self.search.focus_set())
        self.search.bind("<FocusIn>", self._hint)
        self.search.bind("<FocusOut>", self._hint)
        self.query.trace_add("write", self._search_changed)
        self._hint()

        self.panel = tk.Frame(right, bg="#d9d9d9")
        self.panel.place(x=9, y=49, relwidth=1, width=-18, relheight=1, height=-58)
        self.title = tk.Label(
            self.panel,
            text="История занятий",
            font=(family, -20),
            bg="#d9d9d9",
            anchor="w",
            padx=0,
        )
        self.title.place(x=16, y=8, relwidth=1, width=-32, height=28)
        self.help = tk.Label(
            self.panel,
            text="Одна тема на строку",
            font=(family, -12),
            bg="#d9d9d9",
            anchor="w",
            padx=0,
        )
        self.canvas = tk.Canvas(self.panel, bg="#d9d9d9", highlightthickness=0)
        self.canvas.place(x=16, y=48, relwidth=1, width=-32, relheight=1, height=-66)
        self.body = tk.Frame(self.canvas, bg="#d9d9d9")
        self.body_window = self.canvas.create_window(
            0, 0, window=self.body, anchor="nw"
        )
        self.vertical = ttk.Scrollbar(
            self.panel, orient="vertical", command=self.canvas.yview
        )
        self.vertical.place(relx=1, x=-14, y=48, width=14, relheight=1, height=-66)
        self.horizontal = ttk.Scrollbar(
            self.panel, orient="horizontal", command=self.canvas.xview
        )
        self.horizontal.place(x=16, rely=1, y=-16, relwidth=1, width=-32, height=14)
        self.canvas.configure(
            yscrollcommand=self.vertical.set, xscrollcommand=self.horizontal.set
        )
        self.body.bind("<Configure>", self._scroll_region)
        self.canvas.bind("<Configure>", self._resize)
        self.canvas.bind("<MouseWheel>", self._wheel)
        self.save_button = self._button("Сохранить", self.save)
        self.cancel_button = self._button("Отмена", self.cancel_edit)
        self.menu = tk.Menu(self, tearoff=False, font=(family, -14))
        self.menu.add_command(label="Оплатить занятие")
        self.bind("<Map>", self._mapped)
        self.root = self.winfo_toplevel()
        self.click_binding = self.root.bind("<ButtonPress>", self._any_click, add="+")
        self.timer = self.after(30000, self._tick)

    def _button(self, text, command):
        """Создание кнопки с обработчиком нажатия."""
        return tk.Button(
            self,
            text=text,
            command=command,
            font=(self.family, -15),
            bg="#787878",
            fg="white",
            activebackground="#6b6b6b",
            activeforeground="white",
            relief="flat",
            borderwidth=0,
            disabledforeground="#bdbdbd",
            cursor="hand2",
            padx=0,
            pady=0,
        )

    def _hint(self, event=None):
        """Показ подсказки в пустом поле."""
        if not self.query.get() and self.focus_get() != self.search:
            self.hint.place(x=19, y=12, relwidth=1, width=-38, height=21)
        else:
            self.hint.place_forget()

    def _search_changed(self, *args):
        """Обновление результатов после изменения поиска."""
        self._hint()
        self.student_id = None
        self.pending_id, self.highlighted_id = None, None
        self.refresh()

    def _mapped(self, event=None):
        """Обновление данных при открытии вкладки."""
        if not self.editing:
            self.refresh()

    def _tick(self):
        """Периодическое обновление статусов завершившихся занятий."""
        self.timer = None
        if self.winfo_ismapped() and not self.editing:
            self.refresh(silent=True)
        else:
            self.load_items(self.query.get(), self.planned, self.archived, True)
        self.timer = self.after(30000, self._tick)

    def refresh(self, silent=False):
        """Обновление данных на экране."""
        if self.editing:
            return
        items = self.load_items(self.query.get(), self.planned, self.archived, silent)
        if items is None:
            self._render()
            return
        self.items = items
        if self.student_id is not None:
            self.items = [
                item for item in items if item["student"].student_id == self.student_id
            ]
        if not any(item["lesson"].lesson_id == self.selected_id for item in self.items):
            self.selected_id = None
        self._render()
        if self.pending_id is not None:
            self.select_lesson(self.pending_id)
            self.after_idle(self._see_pending)

    def _render(self):
        """Построение элементов экрана из полученных данных."""
        for row in range(self.body.grid_size()[1]):
            self.body.rowconfigure(row, minsize=0)
        for widget in self.body.winfo_children():
            widget.destroy()
        self.row_widgets, self.positions = {}, {}
        self.editors, self.original = {}, {}
        title = "Запланированные занятия" if self.planned else "История занятий"
        if self.archived:
            title = (
                "Запланированные занятия архивных учеников"
                if self.planned
                else "История архивных учеников"
            )
        self.title.configure(text=title)
        self.group_button.configure(
            text="Открыть весь список" if self.group_students else "По ученикам"
        )
        self.period_button.configure(
            text="К прошедшим" if self.planned else "К запланированным"
        )
        self.archive_button.configure(
            text="К занятиям" if self.archived else "К архиву"
        )
        self.topics_button.configure(
            state=(
                "disabled"
                if self.planned or not self.items or self.editing
                else "normal"
            )
        )
        self.search.configure(state="disabled" if self.editing else "normal")
        self.save_button.place_forget()
        self.cancel_button.place_forget()
        self.help.place_forget()
        if self.editing:
            self.help.place(
                in_=self.panel, x=16, y=37, height=18, relwidth=1, width=-32
            )
            self.canvas.place_configure(y=60, height=-116)
            self.vertical.place_configure(y=60, height=-116)
            self.horizontal.place_configure(y=-54)
            self.save_button.place(relx=1, x=-338, rely=1, y=-47, width=151, height=30)
            self.cancel_button.place(
                relx=1, x=-175, rely=1, y=-47, width=151, height=30
            )
        else:
            self.canvas.place_configure(y=48, height=-66)
            self.vertical.place_configure(y=48, height=-66)
            self.horizontal.place_configure(y=-16)

        widths = [140, 95, 120, 125, 266, 80, 116]
        captions = [
            "Имя / ID",
            "Дата и время",
            "Предмет",
            "Цель",
            "Темы",
            "Стоимость, ₽",
            "Оплата",
        ]
        if self.group_students:
            captions[0] = "Дата"
            captions[1] = "Время"
        for column, (width, caption) in enumerate(zip(widths, captions)):
            self.body.columnconfigure(column, minsize=width, weight=width)
            tk.Label(
                self.body,
                text=caption,
                bg="#d9d9d9",
                font=(self.family, -14),
                anchor="w",
                padx=0,
            ).grid(row=0, column=column, sticky="nsew", padx=3, pady=(0, 12))
        if not self.items:
            tk.Label(
                self.body,
                text="Занятий не найдено.",
                bg="#d9d9d9",
                font=(self.family, -14),
                anchor="w",
            ).grid(row=1, column=0, columnspan=7, sticky="ew", pady=10)
        items = self.items
        if self.group_students:
            items = sorted(
                items,
                key=lambda item: (
                    item["student"].full_name.casefold(),
                    item["student"].student_id,
                ),
            )
        previous_student = None
        row = 1
        for item in items:
            lesson, student = item["lesson"], item["student"]
            if self.group_students and student.student_id != previous_student:
                header = tk.Label(
                    self.body,
                    text="ID: "
                    + str(student.student_id).zfill(5)
                    + "     ФИО: "
                    + student.full_name,
                    font=(self.family, -14),
                    bg="#ededed",
                    anchor="w",
                    padx=8,
                    cursor="hand2",
                )
                header.grid(row=row, column=0, columnspan=7, sticky="ew", pady=(5, 8))
                header.bind(
                    "<Button-1>",
                    lambda event, sid=student.student_id: self.show_student(sid),
                )
                header.bind("<MouseWheel>", self._wheel)
                previous_student = student.student_id
                row += 1
            topics = "\n".join(lesson.topics) if not self.planned else ""
            start = lesson.starts_at
            end = lesson.ends_at
            date_text = start.strftime("%d.%m.%Y")
            time_text = start.strftime("%H:%M") + "–" + end.strftime("%H:%M")
            if start.date() != end.date():
                time_text = (
                    start.strftime("%d.%m %H:%M") + "–" + end.strftime("%d.%m %H:%M")
                )
            money = (
                str(lesson.price_kopecks // 100)
                + ","
                + str(lesson.price_kopecks % 100).zfill(2)
            )
            values = [
                student.full_name + "\n(" + str(student.student_id).zfill(5) + ")",
                date_text + "\n" + time_text,
                item["subject"],
                item["goal"],
                topics or "—",
                money,
                "Оплачено" if item["paid"] else "Ожидается",
            ]
            if self.group_students:
                values[0], values[1] = date_text, time_text
            height = 36
            for column, text in enumerate(values):
                lines = 0
                for line in text.splitlines():
                    lines += max(
                        1,
                        (self.text_font.measure(line) + widths[column] - 13)
                        // (widths[column] - 12),
                    )
                height = max(height, min(130, lines * 18 + 10))
            self.body.rowconfigure(row, minsize=height)
            widgets = []
            for column, value in enumerate(values):
                if column == 4:
                    background = "white" if self.editing else "#ededed"
                    if self.highlighted_id == lesson.lesson_id:
                        background = "#bdd7ff"
                    widget = tk.Text(
                        self.body,
                        font=(self.family, -14),
                        bg=background,
                        fg="black",
                        height=1,
                        width=1,
                        wrap="word",
                        borderwidth=1,
                        relief="solid",
                        padx=4,
                        pady=3,
                    )
                    widget.insert("1.0", topics if self.editing else value)
                    if self.editing:
                        self.editors[lesson.lesson_id] = widget
                        self.original[lesson.lesson_id] = list(lesson.topics)
                    else:
                        widget.tag_configure("center", justify="center")
                        widget.tag_add("center", "1.0", "end")
                        widget.configure(state="disabled", relief="flat", borderwidth=0)
                        widget.bind(
                            "<Button-3>",
                            lambda event, current=item: self._menu(event, current),
                        )
                    widget.bind(
                        "<MouseWheel>",
                        lambda event, current=widget: self._text_wheel(event, current),
                    )
                else:
                    widget = tk.Label(
                        self.body,
                        text=value,
                        font=(self.family, -14),
                        bg=(
                            "#bdd7ff"
                            if self.highlighted_id == lesson.lesson_id
                            else "#ededed"
                        ),
                        wraplength=widths[column] - 12,
                        borderwidth=0,
                        highlightthickness=1,
                        highlightbackground="#ededed",
                        padx=4,
                        pady=3,
                    )
                    widget.bind("<MouseWheel>", self._wheel)
                    widget.bind(
                        "<Button-3>",
                        lambda event, current=item: self._menu(event, current),
                    )
                widget.grid(row=row, column=column, sticky="nsew", padx=3, pady=4)
                widget.bind(
                    "<Button-1>",
                    lambda event, lid=lesson.lesson_id: self.select_lesson(lid),
                    add="+",
                )
                widgets.append(widget)
            self.row_widgets[lesson.lesson_id] = widgets
            self.positions[lesson.lesson_id] = row
            row += 1
        self._resize()
        self.select_lesson(self.selected_id)

    def select_lesson(self, lesson_id):
        """Выбор занятия и обновление доступных действий."""
        self.selected_id = lesson_id
        for saved_id, widgets in self.row_widgets.items():
            for widget in widgets:
                if isinstance(widget, tk.Label):
                    widget.configure(
                        highlightbackground=(
                            "#555555" if saved_id == lesson_id else "#ededed"
                        )
                    )

    def _resize(self, event=None):
        """Подстройка содержимого под размер окна."""
        self.canvas.itemconfigure(
            self.body_window, width=max(984, self.canvas.winfo_width())
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

    def _text_wheel(self, event, widget):
        """Прокрутка поля тем вместо всего журнала."""
        if widget.yview() == (0.0, 1.0):
            return self._wheel(event)
        if event.delta:
            widget.yview_scroll(-3 if event.delta > 0 else 3, "units")
        return "break"

    def _menu(self, event, item):
        """Открытие меню действий над выбранным занятием."""
        self.select_lesson(item["lesson"].lesson_id)
        can_pay = (
            not self.editing and not item["paid"] and item["lesson"].price_kopecks > 0
        )
        self.menu.entryconfigure(
            0,
            state="normal" if can_pay else "disabled",
            command=lambda: self.on_pay(item["lesson"].lesson_id),
        )
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()
        return "break"

    def leave_editing(self):
        """Проверка несохранённых тем перед уходом с экрана."""
        if not self.editing:
            return True
        if self.changes() and not messagebox.askyesno(
            "Темы занятия", "Отменить несохранённые изменения тем?", parent=self
        ):
            return False
        self.editing = False
        self.editors = {}
        self.original = {}
        self.refresh()
        return True

    def toggle_group(self):
        """Переключение группировки занятий по ученикам."""
        if not self.leave_editing():
            return
        if self.group_students:
            self.group_students, self.student_id = False, None
            self.query.set("")
        else:
            self.group_students = True
            for item in self.items:
                if item["lesson"].lesson_id == self.selected_id:
                    self.student_id = item["student"].student_id
                    break
        self.refresh()

    def show_student(self, student_id):
        """Открытие журнала выбранного ученика."""
        if self.leave_editing():
            self.student_id = student_id
            self.refresh()

    def toggle_period(self):
        """Переключение проведённых и запланированных занятий."""
        if self.leave_editing():
            self.planned = not self.planned
            self.pending_id = None
            self.refresh()

    def toggle_archive(self):
        """Переключение активных и архивных учеников."""
        if self.leave_editing():
            self.archived = not self.archived
            self.planned = False
            self.group_students, self.student_id = False, None
            self.pending_id = None
            self.query.set("")
            self.refresh()

    def edit_topics(self):
        """Включение редактирования тем проведённых занятий."""
        if self.editing or self.planned or not self.items:
            return
        self.highlighted_id = None
        self.editing = True
        self._render()
        if self.selected_id in self.editors:
            self.editors[self.selected_id].focus_set()

    def changes(self):
        """Получение изменённых тем и их исходных значений."""
        result = {}
        for lesson_id, widget in self.editors.items():
            topics = topics_from_text(widget.get("1.0", "end-1c"))
            if topics != self.original[lesson_id]:
                result[lesson_id] = {
                    "topics": topics,
                    "original": self.original[lesson_id],
                }
        return result

    def save(self):
        """Сохранение подготовленных данных через обработчик экрана."""
        if not self.editing:
            return
        if self.on_save(self.changes()):
            self.editing = False
            self.refresh()

    def cancel_edit(self):
        """Отмена несохранённых изменений тем."""
        self.editing = False
        self.refresh()

    def open_student(self, student_id, archived, planned=False):
        """История ученика из списка балансов."""
        if not self.leave_editing():
            return False
        self.query.set("")
        self.planned, self.archived = planned, archived
        self.group_students, self.student_id = True, student_id
        self.selected_id = None
        self.pending_id, self.highlighted_id = None, None
        self.refresh()
        self.canvas.yview_moveto(0)
        return True

    def show_lesson(self, lesson_id, student_id, planned, archived):
        """Переход к выбранному занятию в журнале."""
        if not self.leave_editing():
            return False
        self.query.set("")
        self.planned, self.archived = planned, archived
        self.group_students, self.student_id = True, student_id
        self.pending_id, self.highlighted_id = lesson_id, lesson_id
        self.refresh()
        return True

    def _see_pending(self):
        """Прокрутка к занятию, выбранному при переходе."""
        if self.pending_id not in self.row_widgets:
            return
        self.update_idletasks()
        widget = self.row_widgets[self.pending_id][0]
        total = max(1, self.body.winfo_height())
        self.canvas.yview_moveto(widget.winfo_y() / total)

    def _any_click(self, event=None):
        """Снятие выделения при нажатии за пределами строки."""
        if self.highlighted_id is not None:
            for widget in self.row_widgets.get(self.highlighted_id, []):
                widget.configure(bg="#ededed")
            self.highlighted_id = None
            self.pending_id = None

    def destroy(self):
        """Удаление окна и отключение его обработчиков."""
        if self.timer is not None:
            self.after_cancel(self.timer)
        self.root.unbind("<ButtonPress>", self.click_binding)
        super().destroy()
