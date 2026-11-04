"""Добавление и перенос занятия."""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta, timezone


def duration_minutes(hours, minutes):
    """Длительность занятия в минутах."""
    hours = hours.strip()
    minutes = minutes.strip()
    if not hours.isdecimal() or minutes not in ("0", "00", "30"):
        raise ValueError("Укажи целое число часов и 00 или 30 минут.")
    total = int(hours) * 60 + int(minutes)
    if total <= 0:
        raise ValueError("Длительность должна быть больше нуля.")
    return total


class LessonForm(tk.Frame):
    """Выбор ученика, направления и времени."""

    def __init__(self, parent, family, students, monday, half,
                 load_directions, on_save, on_cancel, record=None):
        super().__init__(parent, bg="#6b6b6b")
        self.family = family
        self.students = students
        self.directions = []
        self.load_directions = load_directions
        self.on_save = on_save
        self.record = record

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Lesson.TCombobox", padding=(5, 0), borderwidth=0,
            fieldbackground="#d9d9d9", background="#d9d9d9",
            bordercolor="#d9d9d9", lightcolor="#d9d9d9", darkcolor="#d9d9d9"
        )
        style.map(
            "Lesson.TCombobox", fieldbackground=[("readonly", "#d9d9d9")],
            background=[("active", "#d9d9d9"), ("readonly", "#d9d9d9")],
            foreground=[("disabled", "black"), ("readonly", "black")],
            selectbackground=[("readonly", "#d9d9d9")],
            selectforeground=[("readonly", "black")],
            bordercolor=[("focus", "#d9d9d9")],
            lightcolor=[("focus", "#d9d9d9")], darkcolor=[("focus", "#d9d9d9")]
        )
        style.map("Hint.Lesson.TCombobox", foreground=[("readonly", "#6b6b6b")])

        title = "Форма добавления занятия"
        if record is not None:
            title = "Перенос занятия"
            if record["lesson"].status == "Отменено":
                title = "Перенос отменённого занятия"
        tk.Label(
            self, text=title, font=(family, -24),
            bg="#6b6b6b", fg="white", padx=0, pady=0
        ).place(x=0, y=5, width=621, height=32)

        labels = ["Ученик:", "Предмет:", "Дата:", "Время:",
                  "Длительность:", "Стоимость занятия:"]
        for row, text in enumerate(labels):
            tk.Label(
                self, text=text, font=(family, -16), bg="#6b6b6b",
                fg="white", anchor="e", padx=0, pady=0
            ).place(x=105, y=80 + row * 35, width=162, height=25)

        self.student_combo = self._combo(
            [str(student.student_id).zfill(5) + " — " + student.full_name
             for student in students], 277, 80, 260
        )
        self.student_combo.configure(style="Hint.Lesson.TCombobox")
        self.student_combo.set("Выберите ученика")
        self.student_combo.bind("<<ComboboxSelected>>", self._student_changed)
        self.direction_combo = self._combo([], 277, 115, 260)
        self.direction_combo.configure(style="Hint.Lesson.TCombobox")
        self.direction_combo.set("Выберите предмет и цель")
        self.direction_combo.bind("<<ComboboxSelected>>", self._preview)

        dates = [(monday + timedelta(days=day)).strftime("%d.%m.%Y")
                 for day in range(7)]
        self.date_combo = self._combo(dates, 277, 150, 206, editable=True)
        today = datetime.now(timezone(timedelta(hours=3))).date()
        selected_date = monday
        if monday <= today <= monday + timedelta(days=6):
            selected_date = today
        self.date_combo.set(selected_date.strftime("%d.%m.%Y"))
        times = []
        for minutes in range(8 * 60, 22 * 60, 30):
            times.append(str(minutes // 60).zfill(2) + ":" + str(minutes % 60).zfill(2))
        self.time_combo = self._combo(times, 277, 185, 206)
        self.time_combo.set("08:00" if half == 1 else "15:00")

        self.hours = tk.StringVar(master=self, value="1")
        self.minutes = tk.StringVar(master=self, value="00")
        self.hours_combo = self._combo(list(range(13)), 277, 220, 81, editable=True)
        self.hours_combo.configure(textvariable=self.hours)
        tk.Label(
            self, text=":", font=(family, -20), bg="#6b6b6b", fg="white"
        ).place(x=358, y=220, width=13, height=25)
        self.minutes_combo = self._combo(["00", "30"], 371, 220, 81)
        self.minutes_combo.configure(textvariable=self.minutes)
        self.hours.trace_add("write", self._preview)
        self.minutes.trace_add("write", self._preview)
        self.price = tk.StringVar(master=self, value="—")
        tk.Label(
            self, textvariable=self.price, font=(family, -12),
            bg="#d9d9d9", fg="black", anchor="center", padx=0, pady=0
        ).place(x=277, y=255, width=125, height=25)

        self._button("Отмена", on_cancel).place(x=17, y=326, width=106, height=24)
        self.save_button = self._button("Добавить", self._save)
        self.save_button.place(x=501, y=326, width=106, height=24)
        self.save_button.configure(state="disabled")
        if record is not None:
            lesson = record["lesson"]
            self.student_combo.current(0)
            self.student_combo.configure(state="disabled", style="Lesson.TCombobox")
            self.directions = [{"enrollment": record["enrollment"], "subject": record["subject"]}]
            self.direction_combo.configure(
                values=[record["subject"] + " — " + record["enrollment"].preparation_goal],
                style="Lesson.TCombobox"
            )
            self.direction_combo.current(0)
            self.direction_combo.configure(state="disabled")
            self.date_combo.set(lesson.starts_at.strftime("%d.%m.%Y"))
            self.time_combo.set(lesson.starts_at.strftime("%H:%M"))
            duration = int((lesson.ends_at - lesson.starts_at).total_seconds() // 60)
            self.hours.set(str(duration // 60))
            self.minutes.set(str(duration % 60).zfill(2))
            self.hours_combo.configure(state="disabled")
            self.minutes_combo.configure(state="disabled")
            self.save_button.configure(text="Перенести")
            self._preview()
        self.place(relx=0.5, rely=0.5, anchor="center", width=621, height=359)
        self.update_idletasks()
        self.grab_set()
        if record is None:
            self.student_combo.focus_set()
        else:
            self.date_combo.focus_set()

    def _combo(self, values, x, y, width, editable=False):
        state = "normal" if editable else "readonly"
        combo = ttk.Combobox(
            self, values=values, state=state, font=(self.family, -12),
            style="Lesson.TCombobox", height=12
        )
        combo.place(x=x, y=y, width=width, height=25)
        return combo

    def _button(self, text, command):
        return tk.Button(
            self, text=text, command=command, font=(self.family, -14),
            bg="#d9d9d9", fg="black", relief="flat", borderwidth=0,
            cursor="hand2"
        )

    def _student_changed(self, event=None):
        self.directions = []
        self.direction_combo.configure(values=[], style="Hint.Lesson.TCombobox")
        self.direction_combo.set("Выберите предмет и цель")
        index = self.student_combo.current()
        if index >= 0:
            self.student_combo.configure(style="Lesson.TCombobox")
            rows = self.load_directions(self.students[index].student_id)
            if rows is not None:
                self.directions = rows
        choices = []
        for number, item in enumerate(self.directions, 1):
            enrollment = item["enrollment"]
            choices.append(str(number) + ". " + item["subject"] + " — "
                           + enrollment.preparation_goal)
        self.direction_combo.configure(values=choices)
        if not choices:
            self.direction_combo.set("Нет направлений обучения")
        self._preview()

    def _preview(self, *args):
        index = self.direction_combo.current()
        self.price.set("—")
        self.save_button.configure(state="disabled")
        if index < 0:
            return
        self.direction_combo.configure(style="Lesson.TCombobox")
        try:
            duration = duration_minutes(self.hours.get(), self.minutes.get())
            amount = self.directions[index]["enrollment"].calculate_price(duration)
            if self.record is not None:
                amount = self.record["lesson"].price_kopecks
        except ValueError:
            return
        self.price.set(str(amount // 100) + "," + str(amount % 100).zfill(2) + " руб.")
        self.save_button.configure(state="normal")

    def _save(self):
        student_index = self.student_combo.current()
        direction_index = self.direction_combo.current()
        if student_index < 0 or direction_index < 0:
            messagebox.showerror("Занятие", "Выберите ученика и направление.", parent=self)
            return
        self.on_save({
            "student_id": self.students[student_index].student_id,
            "enrollment_id": self.directions[direction_index]["enrollment"].enrollment_id,
            "date": self.date_combo.get().strip(),
            "time": self.time_combo.get().strip(),
            "hours": self.hours.get(), "minutes": self.minutes.get()
        })

    def destroy(self):
        self.grab_release()
        super().destroy()
