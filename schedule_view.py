"""Сетка расписания и выбор недели."""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, datetime, timedelta, timezone


LEGEND_IMAGES = {
    "0": "iVBORw0KGgoAAAANSUhEUgAAACEAAAAeCAYAAACiyHcXAAAACXBIWXMAAAsTAAALEwEAmpwYAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAOdEVYdFNvZnR3YXJlAEZpZ21hnrGWYwAAADZJREFUeAHtzjEBwCAQADFa/3Z/huk0wJAoyDcze132rwdIRCISkYhEJCIRiUhEIhKRiEQkcgAjJgQaOim0IwAAAABJRU5ErkJggg==",
    "1": "iVBORw0KGgoAAAANSUhEUgAAACEAAAAeCAYAAACiyHcXAAAACXBIWXMAAAsTAAALEwEAmpwYAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAOdEVYdFNvZnR3YXJlAEZpZ21hnrGWYwAAADdJREFUeAHtzjERwCAAADFa/9KQxB1MrwGGREG+Nfcel/3jARKRiEQkIhGJSEQiEpGIRCQiEYkcrSUEAslXez4AAAAASUVORK5CYII=",
    "2": "iVBORw0KGgoAAAANSUhEUgAAACEAAAAeCAYAAACiyHcXAAAACXBIWXMAAAsTAAALEwEAmpwYAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAOdEVYdFNvZnR3YXJlAEZpZ21hnrGWYwAAADhJREFUeAHtzjEBwCAAwDA2yRM5UxxwVQMciYI8//zWOOwdF5CIRCQiEYlIRCISkYhEJCIRiUhkA6tlA25u/8HcAAAAAElFTkSuQmCC",
    "3": "iVBORw0KGgoAAAANSUhEUgAAACEAAAAeCAYAAACiyHcXAAAACXBIWXMAAAsTAAALEwEAmpwYAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAOdEVYdFNvZnR3YXJlAEZpZ21hnrGWYwAAADdJREFUeAHtzjEBwCAAwDA2/xZwyQ9XNcCRKMg399rjsn88QCISkYhEJCIRiUhEIhKRiEQkIpEDU9gDy1+HGJ8AAAAASUVORK5CYII="
}

CANCELLED_LEGEND_IMAGE = "iVBORw0KGgoAAAANSUhEUgAAACEAAAAeCAYAAACiyHcXAAAACXBIWXMAAAsTAAALEwEAmpwYAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAOdEVYdFNvZnR3YXJlAEZpZ21hnrGWYwAAADZJREFUeAHtzjEBwCAAwDA2/ybAKFzVAEeiIN+ea4/L/vEAiUhEIhKRiEQkIhGJSEQiEpGIRA6VKQN9Wt7rnwAAAABJRU5ErkJggg=="

MONTHS = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
]


def month_weeks(year, month):
    """Понедельники недель выбранного месяца."""
    first = date(year, month, 1)
    if month == 12:
        last = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)
    monday = first - timedelta(days=first.weekday())
    weeks = []
    while monday <= last:
        weeks.append(monday)
        monday += timedelta(days=7)
    return weeks


