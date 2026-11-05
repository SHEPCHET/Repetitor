"""Отчёт для родителей и предпросмотр."""

import tkinter as tk
from tkinter import ttk


def student_label(student):
    text = str(student.student_id).zfill(5) + " — " + student.full_name
    if student.is_archived:
        text += " (архив)"
    return text


def report_money(amount):
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    return sign + str(amount // 100) + "," + str(amount % 100).zfill(2) + " ₽"


def balance_text(amount):
    if amount > 0:
        return "Долг: " + report_money(amount)
    if amount < 0:
        return "Переплата: " + report_money(-amount)
    return report_money(0)


class DateField(tk.Frame):
    def __init__(self, parent, variable, family):
        super().__init__(parent, bg="#a1a1a1")
        self.variable = variable
        self.entry = tk.Entry(self, textvariable=variable, font=(family, -14),
                              bg="#a1a1a1", fg="white", insertbackground="white",
                              borderwidth=0, relief="flat")
        self.entry.pack(fill="both", expand=True, padx=10)
        self.hint = tk.Label(self, text="дд.мм.гггг", font=(family, -14),
                             bg="#a1a1a1", fg="white", anchor="w", padx=0)
        self.hint.bind("<Button-1>", lambda event: self.entry.focus_set())
        self.bind("<Button-1>", lambda event: self.entry.focus_set())
        self.entry.bind("<FocusIn>", self._hint)
        self.entry.bind("<FocusOut>", self._hint)
        variable.trace_add("write", self._hint)
        self._hint()

    def _hint(self, *args):
        if not self.variable.get() and self.focus_get() != self.entry:
            self.hint.place(x=10, y=0, relwidth=1, width=-20, relheight=1)
        else:
            self.hint.place_forget()


class ReportsView(tk.Frame):
    def __init__(self, parent, family, load_students, generate, save_report):
        super().__init__(parent, bg="#d9d9d9")
        self.family = family
        self.load_students, self.on_generate, self.on_save = load_students, generate, save_report
        self.students, self.shown_students = [], []
        self.report = None
        self.query = tk.StringVar(master=self)
        self.date_from = tk.StringVar(master=self)
        self.date_to = tk.StringVar(master=self)
        tk.Label(self, text="Отчёт для родителей", font=(family, -20), bg="#d9d9d9", anchor="w",
                 padx=0).place(x=16, y=12, relwidth=1, width=-32, height=28)

        parameters = tk.Frame(self, bg="#d9d9d9")
        parameters.place(x=16, y=52, relwidth=1, width=-32, height=84)
        for column, weight in enumerate([42, 16, 16, 21]):
            parameters.columnconfigure(column, weight=weight, minsize=[240, 125, 125, 180][column])
        for column, label in enumerate(["Ученик", "Период с", "По"]):
            tk.Label(parameters, text=label, font=(family, -14), bg="#d9d9d9", anchor="w", padx=0).grid(
                row=0, column=column, sticky="ew", padx=(0, 18) if column < 3 else 0)
        style = ttk.Style(self)
        style.configure("Report.TCombobox", padding=(10, 0), fieldbackground="#a1a1a1",
                        background="#a1a1a1", foreground="white", borderwidth=0,
                        bordercolor="#a1a1a1", lightcolor="#a1a1a1", darkcolor="#a1a1a1")
        style.map("Report.TCombobox", fieldbackground=[("focus", "#a1a1a1")],
                  foreground=[("focus", "white")], selectbackground=[("focus", "#787878")],
                  selectforeground=[("focus", "white")])
        student_area = tk.Frame(parameters, bg="#a1a1a1", height=32)
        student_area.grid(row=1, column=0, sticky="ew", padx=(0, 18), pady=(6, 8))
        self.student_combo = ttk.Combobox(student_area, textvariable=self.query, style="Report.TCombobox",
                                          font=(family, -14), height=12)
        self.student_combo.place(x=0, y=0, relwidth=1, relheight=1)
        self.hint = tk.Label(student_area, text="Поиск ученика по ФИО или ID", font=(family, -14),
                             bg="#a1a1a1", fg="white", anchor="w", padx=0)
        self.hint.bind("<Button-1>", lambda event: self.student_combo.focus_set())
        self.student_combo.bind("<FocusIn>", self._student_hint)
        self.student_combo.bind("<FocusOut>", self._student_hint)
        self.start_field = DateField(parameters, self.date_from, family)
        self.start_field.grid(row=1, column=1, sticky="nsew", padx=(0, 18), pady=(6, 8))
        self.end_field = DateField(parameters, self.date_to, family)
        self.end_field.grid(row=1, column=2, sticky="nsew", padx=(0, 18), pady=(6, 8))
        self.generate_button = self._button(parameters, "Сформировать отчёт", self.generate)
        self.generate_button.grid(row=1, column=3, sticky="nsew", pady=(6, 8))
        tk.Label(parameters, text="Поиск среди всех учеников, включая архивных", font=(family, -12),
                 bg="#d9d9d9", fg="#555555", anchor="w", padx=0).grid(row=2, column=0, sticky="ew")
        tk.Label(parameters, text="Обе даты включительно · время МСК", font=(family, -12),
                 bg="#d9d9d9", fg="#555555", anchor="w", padx=0).grid(row=2, column=1, columnspan=3, sticky="ew")

        tk.Label(self, text="Предпросмотр отчёта", font=(family, -16), bg="#d9d9d9", anchor="w",
                 padx=0).place(x=16, y=148, width=250, height=24)
        self.scroll_hint = tk.Label(self, text="Прокрутите документ: оплаты и баланс ↓",
                                     font=(family, -12), bg="#d9d9d9", fg="#555555", anchor="e", padx=0)
        self.preview = tk.Frame(self, bg="white")
        self.preview.place(x=16, y=180, relwidth=1, width=-32, relheight=1, height=-246)
        self.canvas = tk.Canvas(self.preview, bg="white", highlightthickness=0)
        self.canvas.place(x=0, y=0, relwidth=1, width=-14, relheight=1, height=-14)
        self.body = tk.Frame(self.canvas, bg="white", padx=24, pady=22)
        self.body_window = self.canvas.create_window(0, 0, anchor="nw", window=self.body)
        scrollbar = ttk.Scrollbar(self.preview, orient="vertical", command=self.canvas.yview)
        scrollbar.place(relx=1, x=-14, y=0, width=14, relheight=1, height=-14)
        horizontal = ttk.Scrollbar(self.preview, orient="horizontal", command=self.canvas.xview)
        horizontal.place(x=0, rely=1, y=-14, relwidth=1, width=-14, height=14)
        self.canvas.configure(yscrollcommand=scrollbar.set, xscrollcommand=horizontal.set)
        self.canvas.bind("<Configure>", self._resize)
        self.body.bind("<Configure>", self._scroll_region)
        self.canvas.bind("<MouseWheel>", self._wheel)
        self.empty = tk.Frame(self.preview, bg="white")
        for y, text, size, colour in [(-30, "Отчёт ещё не сформирован", 20, "black"),
                                       (4, "Выберите ученика и период", 14, "#555555"),
                                       (34, "Затем нажмите «Сформировать отчёт»", 14, "#555555")]:
            tk.Label(self.empty, text=text, font=(family, -size), bg="white", fg=colour).place(
                relx=0.5, rely=0.5, y=y, anchor="center")
        self.status = tk.Label(self, text="Выберите ученика и период", font=(family, -14),
                               bg="#d9d9d9", fg="#555555", anchor="w", padx=0)
        self.status.place(x=16, rely=1, y=-44, relwidth=1, width=-230, height=32)
        self.save_button = self._button(self, "Сохранить отчёт", self.save)
        self.save_button.place(relx=1, x=-206, rely=1, y=-44, width=190, height=32)
        self.save_button.configure(state="disabled", bg="#b2b2b2")
        self.empty.place(x=0, y=0, relwidth=1, relheight=1)
        self._student_hint()
        for variable in [self.query, self.date_from, self.date_to]:
            variable.trace_add("write", self._parameters_changed)
        self.bind("<Map>", self.refresh_students)

    def _button(self, parent, text, command):
        return tk.Button(parent, text=text, command=command, font=(self.family, -15),
                         bg="#787878", fg="white", disabledforeground="white",
                         activebackground="#6b6b6b", activeforeground="white", borderwidth=0,
                         relief="flat", cursor="hand2", padx=4, pady=0)

    def _student_hint(self, event=None):
        if not self.query.get() and self.focus_get() != self.student_combo:
            self.hint.place(x=10, y=0, relwidth=1, width=-32, relheight=1)
        else:
            self.hint.place_forget()

    def refresh_students(self, event=None):
        students = self.load_students()
        if students is not None:
            self.students = students
            self._filter_students()

    def _filter_students(self):
        query = self.query.get().strip().casefold()
        self.shown_students = []
        for student in self.students:
            if not query or query in student_label(student).casefold():
                self.shown_students.append(student)
        self.student_combo.configure(values=[student_label(student) for student in self.shown_students])

    def _parameters_changed(self, *args):
        self._student_hint()
        self._filter_students()
        if self.report is not None:
            self._clear_report()
            self.status.configure(text="Параметры изменены. Сформируйте отчёт заново.")

    def _clear_report(self):
        self.report = None
        for widget in self.body.winfo_children():
            widget.destroy()
        self.save_button.configure(state="disabled", bg="#b2b2b2")
        self.empty.place(x=0, y=0, relwidth=1, relheight=1)
        self.empty.lift()
        self.scroll_hint.place_forget()
        self.canvas.yview_moveto(0)

    def generate(self):
        index = self.student_combo.current()
        query = self.query.get().strip()
        if index >= 0:
            query = str(self.shown_students[index].student_id)
        elif " — " in query and query.split(" — ", 1)[0].isdecimal():
            query = query.split(" — ", 1)[0]
        self._clear_report()
        result = self.on_generate(query, self.date_from.get().strip(), self.date_to.get().strip())
        if result is None:
            self.status.configure(text="Проверьте ученика и даты.")
            return
        self.report = result
        self._render(result["data"])
        self.empty.place_forget()
        self.save_button.configure(state="normal", bg="#787878")
        self.scroll_hint.place(relx=1, x=-16, y=148, anchor="ne", width=370, height=24)
        self.status.configure(text="Отчёт сформирован. Можно сохранить в TXT.")
        self.canvas.yview_moveto(0)
        self.canvas.xview_moveto(0)

    def _text(self, text, size=14, gap=8):
        label = tk.Label(self.body, text=text, font=(self.family, -size), bg="white", anchor="w",
                         justify="left", wraplength=960, padx=0, pady=0)
        label.pack(fill="x", pady=(0, gap))
        label.bind("<MouseWheel>", self._wheel)

    def _table(self, captions, rows, widths):
        table = tk.Frame(self.body, bg="white")
        table.pack(fill="x", pady=(0, 12))
        for column, (caption, width) in enumerate(zip(captions, widths)):
            table.columnconfigure(column, minsize=width, weight=width)
            label = tk.Label(table, text=caption, font=(self.family, -14), bg="#d9d9d9", anchor="w",
                             wraplength=width - 16, padx=8, pady=10)
            label.grid(row=0, column=column, sticky="nsew")
            label.bind("<MouseWheel>", self._wheel)
        for row_number, values in enumerate(rows, 1):
            for column, value in enumerate(values):
                label = tk.Label(table, text=value, font=(self.family, -14), bg="white",
                                 anchor="nw", justify="left", wraplength=widths[column] - 16,
                                 padx=8, pady=8)
                label.grid(row=row_number * 2 - 1, column=column, sticky="nsew")
                label.bind("<MouseWheel>", self._wheel)
            tk.Frame(table, bg="#cccccc", height=1).grid(row=row_number * 2, column=0,
                                                        columnspan=len(widths), sticky="ew")

    def _render(self, data):
        self._text("Отчёт для родителей", 20, 12)
        self._text("Ученик: " + data["student"].full_name + " · ID: " + str(data["student"].student_id).zfill(5))
        self._text("Период: " + data["date_from"].strftime("%d.%m.%Y") + " — "
                   + data["date_to"].strftime("%d.%m.%Y") + ", включительно")
        self._text("Дата формирования: " + data["created"] + " · Время МСК")
        self._text("Баланс на начало периода: " + balance_text(data["opening"]), 14, 18)
        self._text("Проведённые занятия", 18, 10)
        rows = []
        for item in data["lessons"]:
            lesson = item["lesson"]
            when = lesson.starts_at.strftime("%H:%M") + "–" + lesson.ends_at.strftime("%H:%M")
            if lesson.starts_at.date() != lesson.ends_at.date():
                when = lesson.starts_at.strftime("%d.%m %H:%M") + "–" + lesson.ends_at.strftime("%d.%m %H:%M")
            rows.append([lesson.starts_at.strftime("%d.%m.%Y"), when, item["subject"], item["goal"],
                         "; ".join(lesson.topics) if lesson.topics else "Темы не указаны",
                         report_money(lesson.price_kopecks)])
        if rows:
            self._table(["Дата", "Время, МСК", "Предмет", "Цель", "Пройденные темы", "Стоимость"],
                        rows, [95, 110, 150, 150, 310, 135])
        else:
            self._text("Проведённых занятий за период нет.")
        self._text("Количество занятий: " + str(len(data["lessons"])) + " · Начислено за период: "
                   + report_money(data["charged"]), 14, 20)
        self._text("Оплаты", 18, 10)
        rows = []
        for payment in data["payments"]:
            rows.append([payment.paid_at.strftime("%d.%m.%Y"), payment.paid_at.strftime("%H:%M:%S"),
                         report_money(payment.amount_kopecks)])
        if rows:
            self._table(["Дата получения платежа", "Время получения, МСК", "Сумма"], rows, [350, 350, 250])
        else:
            self._text("Оплат за период нет.")
        self._text("Получено за период: " + report_money(data["received"]), 14, 18)
        self._text("Баланс на конец периода: " + balance_text(data["closing"]), 16, 8)
        self._resize()

    def save(self):
        if self.report is None:
            return
        data = self.report["data"]
        filename = ("report_" + str(data["student"].student_id) + "_"
                    + data["date_from"].strftime("%Y%m%d") + "_"
                    + data["date_to"].strftime("%Y%m%d") + ".txt")
        if self.on_save(self.report["text"], filename):
            self.status.configure(text="Отчёт сохранён.")

    def _resize(self, event=None):
        self.canvas.itemconfigure(self.body_window, width=max(1000, self.canvas.winfo_width()))
        self._scroll_region()

    def _scroll_region(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _wheel(self, event):
        if event.delta:
            self.canvas.yview_scroll(-3 if event.delta > 0 else 3, "units")
        return "break"
