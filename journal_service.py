"""Данные журнала и сохранение тем."""

from student_repository import StudentRepository
from enrollment_repository import EnrollmentRepository
from subject_repository import SubjectRepository
from lesson_repository import LessonRepository
from payment_repository import PaymentRepository


class JournalService:
    """Чтение журнала и сохранение тем занятий."""

    def __init__(self, db):
        """Подготовка данных и элементов объекта."""
        self.db = db

    def get_items(self, query="", planned=False, archived=False):
        """Поиск по ученику и выбранному разделу."""
        students = {}
        for student in StudentRepository(self.db).search(query, archived):
            students[student.student_id] = student
        enrollments = EnrollmentRepository(self.db)
        subjects = SubjectRepository(self.db)
        payments = PaymentRepository(self.db)
        paid_ids = {payment.lesson_id for payment in payments.get_by_student()}
        saved_enrollments = {}
        saved_subjects = {}
        status = "Запланировано" if planned else "Проведено"
        items = []
        for lesson in LessonRepository(self.db).get_by_student():
            if lesson.status != status:
                continue
            if lesson.enrollment_id not in saved_enrollments:
                saved_enrollments[lesson.enrollment_id] = enrollments.get_by_id(
                    lesson.enrollment_id
                )
            enrollment = saved_enrollments[lesson.enrollment_id]
            if enrollment.student_id not in students:
                continue
            if enrollment.subject_id not in saved_subjects:
                saved_subjects[enrollment.subject_id] = subjects.get_by_id(
                    enrollment.subject_id
                )[1]
            items.append(
                {
                    "lesson": lesson,
                    "student": students[enrollment.student_id],
                    "subject": saved_subjects[enrollment.subject_id],
                    "goal": enrollment.preparation_goal,
                    "paid": lesson.lesson_id in paid_ids,
                }
            )
        items.sort(
            key=lambda item: (item["lesson"].starts_at, item["lesson"].lesson_id),
            reverse=not planned,
        )
        return items

    def save_topics(self, changes):
        """Все изменённые темы сохраняются вместе."""
        repository = LessonRepository(self.db)
        if self.db.connection.in_transaction:
            raise ValueError("Сначала сохрани или отмени предыдущие изменения.")
        self.db.connection.execute("BEGIN IMMEDIATE;")
        with self.db.connection:
            for lesson_id, values in changes.items():
                lesson = repository.get_by_id(lesson_id)
                if lesson is None or lesson.status != "Проведено":
                    raise ValueError(
                        "Темы можно менять только у существующего проведённого занятия."
                    )
                if lesson.topics != values["original"]:
                    raise ValueError(
                        (
                            "Темы уже изменились. Отмени редактирование и загрузи "
                            "журнал заново."
                        )
                    )
                lesson.topics = values["topics"]
                lesson.validate()
                repository.update(lesson)
