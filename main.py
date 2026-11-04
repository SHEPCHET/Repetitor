"""Запуск графического интерфейса."""

import sqlite3
import tkinter as tk
from tkinter import messagebox
from datetime import datetime, timedelta

from authenticator import Authenticator
from auth_view import AuthWindow
from database import DatabaseManager
from main_window import MainWindow
from student_repository import StudentRepository
from parent_repository import ParentRepository
from enrollment_repository import EnrollmentRepository
from subject_repository import SubjectRepository
from students_view import StudentsView
from student_form import StudentForm
from student_service import StudentService
from schedule_view import ScheduleView
from lesson_repository import LessonRepository
from payment_repository import PaymentRepository
from lesson_form import LessonForm, duration_minutes
from lesson_service import LessonService


class ApplicationController:
    """Управление окнами программы."""

    def __init__(self, root):
        """Подключение базы и создание первого экрана."""
        self.root = root
        self.db = DatabaseManager()
        self.authenticator = Authenticator(self.db)
        self.main_window = None
        self.view = AuthWindow(root, self.login, self.register)
        self.view.pack(fill="both", expand=True)
        root.protocol("WM_DELETE_WINDOW", self.close)

    def login(self, username, password):
        """Проверка данных из формы входа."""
        self.authenticator.logout()
        try:
            if username.strip() == "" or password == "":
                raise ValueError("Введите логин и пароль.")

            if not self.authenticator.login(username, password):
                raise ValueError("Неверный логин или пароль.")

        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror("Вход", str(error), parent=self.root)

        else:
            self.show_main_window()

        finally:
            self.view.clear_password()

    def show_main_window(self):
        """Открытие главного окна после входа."""
        if self.authenticator.current_user_id is None:
            return

        if self.main_window is None:
            self.main_window = MainWindow(self.root)
            self.students_view = StudentsView(
                self.main_window.pages["Ученики"],
                self.main_window.family,
                self.load_students
            )
            self.students_view.pack(fill="both", expand=True)
            self.students_view.add_button.configure(
                state="normal", command=self.open_student_form
            )
            self.students_view.edit_button.configure(command=self.edit_student)
            self.students_view.move_button.configure(command=self.move_student)
            self.student_form = None
            self.schedule_view = ScheduleView(
                self.main_window.pages["Расписание"],
                self.main_window.family, self.load_schedule
            )
            self.schedule_view.pack(fill="both", expand=True)
            self.lesson_form = None
            self.schedule_view.buttons["Добавить занятие"].configure(
                state="normal", command=self.open_lesson_form,
                fg="white", activeforeground="white",
                activebackground="#787878", cursor="hand2"
            )

        self.view.pack_forget()
        self.main_window.pack(fill="both", expand=True)
        self.root.minsize(1024, 760)

    def open_lesson_form(self):
        """Открытие формы добавления занятия."""
        if self.authenticator.current_user_id is None:
            return
        if self.lesson_form is not None:
            self.lesson_form.lift()
            return
        try:
            students = StudentRepository(self.db).get_all()
            if not students:
                raise ValueError("Сначала добавь активного ученика во вкладке «Ученики».")
        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror("Занятие", str(error), parent=self.root)
            return
        self.lesson_form = LessonForm(
            self.root, self.main_window.family, students,
            self.schedule_view.monday, int(self.schedule_view.half.get()),
            self.load_lesson_directions, self.save_lesson, self.close_lesson_form
        )

    def load_lesson_directions(self, student_id):
        """Направления выбранного активного ученика."""
        if self.authenticator.current_user_id is None:
            return []
        try:
            student = StudentRepository(self.db).get_by_id(student_id)
            if student is None or student.is_archived:
                raise ValueError("Выбери активного ученика.")
            subjects = SubjectRepository(self.db)
            directions = EnrollmentRepository(self.db).get_by_student(student_id)
            items = []
            for enrollment in directions:
                subject = subjects.get_by_id(enrollment.subject_id)
                items.append({"enrollment": enrollment, "subject": subject[1]})
            return items
        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror("Занятие", str(error), parent=self.root)
            return None

    def close_lesson_form(self):
        """Закрытие формы без сохранения."""
        if self.lesson_form is not None:
            self.lesson_form.destroy()
            self.lesson_form = None

    def save_lesson(self, data):
        """Создание занятия через готовый сервис."""
        if self.authenticator.current_user_id is None:
            return
        try:
            student = StudentRepository(self.db).get_by_id(data["student_id"])
            if student is None or student.is_archived:
                raise ValueError("Выбери активного ученика.")
            enrollment = EnrollmentRepository(self.db).get_by_id(data["enrollment_id"])
            if enrollment is None or enrollment.student_id != student.student_id:
                raise ValueError("Это направление не принадлежит выбранному ученику.")
            try:
                starts_at = datetime.strptime(data["date"] + " " + data["time"], "%d.%m.%Y %H:%M")
            except ValueError:
                raise ValueError("Укажи дату в формате ДД.ММ.ГГГГ и время ЧЧ:ММ.")
            duration = duration_minutes(data["hours"], data["minutes"])
            lesson = LessonService(self.db).schedule(enrollment.enrollment_id, starts_at, duration)
        except (sqlite3.Error, ValueError, OverflowError) as error:
            messagebox.showerror("Занятие", str(error), parent=self.root)
            return
        self.close_lesson_form()
        self.schedule_view.show_lesson(lesson)
        amount = lesson.price_kopecks
        money = str(amount // 100) + "," + str(amount % 100).zfill(2)
        messagebox.showinfo(
            "Занятие", "Занятие добавлено. Стоимость: " + money + " руб.",
            parent=self.root
        )

    def load_schedule(self, date_from, date_to):
        """Занятия, пересекающиеся с выбранной неделей."""
        if self.authenticator.current_user_id is None:
            return []
        try:
            if date_from > date_to:
                raise ValueError("Начало периода позже его конца.")
            start = datetime(date_from.year, date_from.month, date_from.day)
            end = datetime(date_to.year, date_to.month, date_to.day) + timedelta(days=1)
            lessons = LessonRepository(self.db).get_overlapping(start, end)
            enrollments = EnrollmentRepository(self.db)
            students = StudentRepository(self.db)
            subjects = SubjectRepository(self.db)
            payments = PaymentRepository(self.db)
            items = []
            for lesson in lessons:
                enrollment = enrollments.get_by_id(lesson.enrollment_id)
                student = students.get_by_id(enrollment.student_id)
                subject = subjects.get_by_id(enrollment.subject_id)
                items.append({
                    "lesson": lesson,
                    "student_name": student.full_name,
                    "student_id": student.student_id,
                    "subject": subject[1],
                    "goal": enrollment.preparation_goal,
                    "paid": payments.get_by_lesson(lesson.lesson_id) is not None
                })
            return items
        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror("Расписание", str(error), parent=self.root)
            return None

    def open_student_form(self):
        """Открытие формы добавления."""
        if self.authenticator.current_user_id is None:
            return
        self.show_student_form()

    def show_student_form(self, record=None):
        """Форма добавления или изменения."""
        lookup = None
        if record is not None:
            lookup = self.find_student_for_edit
        form = StudentForm(
            self.main_window.pages["Ученики"], self.main_window.family,
            self.save_student, self.close_student_form, record, lookup
        )
        if self.student_form is not None:
            self.student_form.destroy()
        self.student_form = form
        self.students_view.pack_forget()
        self.student_form.pack(fill="both", expand=True)

    def edit_student(self):
        """Изменение выбранной карточки."""
        if self.authenticator.current_user_id is None:
            return
        student_id = self.students_view.selected_id
        if student_id is None:
            return
        try:
            record = StudentService(self.db).get_card(student_id)
        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror("Ученики", str(error), parent=self.root)
            return
        self.show_student_form(record)

    def find_student_for_edit(self, query):
        """Поиск другой карточки в форме по Enter."""
        if self.authenticator.current_user_id is None:
            return
        try:
            if query.strip() == "":
                raise ValueError("Введите ФИО или ID ученика.")
            students = StudentRepository(self.db).search(query, None)
            if not students:
                raise ValueError("Ученик не найден.")
            if len(students) > 1:
                raise ValueError("Найдено несколько учеников. Уточни ФИО или введи ID.")
            record = StudentService(self.db).get_card(students[0].student_id)
        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror("Ученики", str(error), parent=self.root)
            return
        if self.student_form.has_changes():
            if not messagebox.askyesno(
                "Изменить карточку",
                "Загрузить другую карточку? Несохранённые изменения будут потеряны.",
                parent=self.root
            ):
                return
        self.show_student_form(record)

    def close_student_form(self):
        """Возврат к карточкам."""
        if self.student_form is not None:
            self.student_form.destroy()
            self.student_form = None
        self.students_view.pack(fill="both", expand=True)

    def save_student(self, data):
        """Сохранение данных из формы."""
        if self.authenticator.current_user_id is None:
            return
        try:
            service = StudentService(self.db)
            student_id = self.student_form.student_id
            text = "Изменения сохранены. ID: "
            if student_id is None:
                student_id = service.add(data)
                text = "Ученик сохранён. ID: "
            else:
                service.update(student_id, data)
        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror("Ученики", str(error), parent=self.root)
            return

        self.close_student_form()
        self.students_view.set_archive_mode(data["student"]["is_archived"])
        self.students_view.select_student(student_id)
        messagebox.showinfo(
            "Ученики", text + str(student_id),
            parent=self.root
        )

    def move_student(self):
        """Перемещение выбранного ученика или восстановление."""
        if self.authenticator.current_user_id is None:
            return
        student_id = self.students_view.selected_id
        if student_id is None:
            return
        archived = not self.students_view.archive_mode
        try:
            StudentService(self.db).set_archived(student_id, archived)
        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror("Ученики", str(error), parent=self.root)
            return
        self.students_view.refresh()
        text = "Ученик восстановлен."
        if archived:
            text = "Ученик перемещён в архив."
        messagebox.showinfo("Ученики", text, parent=self.root)

    def load_students(self, query, is_archived=False):
        """Данные для карточек учеников."""
        if self.authenticator.current_user_id is None:
            return []

        try:
            students = StudentRepository(self.db).search(query, is_archived)
            parents = ParentRepository(self.db)
            enrollments = EnrollmentRepository(self.db)
            subjects = SubjectRepository(self.db)
            items = []

            for student in students:
                directions = []
                for enrollment in enrollments.get_by_student(student.student_id):
                    subject = subjects.get_by_id(enrollment.subject_id)
                    directions.append((enrollment, subject[1]))

                items.append({
                    "student": student,
                    "parents": parents.get_by_student(student.student_id),
                    "enrollments": directions
                })

            return items

        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror("Ученики", str(error), parent=self.root)
            return None

    def register(self, name, username, email, password, repeat):
        """Регистрация из графической формы."""
        self.authenticator.logout()
        try:
            if password != repeat:
                raise ValueError("Пароли не совпадают.")

            self.authenticator.register(name, username, email, password)

        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror(
                "Регистрация", str(error), parent=self.root
            )

        else:
            messagebox.showinfo(
                "Регистрация", "Учётная запись создана.", parent=self.root
            )
            self.view.show_login(username.strip())

    def close(self):
        """Закрытие приложения."""
        self.authenticator.logout()
        self.db.close()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Репетитор")
    root.geometry("1280x800")
    root.minsize(640, 760)
    root.configure(bg="white")
    controller = None

    try:
        controller = ApplicationController(root)
        root.mainloop()

    except (sqlite3.Error, OSError, ValueError) as error:
        messagebox.showerror("Ошибка запуска", str(error), parent=root)
        root.destroy()

    finally:
        if controller is not None:
            controller.db.close()
