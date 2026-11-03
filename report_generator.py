"""Формирование отчёта для родителей."""

import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from billing_service import BillingService
from database import DatabaseManager
from enrollment_repository import EnrollmentRepository
from lesson_repository import LessonRepository
from payment_repository import PaymentRepository
from student_repository import StudentRepository
from subject_repository import SubjectRepository


class ReportGenerator:
    """Отчёт ученика за выбранный период."""

    def __init__(self, db):
        """Подключение репозиториев и расчётов."""
        self.student_repository = StudentRepository(db)
        self.enrollment_repository = EnrollmentRepository(db)
        self.subject_repository = SubjectRepository(db)
        self.lesson_repository = LessonRepository(db)
        self.payment_repository = PaymentRepository(db)
        self.billing_service = BillingService(db)

    def _money(self, amount):
        """Перевод целых копеек в текст с рублями."""
        rubles = amount // 100
        kopecks = str(amount % 100).zfill(2)

        return str(rubles) + "," + kopecks + " руб."

    def _balance_text(self, balance):
        """Подпись долга или переплаты."""
        if balance > 0:
            return "Долг: " + self._money(balance)

        if balance < 0:
            return "Переплата: " + self._money(-balance)

        return self._money(0)

    def generate(self, student_id, date_from, date_to):
        """Текст отчёта за период с обеими граничными датами."""
        for value in (date_from, date_to):
            if (
                not isinstance(value, date)
                or isinstance(value, datetime)
            ):
                raise ValueError(
                    "Границы периода должны быть объектами date."
                )

        if date_from > date_to:
            raise ValueError("Начало периода позже его конца.")

        student = self.student_repository.get_by_id(student_id)

        if student is None:
            raise ValueError("Ученик с таким ID не найден.")

        # Начальный баланс
        opening = 0

        if date_from != date.min:
            opening = self.billing_service.calculate_balance(
                student_id,
                date_from - timedelta(days=1)
            )

        lessons = self.lesson_repository.get_by_student(
            student_id, date_from, date_to
        )
        payments = self.payment_repository.get_by_student(
            student_id, date_from, date_to
        )

        moscow = timezone(timedelta(hours=3))
        created = datetime.now(moscow).strftime("%d.%m.%Y %H:%M")

        lines = [
            "ОТЧЁТ О ЗАНЯТИЯХ И ОПЛАТАХ",
            "Ученик: " + student.full_name,
            "ID ученика: " + str(student.student_id),
            "Период: " + date_from.strftime("%d.%m.%Y")
            + " — " + date_to.strftime("%d.%m.%Y"),
            "Дата формирования: " + created,
            "",
            "Баланс на начало периода: "
            + self._balance_text(opening),
            "",
            "ПРОВЕДЁННЫЕ ЗАНЯТИЯ"
        ]

        # Занятия и темы
        charged = 0
        count = 0

        for lesson in lessons:
            if lesson.status != "Проведено":
                continue

            enrollment = self.enrollment_repository.get_by_id(
                lesson.enrollment_id
            )
            subject = self.subject_repository.get_by_id(
                enrollment.subject_id
            )

            count += 1
            charged += lesson.price_kopecks

            lines.append(
                str(count) + ". "
                + lesson.starts_at.strftime("%d.%m.%Y %H:%M")
                + " — "
                + lesson.ends_at.strftime("%d.%m.%Y %H:%M")
            )
            lines.append("Предмет: " + subject[1])
            lines.append(
                "Цель подготовки: " + enrollment.preparation_goal
            )
            lines.append(
                "Стоимость: " + self._money(lesson.price_kopecks)
            )

            if lesson.topics:
                lines.append("Темы: " + "; ".join(lesson.topics))
            else:
                lines.append("Темы не указаны")

            lines.append("")

        if count == 0:
            lines.append("Проведённых занятий за период нет.")

        lines.append("Количество занятий: " + str(count))
        lines.append(
            "Начислено за период: " + self._money(charged)
        )
        lines.append("")
        lines.append("ПОЛУЧЕННЫЕ ОПЛАТЫ")

        # Все поступления за период
        received = 0

        for payment in payments:
            received += payment.amount_kopecks

            lines.append(
                payment.paid_at.strftime("%d.%m.%Y %H:%M:%S")
                + " — занятие №" + str(payment.lesson_id)
                + " — " + self._money(payment.amount_kopecks)
            )

        if not payments:
            lines.append("Оплат за период нет.")

        closing = opening + charged - received

        lines.append(
            "Получено за период: " + self._money(received)
        )
        lines.append("")
        lines.append(
            "Баланс на конец периода: "
            + self._balance_text(closing)
        )

        return "\n".join(lines)

    def save(self, report, path):
        """Сохранение отчёта в TXT."""
        with open(path, "w", encoding="utf-8") as file:
            file.write(report)


# Проверка отчёта
if __name__ == "__main__":
    db = DatabaseManager()

    try:
        generator = ReportGenerator(db)
        student_id = int(input("ID ученика: "))

        date_from = datetime.strptime(
            input("Начало периода (ДД.ММ.ГГГГ): ").strip(),
            "%d.%m.%Y"
        ).date()

        date_to = datetime.strptime(
            input("Конец периода (ДД.ММ.ГГГГ): ").strip(),
            "%d.%m.%Y"
        ).date()

        report = generator.generate(student_id, date_from, date_to)

        # Папка для отчётов
        folder = Path(__file__).resolve().parent / "reports"
        folder.mkdir(exist_ok=True)

        filename = (
            "report_" + str(student_id) + "_"
            + date_from.strftime("%Y%m%d") + "_"
            + date_to.strftime("%Y%m%d") + ".txt"
        )
        path = folder / filename
        generator.save(report, path)

        print(report)
        print("\nОтчёт сохранён:", path)

    except (sqlite3.Error, ValueError, OSError) as error:
        print("Ошибка:", error)

    finally:
        db.close()