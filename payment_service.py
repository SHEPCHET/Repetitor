"""Регистрация оплаты выбранного занятия."""

import sqlite3
from datetime import datetime, timedelta, timezone

from database import DatabaseManager
from enrollment_repository import EnrollmentRepository
from lesson_repository import LessonRepository
from payment import Payment
from payment_repository import PaymentRepository


class PaymentService:
    """Полная оплата занятия."""

    def __init__(self, db):
        """Подключение репозиториев."""
        self.db = db
        self.lesson_repository = LessonRepository(db)
        self.enrollment_repository = EnrollmentRepository(db)
        self.payment_repository = PaymentRepository(db)

    def register_payment(self, lesson_id, expected_amount=None):
        """Сохранение оплаты выбранного занятия."""
        if (
            not isinstance(lesson_id, int)
            or isinstance(lesson_id, bool)
            or lesson_id <= 0
        ):
            raise ValueError("ID занятия должен быть целым числом больше 0.")

        if self.db.connection.in_transaction:
            raise ValueError("Сначала сохрани или отмени предыдущие изменения.")

        self.db.connection.execute("BEGIN IMMEDIATE;")

        with self.db.connection:
            lesson = self.lesson_repository.get_by_id(lesson_id)

            if lesson is None:
                raise ValueError("Занятие с таким ID не найдено.")
            if lesson.status == "Отменено":
                raise ValueError("Нельзя оплатить отменённое занятие.")
            if expected_amount is not None and lesson.price_kopecks != expected_amount:
                raise ValueError(
                    "Стоимость занятия изменилась. Проверь сумму и повтори оплату."
                )

            enrollment = self.enrollment_repository.get_by_id(lesson.enrollment_id)

            if enrollment is None:
                raise ValueError("Направление обучения не найдено.")

            # Текущее московское время
            moscow = timezone(timedelta(hours=3))
            paid_at = datetime.now(moscow).replace(tzinfo=None, microsecond=0)

            payment = Payment(
                student_id=enrollment.student_id,
                lesson_id=lesson.lesson_id,
                paid_at=paid_at,
                amount_kopecks=lesson.price_kopecks,
            )

            self.payment_repository.add(payment)
            return payment


# Проверка оплаты
if __name__ == "__main__":
    db = DatabaseManager()

    try:
        service = PaymentService(db)
        lesson_id = int(input("ID занятия для оплаты: "))
        payment = service.register_payment(lesson_id)

        print("Оплата сохранена.")
        print("ID оплаты:", payment.payment_id)
        print("ID ученика:", payment.student_id)
        print("ID занятия:", payment.lesson_id)
        print("Сумма:", payment.amount_kopecks, "коп.")
        print("Дата оплаты:", payment.paid_at.strftime("%d.%m.%Y %H:%M:%S"))

    except (sqlite3.Error, ValueError) as error:
        print("Ошибка:", error)

    finally:
        db.close()
