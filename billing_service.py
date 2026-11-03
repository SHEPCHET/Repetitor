"""Расчёт долга и аванса ученика."""

import sqlite3
from datetime import date, datetime

from database import DatabaseManager
from lesson_repository import LessonRepository
from payment_repository import PaymentRepository
from student_repository import StudentRepository


class BillingService:
    """Расчёты по проведённым занятиям и оплатам."""

    def __init__(self, db):
        """Подключение репозиториев."""
        self.student_repository = StudentRepository(db)
        self.lesson_repository = LessonRepository(db)
        self.payment_repository = PaymentRepository(db)

    def get_summary(self, student_id, as_of=None):
        """Начисления, оплаты, долг и аванс."""
        if self.student_repository.get_by_id(student_id) is None:
            raise ValueError("Ученик с таким ID не найден.")

        if as_of is not None:
            if not isinstance(as_of, date) or isinstance(as_of, datetime):
                raise ValueError(
                    "Дата расчёта должна быть объектом date."
                )

        charged = self.lesson_repository.get_total_completed(
            student_id, as_of
        )
        received = self.payment_repository.get_total(
            student_id, as_of
        )

        balance = charged - received
        debt = 0
        advance = 0

        if balance > 0:
            debt = balance
        elif balance < 0:
            advance = -balance

        return {
            "charged": charged,
            "received": received,
            "balance": balance,
            "debt": debt,
            "advance": advance
        }

    def calculate_balance(self, student_id, as_of=None):
        """Баланс в копейках: плюс — долг, минус — аванс."""
        summary = self.get_summary(student_id, as_of)
        return summary["balance"]


# Проверка расчёта
if __name__ == "__main__":
    db = DatabaseManager()

    try:
        service = BillingService(db)
        student_id = int(input("ID ученика: "))
        summary = service.get_summary(student_id)

        print("Начислено:", summary["charged"], "коп.")
        print("Получено:", summary["received"], "коп.")
        print("Долг:", summary["debt"], "коп.")
        print("Аванс:", summary["advance"], "коп.")

    except (sqlite3.Error, ValueError) as error:
        print("Ошибка:", error)

    finally:
        db.close()