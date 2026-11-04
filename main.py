"""Запуск графического интерфейса."""

import sqlite3
import tkinter as tk
from tkinter import messagebox

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

        self.view.pack_forget()
        self.main_window.pack(fill="both", expand=True)
        self.root.minsize(1024, 760)

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
