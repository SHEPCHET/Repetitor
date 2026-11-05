"""Вкладка оплат по макетам."""

import tkinter as tk
from tkinter import ttk, font


def money_text(amount):
    sign = ""
    if amount < 0:
        sign = "-"
        amount = -amount
    return sign + str(amount // 100) + "," + str(amount % 100).zfill(2)


class PaymentsView(tk.Frame):
    def __init__(self, parent, family, load_items, show_student):
        super().__init__(parent, bg="#d9d9d9")
        self.family = family
        self.load_items, self.show_student = load_items, show_student
        self.balance_mode = False
        self.selected_id = None
        self.items = []
        self.row_widgets = {}
        self.query = tk.StringVar(master=self)
        self.text_font = font.Font(self, family=family, size=-14)
        self.main_button = self._button("Баланс учеников", self.main_action)
        self.main_button.place(x=6, y=8, width=151, height=30)
        self.back_button = self._button("К платежам", self.toggle_mode)

        right = tk.Frame(self, bg="white")
        right.place(x=166, y=0, relwidth=1, width=-166, relheight=1)
        self.search = tk.Entry(right, textvariable=self.query, font=(family, -14),
                               bg="#a1a1a1", fg="white", insertbackground="white",
                               borderwidth=0, relief="flat")
        self.search.place(x=9, y=9, relwidth=1, width=-18, height=27)
        self.hint = tk.Label(right, text="Поиск ученика по ФИО или ID", font=(family, -14),
                             bg="#a1a1a1", fg="#d9d9d9", anchor="w", padx=0)
        self.hint.bind("<Button-1>", lambda event: self.search.focus_set())
        self.search.bind("<FocusIn>", self._hint)
        self.search.bind("<FocusOut>", self._hint)
        self.query.trace_add("write", self._search_changed)
        self._hint()

        self.panel = tk.Frame(right, bg="#d9d9d9")
        self.panel.place(x=9, y=49, relwidth=1, width=-18, relheight=1, height=-58)
        self.title = tk.Label(self.panel, text="История платежей", font=(family, -20),
                              bg="#d9d9d9", anchor="w", padx=0)
        self.title.place(x=16, y=8, relwidth=1, width=-32, height=28)
        self.canvas = tk.Canvas(self.panel, bg="#d9d9d9", highlightthickness=0)
        self.canvas.place(x=16, y=48, relwidth=1, width=-32, relheight=1, height=-66)
        self.body = tk.Frame(self.canvas, bg="#d9d9d9")
        self.body_window = self.canvas.create_window(0, 0, window=self.body, anchor="nw")
        self.vertical = ttk.Scrollbar(self.panel, orient="vertical", command=self.canvas.yview)
        self.vertical.place(relx=1, x=-14, y=48, width=14, relheight=1, height=-66)
        self.horizontal = ttk.Scrollbar(self.panel, orient="horizontal", command=self.canvas.xview)
        self.horizontal.place(x=16, rely=1, y=-16, relwidth=1, width=-32, height=14)
        self.canvas.configure(yscrollcommand=self.vertical.set, xscrollcommand=self.horizontal.set)
        self.canvas.bind("<Configure>", self._resize)
        self.body.bind("<Configure>", self._scroll_region)
        self.canvas.bind("<MouseWheel>", self._wheel)
        self.bind("<Map>", self._mapped)

    def _button(self, text, command):
        return tk.Button(self, text=text, command=command, font=(self.family, -15),
                         bg="#787878", fg="white", activebackground="#6b6b6b",
                         activeforeground="white", relief="flat", borderwidth=0,
                         disabledforeground="#bdbdbd", cursor="hand2", padx=0, pady=0)

    def _hint(self, event=None):
        if not self.query.get() and self.focus_get() != self.search:
            self.hint.place(x=19, y=12, relwidth=1, width=-38, height=21)
        else:
            self.hint.place_forget()

    def _search_changed(self, *args):
        self._hint()
        self.selected_id = None
        self.refresh()
        self.canvas.yview_moveto(0)

    def _mapped(self, event=None):
        self.refresh()

    def refresh(self):
        items = self.load_items(self.query.get(), self.balance_mode)
        if items is None:
            self.items = []
        else:
            self.items = items
        if not any(self._key(item) == self.selected_id for item in self.items):
            self.selected_id = None
        self._render()

    def _key(self, item):
        if self.balance_mode:
            return item["student"].student_id
        return item["payment"].payment_id

    def _render(self):
        for row in range(self.body.grid_size()[1]):
            self.body.rowconfigure(row, minsize=0)
        for column in range(6):
            self.body.columnconfigure(column, minsize=0, weight=0)
        for widget in self.body.winfo_children():
            widget.destroy()
        self.row_widgets = {}
        self.title.configure(text="Баланс учеников" if self.balance_mode else "История платежей")
        self.main_button.configure(text="Показать занятия" if self.balance_mode else "Баланс учеников")
        if self.balance_mode:
            self.back_button.place(x=6, y=47, width=151, height=30)
            captions = ["Ученик: ФИО и ID", "Начислено, ₽", "Получено, ₽", "Долг, ₽", "Переплата, ₽"]
            widths = [220, 150, 150, 150, 150]
            self.body.columnconfigure(5, weight=1)
        else:
            self.back_button.place_forget()
            captions = ["ID платежа", "Ученик: ФИО и ID", "Дата и время платежа",
                        "Дата и время занятия", "Предмет / цель", "Сумма платежа, ₽"]
            widths = [90, 180, 180, 180, 180, 138]
        for column, (width, caption) in enumerate(zip(widths, captions)):
            self.body.columnconfigure(column, minsize=width, weight=0 if self.balance_mode else width)
            tk.Label(self.body, text=caption, bg="#d9d9d9", font=(self.family, -14),
                     wraplength=width - 10, padx=0).grid(row=0, column=column, sticky="nsew", padx=3, pady=(0, 12))
        if not self.items:
            text = "Ученики не найдены." if self.balance_mode else "Платежей не найдено."
            tk.Label(self.body, text=text, font=(self.family, -14), bg="#d9d9d9", anchor="w").grid(
                row=1, column=0, columnspan=len(widths), sticky="ew", pady=10)
        for row, item in enumerate(self.items, 1):
            student = item["student"]
            name = student.full_name + "\n(" + str(student.student_id).zfill(5) + ")"
            if student.is_archived:
                name += " — архив"
            if self.balance_mode:
                summary = item["summary"]
                values = [name, money_text(summary["charged"]), money_text(summary["received"]),
                          money_text(summary["debt"]), money_text(summary["advance"])]
            else:
                lesson, payment = item["lesson"], item["payment"]
                when = lesson.starts_at.strftime("%d.%m.%Y\n%H:%M") + "–" + lesson.ends_at.strftime("%H:%M")
                if lesson.starts_at.date() != lesson.ends_at.date():
                    when = lesson.starts_at.strftime("%d.%m.%Y %H:%M") + "–\n" + lesson.ends_at.strftime("%d.%m.%Y %H:%M")
                values = [str(payment.payment_id).zfill(5), name,
                          payment.paid_at.strftime("%d.%m.%Y\n%H:%M:%S"), when,
                          item["subject"] + "\n" + item["goal"], money_text(payment.amount_kopecks)]
            height = 36
            for column, value in enumerate(values):
                lines = 0
                for line in value.splitlines():
                    lines += max(1, (self.text_font.measure(line) + widths[column] - 13) // (widths[column] - 12))
                height = max(height, lines * 18 + 10)
            self.body.rowconfigure(row, minsize=height)
            key = self._key(item)
            widgets = []
            for column, value in enumerate(values):
                label = tk.Label(self.body, text=value, bg="#ededed", font=(self.family, -14),
                                 wraplength=widths[column] - 12, highlightthickness=1,
                                 highlightbackground="#ededed", padx=4, pady=3, cursor="hand2")
                label.grid(row=row, column=column, sticky="nsew", padx=3, pady=4)
                label.bind("<Button-1>", lambda event, selected=key: self.select_row(selected))
                label.bind("<MouseWheel>", self._wheel)
                if self.balance_mode:
                    label.bind("<Double-Button-1>", lambda event, selected=key: self.open_row(selected))
                widgets.append(label)
            self.row_widgets[key] = widgets
        self.select_row(self.selected_id)
        self._resize()

    def select_row(self, key):
        self.selected_id = key
        for row_id, widgets in self.row_widgets.items():
            for widget in widgets:
                widget.configure(highlightbackground="#555555" if row_id == key else "#ededed")
        state = "normal" if not self.balance_mode or key is not None else "disabled"
        self.main_button.configure(state=state)

    def open_row(self, key):
        self.select_row(key)
        self.show_selected()

    def show_selected(self):
        if not self.balance_mode:
            return
        for item in self.items:
            if item["student"].student_id == self.selected_id:
                self.show_student(self.selected_id)
                break

    def main_action(self):
        if self.balance_mode:
            self.show_selected()
        else:
            self.toggle_mode()

    def toggle_mode(self):
        self.balance_mode = not self.balance_mode
        self.selected_id = None
        self.refresh()
        self.canvas.yview_moveto(0)

    def _resize(self, event=None):
        self.canvas.itemconfigure(self.body_window, width=max(984, self.canvas.winfo_width()))
        self._scroll_region()

    def _scroll_region(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _wheel(self, event):
        if event.delta:
            self.canvas.yview_scroll(-3 if event.delta > 0 else 3, "units")
        return "break"