def lesson_parts(lesson, monday, half, include_cancelled=False):
    """Видимые части занятия по дням и получасовым клеткам."""
    if lesson.status == "Отменено" and not include_cancelled:
        return []
    first_hour = 8 if half == 1 else 15
    parts = []
    for row in range(7):
        day = monday + timedelta(days=row)
        start = datetime(day.year, day.month, day.day, first_hour)
        end = start + timedelta(hours=7)
        left = max(start, lesson.starts_at)
        right = min(end, lesson.ends_at)
        if left < right:
            first = int((left - start).total_seconds() // 1800)
            last = int((right - start).total_seconds() // 1800)
            parts.append((row, first, last))
    return parts


def lesson_color(lesson, paid):
    """Цвет по состоянию занятия и оплаты."""
    if lesson.status == "Отменено":
        return "#ffa1a2"
    if lesson.status == "Проведено":
        return "#c7fb72" if paid else "#fcccff"
    return "#9dfff4" if paid else "#f5f5f5"


def cancelled_rows(items, monday, half):
    """Пересекающиеся отмены размещаются друг под другом."""
    rows = [[] for day in range(7)]
    for item in sorted(items, key=lambda item: (item["lesson"].starts_at, item["lesson"].lesson_id)):
        for row, first, last in lesson_parts(item["lesson"], monday, half, True):
            lane = 0
            while any(saved_lane == lane and first < saved_last and last > saved_first
                      for saved_item, saved_first, saved_last, saved_lane in rows[row]):
                lane += 1
            rows[row].append((item, first, last, lane))
    return rows


class ScheduleView(tk.Frame):
    """Неделя расписания по макету."""

    def __init__(self, parent, family, load_schedule):
        super().__init__(parent, bg="#d9d9d9")
        self.family = family
        self.load_schedule = load_schedule
        self.items = []
        self.labels = []
        self.row_views = []
        self.cancelled_mode = False
        self.on_pay = None
        self.on_show = None
        self.lesson_menu = tk.Menu(self, tearoff=False, font=(family, -14),
                                   bg="#d9d9d9", fg="black",
                                   activebackground="#787878", activeforeground="white")
        self.lesson_menu.add_command(label="Оплатить занятие", state="disabled")
        self.lesson_menu.add_command(label="Показать занятие", state="disabled")
        self.selected_lesson_id = None
        today = datetime.now(timezone(timedelta(hours=3))).date()
        self.year = tk.StringVar(master=self, value=str(today.year))
        self.month = tk.StringVar(master=self, value=MONTHS[today.month - 1])
        self.week = tk.StringVar(master=self)
        self.half = tk.StringVar(master=self, value="1")
        self.applied_year = today.year
        self.applied_month = today.month

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Schedule.TCombobox", padding=(5, 0), borderwidth=0,
            fieldbackground="white", background="white",
            bordercolor="white", lightcolor="white", darkcolor="white"
        )
        style.map(
            "Schedule.TCombobox", fieldbackground=[("readonly", "white")],
            selectbackground=[("readonly", "white")],
            selectforeground=[("readonly", "black")]
        )

        filters = [
            ("Год:", self.year, list(range(today.year - 10, today.year + 11))),
            ("Месяц:", self.month, MONTHS),
            ("Неделя:", self.week, []),
            ("Половина дня:", self.half, ["1", "2"])
        ]
        self.combos = []
        for number, (text, variable, values) in enumerate(filters):
            y = 30 + number * 72
            tk.Label(
                self, text=text, font=(family, -16), bg="#d9d9d9",
                anchor="w", padx=0
            ).place(x=12, y=y, width=145, height=20)
            combo = ttk.Combobox(
                self, textvariable=variable, values=values, state="readonly",
                font=(family, -16), style="Schedule.TCombobox", height=12
            )
            if number == 0:
                combo.configure(state="normal")
                combo.bind("<Return>", self._period_changed)
                combo.bind("<FocusOut>", self._period_changed)
            combo.place(x=12, y=y + 32, width=140, height=25)
            self.combos.append(combo)
        self.combos[0].bind("<<ComboboxSelected>>", self._period_changed)
        self.combos[1].bind("<<ComboboxSelected>>", self._period_changed)
        self.combos[2].bind("<<ComboboxSelected>>", self.refresh)
        self.combos[3].bind("<<ComboboxSelected>>", self.refresh)

        self.buttons = {}
        for number, text in enumerate([
            "Добавить занятие", "Перенести занятие", "Отменить занятие", "К отменённым"
        ]):
            button = tk.Button(
                self, text=text, font=(family, -15), bg="#787878",
                disabledforeground="white", borderwidth=0,
                relief="flat", state="disabled"
            )
            button.place(x=6, y=348 + number * 44, width=151, height=30)
            self.buttons[text] = button

        self.legend = []
        self.legend_widgets = []
        descriptions = [
            "Запланировано,\nне оплачено", "Проведено,\nне оплачено",
            "Проведено и\nоплачено", "Запланировано\nи оплачено"
        ]
        for number, text in enumerate(descriptions):
            photo = tk.PhotoImage(master=self, data=LEGEND_IMAGES[str(number)])
            self.legend.append(photo)
            swatch = tk.Label(self, image=photo, bg="#d9d9d9", borderwidth=0, padx=0, pady=0)
            swatch.place(
                x=6, rely=1, y=-143 + number * 35, width=33, height=30
            )
            caption = tk.Label(
                self, text=text, font=(family, -12), bg="#d9d9d9",
                anchor="center", padx=0, pady=0
            )
            caption.place(x=42, rely=1, y=-143 + number * 35, width=114, height=30)
            self.legend_widgets.append((swatch, caption))

        self.cancelled_photo = tk.PhotoImage(master=self, data=CANCELLED_LEGEND_IMAGE)
        self.cancelled_swatch = tk.Label(self, image=self.cancelled_photo, bg="#d9d9d9",
                                         borderwidth=0, padx=0, pady=0)
        self.cancelled_caption = tk.Label(
            self, text="— Отменённое", font=(family, -12), bg="#d9d9d9", padx=0, pady=0
        )

        self.canvas = tk.Canvas(self, bg="#f5f5f5", highlightthickness=0)
        self.canvas.place(x=160, y=0, relwidth=1, width=-160, relheight=1)
        self.canvas.bind("<Configure>", self._draw)
        self.bind("<Map>", self.refresh)
        self._set_weeks(today)

    def _set_weeks(self, preferred):
        year = int(self.year.get())
        month = MONTHS.index(self.month.get()) + 1
        self.weeks = month_weeks(year, month)
        choices = []
        selected = 0
        for number, monday in enumerate(self.weeks):
            sunday = monday + timedelta(days=6)
            choices.append(str(number + 1) + " (" + monday.strftime("%d")
                           + "–" + sunday.strftime("%d") + ")")
            if monday <= preferred <= sunday:
                selected = number
        self.combos[2].configure(values=choices)
        self.combos[2].current(selected)
        self.applied_year = year
        self.applied_month = month

    def _period_changed(self, event=None):
        """Обновление недель после смены месяца или года."""
        try:
            year = int(self.year.get())
            if year < 1 or year > 9998:
                raise ValueError
        except ValueError:
            self.year.set(str(self.applied_year))
            messagebox.showerror("Расписание", "Введите год от 1 до 9998.", parent=self)
            return
        month = MONTHS.index(self.month.get()) + 1
        if year == self.applied_year and month == self.applied_month:
            return
        self._set_weeks(date(year, month, 1))
        self.refresh()

    def refresh(self, event=None):
        """Получение занятий выбранной недели."""
        if not hasattr(self, "weeks"):
            return
        self.monday = self.weeks[self.combos[2].current()]
        if self.cancelled_mode:
            items = self.load_schedule(self.monday, self.monday + timedelta(days=6), True)
        else:
            items = self.load_schedule(self.monday, self.monday + timedelta(days=6))
        if items is None:
            self.items = []
            self._select(None)
            self._draw()
            return
        self.items = items
        self._select(None)
        self._draw()

    def set_cancelled_mode(self, enabled):
        """Переход между расписанием и отменёнными."""
        self.cancelled_mode = enabled
        texts = ["Добавить занятие", "Перенести занятие", "Отменить занятие", "К отменённым"]
        if enabled:
            texts = ["Удалить из истории", "Перенести\nотменённое", "Восстановить\nзанятие", "К расписанию"]
        for button, text in zip(self.buttons.values(), texts):
            button.configure(text=text, font=(self.family, -14 if enabled else -15), pady=0)
        self.buttons["Добавить занятие"].configure(state="disabled" if enabled else "normal")
        for number, (swatch, caption) in enumerate(self.legend_widgets):
            if enabled:
                swatch.place_forget()
                caption.place_forget()
            else:
                swatch.place(x=6, rely=1, y=-143 + number * 35, width=33, height=30)
                caption.place(x=42, rely=1, y=-143 + number * 35, width=114, height=30)
        if enabled:
            self.cancelled_swatch.place(x=6, rely=1, y=-143, width=33, height=30)
            self.cancelled_caption.place(x=42, rely=1, y=-143, width=114, height=30)
        else:
            self.cancelled_swatch.place_forget()
            self.cancelled_caption.place_forget()
        self.refresh()

    def show_lesson(self, lesson):
        """Переход к дате сохранённого занятия."""
        day = lesson.starts_at.date()
        self.year.set(str(day.year))
        self.month.set(MONTHS[day.month - 1])
        self._set_weeks(day)
        self.half.set("1" if lesson.starts_at.hour < 15 else "2")
        self.refresh()
        self._select(lesson.lesson_id)

    def _select(self, lesson_id):
        self.selected_lesson_id = lesson_id
        state = "disabled" if lesson_id is None else "normal"
        self.buttons["Перенести занятие"].configure(state=state)
        self.buttons["Отменить занятие"].configure(state=state)
        if self.cancelled_mode:
            can_delete = False
            for item in self.items:
                if item["lesson"].lesson_id == lesson_id and not item["paid"]:
                    can_delete = True
                    break
            self.buttons["Добавить занятие"].configure(state="normal" if can_delete else "disabled")
        else:
            self.buttons["Добавить занятие"].configure(state="normal")
        for label, saved_id in self.labels:
            label.configure(highlightthickness=3 if saved_id == lesson_id else 1)

    def _show_lesson_menu(self, event, lesson_id):
        """Оплата по правой кнопке мыши."""
        self._select(lesson_id)
        can_pay = False
        for item in self.items:
            if item["lesson"].lesson_id == lesson_id:
                can_pay = (not self.cancelled_mode and not item["paid"]
                           and item["lesson"].status != "Отменено"
                           and item["lesson"].price_kopecks > 0 and self.on_pay is not None)
                break
        self.lesson_menu.entryconfigure(
            0, state="normal" if can_pay else "disabled",
            command=lambda: self.on_pay(lesson_id)
        )
        self.lesson_menu.entryconfigure(
            1, state="normal" if self.on_show is not None and not self.cancelled_mode else "disabled",
            command=lambda: self.on_show(lesson_id)
        )
        try:
            self.lesson_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.lesson_menu.grab_release()
        return "break"

    def _draw(self, event=None):
        """Сетка и цветные блоки занятий."""
        if not hasattr(self, "monday"):
            return
        for label, lesson_id in self.labels:
            label.destroy()
        self.labels = []
        for row_view in self.row_views:
            row_view.destroy()
        self.row_views = []
        self.canvas.delete("all")
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        if width <= 70 or height <= 54:
            return
        step = min(44, max(34, (height - 531) // 3))
        for number, button in enumerate(self.buttons.values()):
            button.place_configure(y=348 + number * step, height=34 if self.cancelled_mode else 30)
        cell = (width - 70) / 14
        row_height = (height - 54) / 7
        half = int(self.half.get())
        first_hour = 8 if half == 1 else 15
        self.canvas.create_rectangle(0, 0, width - 1, height - 1, outline="black")
        self.canvas.create_text(35, 27, text="МСК", font=(self.family, -14))
        for column in range(15):
            x = 70 + column * cell
            self.canvas.create_line(x, 0, x, height, fill="black")
            if column < 14:
                minutes = first_hour * 60 + column * 30
                text = str(minutes // 60) + ":" + str(minutes % 60).zfill(2)
                self.canvas.create_text(x + cell / 2, 27, text=text, font=(self.family, -16))
        days = ["Пн.", "Вт.", "Ср.", "Чт.", "Пт.", "Сб.", "Вс."]
        for row in range(8):
            y = 54 + row * row_height
            self.canvas.create_line(0, y, width, y, fill="black")
            if row < 7:
                day = self.monday + timedelta(days=row)
                self.canvas.create_text(35, y + 20, text=days[row], font=(self.family, -24))
                self.canvas.create_text(35, y + 51, text=day.strftime("%d.%m"), font=(self.family, -16))

        if self.cancelled_mode:
            self._draw_cancelled(cell, row_height, half)
            return
        for item in self.items:
            lesson = item["lesson"]
            name = item["student_name"].split()
            goal = item["goal"]
            if "успеваем" in goal.casefold():
                goal = "ПУ"
            elif "олимпиад" in goal.casefold():
                goal = "Олимпиада"
            text = "\n".join(name[:2]) + "\n" + item["subject"] + "\n" + goal
            for row, first, last in lesson_parts(lesson, self.monday, half):
                box_width = (last - first) * cell
                label = tk.Label(
                    self.canvas, text=text, font=(self.family, -14),
                    bg=lesson_color(lesson, item["paid"]), fg="black",
                    wraplength=max(1, int(box_width) - 8), borderwidth=0,
                    highlightthickness=3 if self.selected_lesson_id == lesson.lesson_id else 1,
                    highlightbackground="black",
                    padx=2, pady=0, cursor="hand2", takefocus=True
                )
                label.bind("<Button-1>", lambda event, sid=lesson.lesson_id: self._select(sid))
                label.bind("<Return>", lambda event, sid=lesson.lesson_id: self._select(sid))
                label.bind("<Button-3>", lambda event, sid=lesson.lesson_id: self._show_lesson_menu(event, sid))
                self.canvas.create_window(
                    70 + first * cell, 54 + row * row_height,
                    anchor="nw", window=label, width=box_width, height=row_height
                )
                self.labels.append((label, lesson.lesson_id))

    def _draw_cancelled(self, cell, row_height, half):
        """Прокрутка отменённых внутри строки дня."""
        for row, entries in enumerate(cancelled_rows(self.items, self.monday, half)):
            if not entries:
                continue
            count = max(entry[3] for entry in entries) + 1
            area = tk.Canvas(self.canvas, bg="#f5f5f5", highlightthickness=0,
                             yscrollincrement=max(1, int(row_height)))
            area.configure(scrollregion=(0, 0, 14 * cell, count * row_height))
            self.row_views.append(area)
            self.canvas.create_window(70, 54 + row * row_height, anchor="nw",
                                      window=area, width=14 * cell, height=row_height)
            for column in range(15):
                area.create_line(column * cell, 0, column * cell, count * row_height, fill="black")
            for lane in range(count + 1):
                area.create_line(0, lane * row_height, 14 * cell, lane * row_height, fill="black")
            for item, first, last, lane in entries:
                lesson = item["lesson"]
                text = ("\n".join(item["student_name"].split()[:2]) + "\n"
                        + item["subject"] + "\n" + item["goal"])
                label = tk.Label(area, text=text, font=(self.family, -14),
                                 bg="#ffa1a2", fg="black", borderwidth=0,
                                 highlightbackground="black", cursor="hand2", takefocus=True,
                                 highlightthickness=3 if self.selected_lesson_id == lesson.lesson_id else 1,
                                 wraplength=max(1, int((last - first) * cell) - 8), padx=2, pady=0)
                label.bind("<Button-1>", lambda event, sid=lesson.lesson_id: self._select(sid))
                label.bind("<Return>", lambda event, sid=lesson.lesson_id: self._select(sid))
                label.bind("<MouseWheel>", lambda event, target=area: self._scroll_day(event, target))
                area.create_window(first * cell, lane * row_height, anchor="nw", window=label,
                                   width=(last - first) * cell, height=row_height)
                self.labels.append((label, lesson.lesson_id))
            area.bind("<MouseWheel>", lambda event, target=area: self._scroll_day(event, target))
            if count > 1:
                scrollbar = ttk.Scrollbar(area, orient="vertical", command=area.yview)
                scrollbar.place(relx=1, x=-13, y=0, width=13, relheight=1)
                area.configure(yscrollcommand=scrollbar.set)
            for item, first, last, lane in entries:
                if item["lesson"].lesson_id == self.selected_lesson_id:
                    area.yview_moveto(lane / count)
                    break

    def _scroll_day(self, event, area):
        if event.delta:
            area.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"
