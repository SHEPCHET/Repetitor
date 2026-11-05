"""История платежей и балансы учеников."""

from billing_service import BillingService
from student_repository import StudentRepository
from lesson_repository import LessonRepository
from enrollment_repository import EnrollmentRepository
from subject_repository import SubjectRepository
from payment_repository import PaymentRepository


class PaymentHistory:
    def __init__(self, db):
        self.db = db

    def get_history(self, query=""):
        """Платежи активных и архивных учеников."""
        students = {}
        for student in StudentRepository(self.db).search(query, None):
            students[student.student_id] = student
        lessons = LessonRepository(self.db)
        enrollments = EnrollmentRepository(self.db)
        subjects = SubjectRepository(self.db)
        items = []
        for payment in PaymentRepository(self.db).get_by_student():
            if payment.student_id not in students:
                continue
            lesson = lessons.get_by_id(payment.lesson_id)
            enrollment = enrollments.get_by_id(lesson.enrollment_id)
            items.append({"payment": payment, "student": students[payment.student_id],
                          "lesson": lesson, "subject": subjects.get_by_id(enrollment.subject_id)[1],
                          "goal": enrollment.preparation_goal})
        return items

    def get_balances(self, query=""):
        """Один общий баланс на ученика."""
        billing = BillingService(self.db)
        items = []
        for student in StudentRepository(self.db).search(query, None):
            items.append({"student": student, "summary": billing.get_summary(student.student_id)})
        return items
