"""Запуск графического интерфейса."""

import sqlite3
import tkinter as tk
from tkinter import messagebox, filedialog
from datetime import datetime, timedelta
from pathlib import Path

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
from payment_service import PaymentService
from lesson_form import LessonForm, duration_minutes
from lesson_service import LessonService
from journal_service import JournalService
from lessons_view import LessonsView
from payment_history import PaymentHistory
from payments_view import PaymentsView
from reports_view import ReportsView
from report_generator import ReportGenerator
from settings_view import SettingsView
from remembered_login import RememberedLogin


class ApplicationController:
    """Управление окнами программы."""

    def __init__(self, root):
        """Подключение базы и создание первого экрана."""
        self.root = root
        self.db = DatabaseManager()
        self.authenticator = Authenticator(self.db)
        self.saved_login = RememberedLogin(self.db)
        self.main_window = None
        self.lesson_form = None
        self.backup_due = False
        self.view = AuthWindow(root, self.login, self.register)
        self.view.pack(fill="both", expand=True)
        root.protocol("WM_DELETE_WINDOW", self.close)

        # Вход при повторном запуске
        user_id = self.saved_login.restore()
        if user_id is not None:
            self.authenticator.current_user_id = user_id
            self.backup_due = True
            self.show_main_window()

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
            self.backup_due = True
            self.remember_login()
            self.show_main_window()

        finally:
            self.view.clear_password()

    def remember_login(self):
        """Запоминание текущего аккаунта."""
        try:
            self.saved_login.remember(self.authenticator.current_user_id)
        except (sqlite3.Error, OSError, ValueError) as error:
            messagebox.showwarning(
                "Сохранение входа",
                "Не удалось запомнить аккаунт. При следующем запуске войди вручную.\n"
                + str(error),
                parent=self.root,
            )

    def show_main_window(self):
        """Открытие главного окна после входа."""
        if self.authenticator.current_user_id is None:
            return

        if self.main_window is None:
            self.main_window = MainWindow(self.root)
            self.students_view = StudentsView(
                self.main_window.pages["Ученики"],
                self.main_window.family,
                self.load_students,
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
                self.main_window.family,
                self.load_schedule,
            )
            self.schedule_view.pack(fill="both", expand=True)
            self.schedule_view.on_pay = self.pay_lesson
            self.schedule_view.on_show = self.show_lesson_in_journal
            self.lessons_view = LessonsView(
                self.main_window.pages["Занятия"],
                self.main_window.family,
                self.load_journal,
                self.save_journal_topics,
                self.pay_lesson,
            )
            self.lessons_view.pack(fill="both", expand=True)
            self.payments_view = PaymentsView(
                self.main_window.pages["Оплаты"],
                self.main_window.family,
                self.load_payments,
                self.show_student_journal,
            )
            self.payments_view.pack(fill="both", expand=True)
            self.reports_view = ReportsView(
                self.main_window.pages["Отчеты"],
                self.main_window.family,
                self.load_report_students,
                self.generate_report,
                self.save_generated_report,
            )
            self.reports_view.pack(fill="both", expand=True)
            self.settings_view = SettingsView(
                self.main_window.pages["Настройки"],
                self.main_window.family,
                self.load_account,
                self.change_account_password,
                self.create_backup,
                self.logout,
            )
            self.settings_view.pack(fill="both", expand=True)
            self.main_window.before_change = self.before_page_change
            self.lesson_form = None
            self.schedule_view.buttons["Добавить занятие"].configure(
                state="normal",
                command=self.add_or_delete_lesson,
                fg="white",
                activeforeground="white",
                activebackground="#787878",
                cursor="hand2",
            )
            self.schedule_view.buttons["Перенести занятие"].configure(
                command=self.open_reschedule_form,
                fg="white",
                activeforeground="white",
                activebackground="#787878",
                cursor="hand2",
            )
            self.schedule_view.buttons["Отменить занятие"].configure(
                command=self.change_lesson_status,
                fg="white",
                activeforeground="white",
                activebackground="#787878",
                cursor="hand2",
            )
            self.schedule_view.buttons["К отменённым"].configure(
                state="normal",
                command=self.toggle_cancelled,
                fg="white",
                activeforeground="white",
                activebackground="#787878",
                cursor="hand2",
            )

        self.view.pack_forget()
        self.main_window.pack(fill="both", expand=True)
        self.root.minsize(1024, 760)

    def load_account(self):
        """Сведения о текущем пользователе."""
        if self.authenticator.current_user_id is None:
            return None
        try:
            return self.authenticator.get_current_user()
        except sqlite3.Error as error:
            messagebox.showerror("Настройки", str(error), parent=self.root)
            return None

    def change_account_password(self, current, new, repeat):
        """Смена пароля из настроек."""
        if self.authenticator.current_user_id is None:
            return False
        try:
            if not current or not new or not repeat:
                raise ValueError("Заполни все три поля пароля.")
            if new != repeat:
                raise ValueError("Новые пароли не совпадают.")
            if not self.authenticator.change_password(current, new):
                raise ValueError("Текущий пароль указан неверно.")
        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror("Смена пароля", str(error), parent=self.root)
            return False
        messagebox.showinfo("Смена пароля", "Пароль изменён.", parent=self.root)
        self.remember_login()
        return True

    def create_backup(self):
        """Ручное создание резервной копии."""
        if self.authenticator.current_user_id is None:
            return None
        try:
            path = self.db.backup()
        except (sqlite3.Error, ValueError, OSError) as error:
            messagebox.showerror("Резервная копия", str(error), parent=self.root)
            return None
        messagebox.showinfo(
            "Резервная копия",
            "Резервная копия создана:\n" + str(path),
            parent=self.root,
        )
        return path

    def logout(self):
        """Очистка рабочих экранов и возврат ко входу."""
        if getattr(self, "lessons_view", None) is not None:
            if not self.lessons_view.leave_editing():
                return False
        try:
            self.saved_login.forget(self.authenticator.current_user_id)
        except (sqlite3.Error, OSError, ValueError) as error:
            messagebox.showerror("Выход", str(error), parent=self.root)
            return False
        self.close_lesson_form()
        if getattr(self, "settings_view", None) is not None:
            self.settings_view.clear_passwords()
        self.authenticator.logout()
        if self.main_window is not None:
            self.main_window.destroy()
            self.main_window = None
        self.student_form = None
        for name in [
            "students_view",
            "schedule_view",
            "lessons_view",
            "payments_view",
            "reports_view",
            "settings_view",
        ]:
            setattr(self, name, None)
        self.view.show_login()
        self.view.pack(fill="both", expand=True)
        self.root.minsize(640, 760)
        return True

    def load_report_students(self):
        """Все ученики, включая архивных."""
        if self.authenticator.current_user_id is None:
            return []
        try:
            return StudentRepository(self.db).get_all(None)
        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror("Отчёты", str(error), parent=self.root)
            return None

    def generate_report(self, query, date_from, date_to):
        """Проверка параметров и подготовка отчёта."""
        if self.authenticator.current_user_id is None:
            return None
        try:
            if not query.strip():
                raise ValueError("Выбери ученика или введи его ФИО / ID.")
            students = StudentRepository(self.db).search(query, None)
            if not students:
                raise ValueError("Ученик не найден.")
            if len(students) > 1:
                raise ValueError(
                    "Найдено несколько учеников. Выбери нужного из списка или введи ID."
                )
            try:
                first = datetime.strptime(date_from, "%d.%m.%Y").date()
                last = datetime.strptime(date_to, "%d.%m.%Y").date()
            except ValueError:
                raise ValueError("Укажи обе даты в формате ДД.ММ.ГГГГ.")
            if first > last:
                raise ValueError("Начало периода позже его конца.")
            changed = LessonService(self.db).complete_finished()
            if changed:
                self.schedule_view.refresh()
                self.lessons_view.refresh()
                self.payments_view.refresh()
            generator = ReportGenerator(self.db)
            data = generator.get_data(students[0].student_id, first, last)
            return {"data": data, "text": generator.make_text(data)}
        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror("Отчёты", str(error), parent=self.root)
            return None

    def save_generated_report(self, report, filename):
        """Выбор папки и сохранение показанного отчёта."""
        if self.authenticator.current_user_id is None:
            return False
        try:
            if not report or not report.strip():
                raise ValueError("Сначала сформируй отчёт.")
            folder = Path(self.db.db_path).parent / "reports"
            folder.mkdir(exist_ok=True)
            path = filedialog.asksaveasfilename(
                parent=self.root,
                title="Сохранить отчёт",
                initialdir=str(folder),
                initialfile=filename,
                defaultextension=".txt",
                filetypes=[("Текстовый файл", "*.txt")],
                confirmoverwrite=True,
            )
            if not path:
                return False
            if Path(path).suffix.lower() != ".txt":
                raise ValueError("Сохрани отчёт с расширением .txt.")
            ReportGenerator(self.db).save(report, path)
        except (sqlite3.Error, ValueError, OSError) as error:
            messagebox.showerror("Сохранение отчёта", str(error), parent=self.root)
            return False
        messagebox.showinfo("Отчёты", "Отчёт сохранён:\n" + str(path), parent=self.root)
        return True

    def load_payments(self, query="", balance_mode=False):
        """История оплат или общие балансы."""
        if self.authenticator.current_user_id is None:
            return []
        try:
            changed = LessonService(self.db).complete_finished()
            if changed:
                self.schedule_view.refresh()
                self.lessons_view.refresh()
            history = PaymentHistory(self.db)
            if balance_mode:
                return history.get_balances(query)
            return history.get_history(query)
        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror("Оплаты", str(error), parent=self.root)
            return None

    def show_student_journal(self, student_id):
        """Переход от баланса к занятиям ученика."""
        if self.authenticator.current_user_id is None:
            return
        try:
            student = StudentRepository(self.db).get_by_id(student_id)
            if student is None:
                raise ValueError("Ученик не найден.")
            LessonService(self.db).complete_finished()
            journal = JournalService(self.db)
            past = journal.get_items(str(student_id), False, student.is_archived)
            planned = False
            if not past:
                planned = bool(
                    journal.get_items(str(student_id), True, student.is_archived)
                )
            opened = self.lessons_view.open_student(
                student_id, student.is_archived, planned
            )
        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror("Занятия", str(error), parent=self.root)
            return
        if opened:
            self.main_window.show_page("Занятия")

    def before_page_change(self, page):
        """Проверка несохранённых тем перед выходом из журнала."""
        if page != "Занятия":
            if not self.lessons_view.leave_editing():
                return False
        if page != "Настройки" and getattr(self, "settings_view", None) is not None:
            self.settings_view.clear_passwords()
        return True

    def load_journal(self, query="", planned=False, archived=False, silent=False):
        """Обновление статусов и чтение выбранного журнала."""
        if self.authenticator.current_user_id is None:
            return []
        try:
            changed = LessonService(self.db).complete_finished()
            if changed and getattr(self, "schedule_view", None) is not None:
                self.schedule_view.refresh()
            if changed and getattr(self, "payments_view", None) is not None:
                self.payments_view.refresh()
            return JournalService(self.db).get_items(query, planned, archived)
        except (sqlite3.Error, ValueError) as error:
            if not silent:
                messagebox.showerror("Занятия", str(error), parent=self.root)
            return None

    def save_journal_topics(self, changes):
        """Сохранение изменённых ячеек тем."""
        if self.authenticator.current_user_id is None:
            return False
        try:
            JournalService(self.db).save_topics(changes)
        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror("Темы занятия", str(error), parent=self.root)
            return False
        messagebox.showinfo("Темы занятия", "Темы сохранены.", parent=self.root)
        return True

    def show_lesson_in_journal(self, lesson_id):
        """Переход из расписания к нужной строке."""
        if self.authenticator.current_user_id is None:
            return
        try:
            LessonService(self.db).complete_finished()
            lesson = LessonRepository(self.db).get_by_id(lesson_id)
            if lesson is None or lesson.status == "Отменено":
                raise ValueError("Занятие не найдено или отменено.")
            enrollment = EnrollmentRepository(self.db).get_by_id(lesson.enrollment_id)
            student = StudentRepository(self.db).get_by_id(enrollment.student_id)
            opened = self.lessons_view.show_lesson(
                lesson_id,
                student.student_id,
                lesson.status == "Запланировано",
                student.is_archived,
            )
        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror("Занятия", str(error), parent=self.root)
            return
        if opened:
            self.main_window.show_page("Занятия")

    def pay_lesson(self, lesson_id):
        """Подтверждение оплаты выбранного занятия."""
        if self.authenticator.current_user_id is None:
            return
        try:
            lesson = LessonRepository(self.db).get_by_id(lesson_id)
            if lesson is None:
                raise ValueError("Занятие не найдено.")
            if lesson.status == "Отменено":
                raise ValueError("Нельзя оплатить отменённое занятие.")
            if PaymentRepository(self.db).get_by_lesson(lesson_id) is not None:
                raise ValueError("Это занятие уже оплачено.")
            if lesson.price_kopecks <= 0:
                raise ValueError("У занятия нулевая стоимость. Оплата не требуется.")
            enrollment = EnrollmentRepository(self.db).get_by_id(lesson.enrollment_id)
            student = StudentRepository(self.db).get_by_id(enrollment.student_id)
            subject = SubjectRepository(self.db).get_by_id(enrollment.subject_id)
            amount = lesson.price_kopecks
            money = str(amount // 100) + "," + str(amount % 100).zfill(2)
            text = (
                "Зарегистрировать оплату?\n\nУченик: "
                + student.full_name
                + "\nID ученика: "
                + str(student.student_id).zfill(5)
                + "\nПредмет: "
                + subject[1]
                + " — "
                + enrollment.preparation_goal
                + "\nЗанятие №"
                + str(lesson_id)
                + "\n"
                + lesson.starts_at.strftime("%d.%m.%Y %H:%M")
                + "–"
                + lesson.ends_at.strftime("%d.%m.%Y %H:%M")
                + "\nСумма: "
                + money
                + " руб."
                + "\n\nДата оплаты будет записана текущим московским временем."
            )
            if not messagebox.askyesno("Оплатить занятие", text, parent=self.root):
                return
            PaymentService(self.db).register_payment(lesson_id, amount)
        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror("Оплата занятия", str(error), parent=self.root)
            return
        self.schedule_view.refresh()
        self.schedule_view._select(lesson_id)
        if getattr(self, "lessons_view", None) is not None:
            self.lessons_view.refresh()
        if getattr(self, "payments_view", None) is not None:
            self.payments_view.refresh()
        messagebox.showinfo(
            "Оплата занятия", "Оплата зарегистрирована.", parent=self.root
        )

    def add_or_delete_lesson(self):
        """Действие первой кнопки расписания."""
        if self.schedule_view.cancelled_mode:
            self.delete_lesson()
        else:
            self.open_lesson_form()

    def delete_lesson(self):
        """Удаление отменённого занятия без оплаты."""
        if (
            self.authenticator.current_user_id is None
            or not self.schedule_view.cancelled_mode
        ):
            return
        lesson_id = self.schedule_view.selected_lesson_id
        if lesson_id is None:
            return
        try:
            lesson = LessonRepository(self.db).get_by_id(lesson_id)
            if lesson is None or lesson.status != "Отменено":
                raise ValueError("Выбери отменённое занятие.")
            if PaymentRepository(self.db).get_by_lesson(lesson_id) is not None:
                raise ValueError("У занятия есть оплата. Его нельзя удалить.")
            enrollment = EnrollmentRepository(self.db).get_by_id(lesson.enrollment_id)
            student = StudentRepository(self.db).get_by_id(enrollment.student_id)
            text = (
                "Удалить занятие из истории?\n\n"
                + student.full_name
                + "\n"
                + lesson.starts_at.strftime("%d.%m.%Y %H:%M")
                + "–"
                + lesson.ends_at.strftime("%d.%m.%Y %H:%M")
                + "\n\nВосстановить запись после удаления нельзя."
            )
            if not messagebox.askyesno("Удаление занятия", text, parent=self.root):
                return
            LessonService(self.db).delete(lesson_id)
        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror("Удаление занятия", str(error), parent=self.root)
            return
        self.schedule_view.refresh()
        messagebox.showinfo(
            "Удаление занятия", "Занятие удалено из истории.", parent=self.root
        )

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
                raise ValueError(
                    "Сначала добавь активного ученика во вкладке «Ученики»."
                )
        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror("Занятие", str(error), parent=self.root)
            return
        self.lesson_form = LessonForm(
            self.root,
            self.main_window.family,
            students,
            self.schedule_view.monday,
            int(self.schedule_view.half.get()),
            self.load_lesson_directions,
            self.save_lesson,
            self.close_lesson_form,
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

    def open_reschedule_form(self):
        """Перенос выбранного занятия."""
        if self.authenticator.current_user_id is None:
            return
        if self.lesson_form is not None:
            self.lesson_form.lift()
            return
        lesson_id = self.schedule_view.selected_lesson_id
        if lesson_id is None:
            return
        cancelled = self.schedule_view.cancelled_mode
        try:
            lesson = LessonRepository(self.db).get_by_id(lesson_id)
            if lesson is None:
                raise ValueError("Занятие не найдено.")
            if (lesson.status == "Отменено") != cancelled:
                raise ValueError("Состояние занятия изменилось. Обнови расписание.")
            enrollment = EnrollmentRepository(self.db).get_by_id(lesson.enrollment_id)
            student = StudentRepository(self.db).get_by_id(enrollment.student_id)
            subject = SubjectRepository(self.db).get_by_id(enrollment.subject_id)
            record = {"lesson": lesson, "enrollment": enrollment, "subject": subject[1]}
        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror("Перенос занятия", str(error), parent=self.root)
            return
        self.lesson_form = LessonForm(
            self.root,
            self.main_window.family,
            [student],
            self.schedule_view.monday,
            int(self.schedule_view.half.get()),
            self.load_lesson_directions,
            lambda data: self.reschedule_lesson(lesson_id, data, cancelled),
            self.close_lesson_form,
            record,
        )

    def reschedule_lesson(self, lesson_id, data, cancelled=False):
        """Смена даты и времени с прежней длительностью."""
        if self.authenticator.current_user_id is None:
            return
        try:
            lesson = LessonRepository(self.db).get_by_id(lesson_id)
            if lesson is None:
                raise ValueError("Занятие не найдено.")
            if (lesson.status == "Отменено") != cancelled:
                raise ValueError("Состояние занятия изменилось. Обнови расписание.")
            try:
                starts_at = datetime.strptime(
                    data["date"] + " " + data["time"], "%d.%m.%Y %H:%M"
                )
            except ValueError:
                raise ValueError("Укажи дату в формате ДД.ММ.ГГГГ и время ЧЧ:ММ.")
            ends_at = starts_at + (lesson.ends_at - lesson.starts_at)
            lesson = LessonService(self.db).reschedule(lesson_id, starts_at, ends_at)
        except (sqlite3.Error, ValueError, OverflowError) as error:
            messagebox.showerror("Перенос занятия", str(error), parent=self.root)
            return
        self.close_lesson_form()
        self.schedule_view.show_lesson(lesson)
        text = "Занятие перенесено."
        if cancelled:
            text = "Дата и время изменены. Занятие осталось отменённым."
        messagebox.showinfo("Перенос занятия", text, parent=self.root)

    def toggle_cancelled(self):
        """Переход к отменённым или обратно."""
        if self.authenticator.current_user_id is not None:
            self.schedule_view.set_cancelled_mode(not self.schedule_view.cancelled_mode)

    def change_lesson_status(self):
        """Отмена выбранного занятия."""
        if self.schedule_view.cancelled_mode:
            self.restore_lesson()
        else:
            self.cancel_lesson()

    def restore_lesson(self):
        """Возврат отменённого занятия в расписание."""
        if self.authenticator.current_user_id is None:
            return
        lesson_id = self.schedule_view.selected_lesson_id
        if lesson_id is None:
            return
        try:
            lesson = LessonService(self.db).restore(lesson_id)
        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror("Восстановление занятия", str(error), parent=self.root)
            return
        self.schedule_view.set_cancelled_mode(False)
        self.schedule_view.show_lesson(lesson)
        messagebox.showinfo(
            "Восстановление занятия", "Занятие восстановлено.", parent=self.root
        )

    def cancel_lesson(self):
        """Отмена выбранного занятия."""
        if self.authenticator.current_user_id is None:
            return
        lesson_id = self.schedule_view.selected_lesson_id
        if lesson_id is None:
            return
        try:
            lesson = LessonRepository(self.db).get_by_id(lesson_id)
            if lesson is None or lesson.status == "Отменено":
                raise ValueError("Выбери занятие в расписании.")
            enrollment = EnrollmentRepository(self.db).get_by_id(lesson.enrollment_id)
            student = StudentRepository(self.db).get_by_id(enrollment.student_id)
            text = (
                "Отменить занятие?\n\n"
                + student.full_name
                + "\n"
                + lesson.starts_at.strftime("%d.%m.%Y %H:%M")
                + "–"
                + lesson.ends_at.strftime("%d.%m.%Y %H:%M")
            )
            if not messagebox.askyesno("Отмена занятия", text, parent=self.root):
                return
            LessonService(self.db).cancel(lesson_id)
        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror("Отмена занятия", str(error), parent=self.root)
            return
        self.schedule_view.refresh()
        messagebox.showinfo("Отмена занятия", "Занятие отменено.", parent=self.root)

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
                starts_at = datetime.strptime(
                    data["date"] + " " + data["time"], "%d.%m.%Y %H:%M"
                )
            except ValueError:
                raise ValueError("Укажи дату в формате ДД.ММ.ГГГГ и время ЧЧ:ММ.")
            duration = duration_minutes(data["hours"], data["minutes"])
            lesson = LessonService(self.db).schedule(
                enrollment.enrollment_id, starts_at, duration
            )
        except (sqlite3.Error, ValueError, OverflowError) as error:
            messagebox.showerror("Занятие", str(error), parent=self.root)
            return
        self.close_lesson_form()
        self.schedule_view.show_lesson(lesson)
        amount = lesson.price_kopecks
        money = str(amount // 100) + "," + str(amount % 100).zfill(2)
        messagebox.showinfo(
            "Занятие",
            "Занятие добавлено. Стоимость: " + money + " руб.",
            parent=self.root,
        )

    def load_schedule(self, date_from, date_to, cancelled=False):
        """Занятия, пересекающиеся с выбранной неделей."""
        if self.authenticator.current_user_id is None:
            return []
        try:
            if date_from > date_to:
                raise ValueError("Начало периода позже его конца.")
            start = datetime(date_from.year, date_from.month, date_from.day)
            end = datetime(date_to.year, date_to.month, date_to.day) + timedelta(days=1)
            repository = LessonRepository(self.db)
            if cancelled:
                lessons = repository.get_cancelled(start, end)
            else:
                lessons = repository.get_overlapping(start, end)
            enrollments = EnrollmentRepository(self.db)
            students = StudentRepository(self.db)
            subjects = SubjectRepository(self.db)
            payments = PaymentRepository(self.db)
            items = []
            for lesson in lessons:
                enrollment = enrollments.get_by_id(lesson.enrollment_id)
                student = students.get_by_id(enrollment.student_id)
                subject = subjects.get_by_id(enrollment.subject_id)
                items.append(
                    {
                        "lesson": lesson,
                        "student_name": student.full_name,
                        "student_id": student.student_id,
                        "subject": subject[1],
                        "goal": enrollment.preparation_goal,
                        "paid": payments.get_by_lesson(lesson.lesson_id) is not None,
                    }
                )
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
            self.main_window.pages["Ученики"],
            self.main_window.family,
            self.save_student,
            self.close_student_form,
            record,
            lookup,
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
                parent=self.root,
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
        messagebox.showinfo("Ученики", text + str(student_id), parent=self.root)

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

                items.append(
                    {
                        "student": student,
                        "parents": parents.get_by_student(student.student_id),
                        "enrollments": directions,
                    }
                )

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
            messagebox.showerror("Регистрация", str(error), parent=self.root)

        else:
            self.backup_due = True
            messagebox.showinfo(
                "Регистрация", "Учётная запись создана.", parent=self.root
            )
            self.view.show_login(username.strip())

    def close(self):
        """Закрытие приложения."""
        if getattr(self, "lessons_view", None) is not None:
            if not self.lessons_view.leave_editing():
                return

        # Копия после работы
        while self.backup_due:
            try:
                self.db.backup()
            except (sqlite3.Error, OSError, ValueError) as error:
                retry = messagebox.askretrycancel(
                    "Резервная копия",
                    "Не удалось создать копию базы.\n"
                    + str(error)
                    + (
                        "\n\nПовторить? Нажми «Отмена», чтобы оставить программу "
                        "открытой."
                    ),
                    parent=self.root,
                )
                if not retry:
                    return
            else:
                self.backup_due = False

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
