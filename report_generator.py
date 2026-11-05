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

    def get_data(self, student_id, date_from, date_to):
        """Данные для предпросмотра и текстового файла."""
        for value in (date_from, date_to):
            if not isinstance(value, date) or isinstance(value, datetime):
                raise ValueError("Границы периода должны быть объектами date.")

        if date_from > date_to:
            raise ValueError("Начало периода позже его конца.")

        student = self.student_repository.get_by_id(student_id)

        if student is None:
            raise ValueError("Ученик с таким ID не найден.")

        # Начальный баланс
        opening = 0

        if date_from != date.min:
            opening = self.billing_service.calculate_balance(
                student_id, date_from - timedelta(days=1)
            )

        lessons = []
        charged = 0
        for lesson in self.lesson_repository.get_by_student(
            student_id, date_from, date_to
        ):
            if lesson.status != "Проведено":
                continue
            enrollment = self.enrollment_repository.get_by_id(lesson.enrollment_id)
            subject = self.subject_repository.get_by_id(enrollment.subject_id)
            lessons.append(
                {
                    "lesson": lesson,
                    "subject": subject[1],
                    "goal": enrollment.preparation_goal,
                }
            )
            charged += lesson.price_kopecks
        payments = self.payment_repository.get_by_student(
            student_id, date_from, date_to
        )

        moscow = timezone(timedelta(hours=3))
        created = datetime.now(moscow).strftime("%d.%m.%Y %H:%M")

        received = sum(payment.amount_kopecks for payment in payments)
        return {
            "student": student,
            "date_from": date_from,
            "date_to": date_to,
            "created": created,
            "opening": opening,
            "closing": opening + charged - received,
            "lessons": lessons,
            "payments": payments,
            "charged": charged,
            "received": received,
        }

    def make_text(self, data):
        """TXT из тех же данных, которые показаны на экране."""
        student = data["student"]

        lines = [
            "ОТЧЁТ О ЗАНЯТИЯХ И ОПЛАТАХ",
            "Ученик: " + student.full_name,
            "ID ученика: " + str(student.student_id),
            "Период: "
            + data["date_from"].strftime("%d.%m.%Y")
            + " — "
            + data["date_to"].strftime("%d.%m.%Y"),
            "Дата формирования: " + data["created"],
            "",
            "Баланс на начало периода: " + self._balance_text(data["opening"]),
            "",
            "ПРОВЕДЁННЫЕ ЗАНЯТИЯ",
        ]

        # Занятия и темы
        count = 0

        for item in data["lessons"]:
            lesson = item["lesson"]
            count += 1

            lines.append(
                str(count)
                + ". "
                + lesson.starts_at.strftime("%d.%m.%Y %H:%M")
                + " — "
                + lesson.ends_at.strftime("%d.%m.%Y %H:%M")
            )
            lines.append("Предмет: " + item["subject"])
            lines.append("Цель подготовки: " + item["goal"])
            lines.append("Стоимость: " + self._money(lesson.price_kopecks))

            if lesson.topics:
                lines.append("Темы: " + "; ".join(lesson.topics))
            else:
                lines.append("Темы не указаны")

            lines.append("")

        if count == 0:
            lines.append("Проведённых занятий за период нет.")

        lines.append("Количество занятий: " + str(count))
        lines.append("Начислено за период: " + self._money(data["charged"]))
        lines.append("")
        lines.append("ПОЛУЧЕННЫЕ ОПЛАТЫ")

        # Все поступления за период
        for payment in data["payments"]:

            lines.append(
                payment.paid_at.strftime("%d.%m.%Y %H:%M:%S")
                + " — занятие №"
                + str(payment.lesson_id)
                + " — "
                + self._money(payment.amount_kopecks)
            )

        if not data["payments"]:
            lines.append("Оплат за период нет.")

        lines.append("Получено за период: " + self._money(data["received"]))
        lines.append("")
        lines.append("Баланс на конец периода: " + self._balance_text(data["closing"]))

        return "\n".join(lines)

    def generate(self, student_id, date_from, date_to):
        """Текст отчёта за выбранные даты включительно."""
        return self.make_text(self.get_data(student_id, date_from, date_to))

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
            input("Начало периода (ДД.ММ.ГГГГ): ").strip(), "%d.%m.%Y"
        ).date()

        date_to = datetime.strptime(
            input("Конец периода (ДД.ММ.ГГГГ): ").strip(), "%d.%m.%Y"
        ).date()

        report = generator.generate(student_id, date_from, date_to)

        # Папка для отчётов
        folder = Path(__file__).resolve().parent / "reports"
        folder.mkdir(exist_ok=True)

        filename = (
            "report_"
            + str(student_id)
            + "_"
            + date_from.strftime("%Y%m%d")
            + "_"
            + date_to.strftime("%Y%m%d")
            + ".txt"
        )
        path = folder / filename
        generator.save(report, path)

        print(report)
        print("\nОтчёт сохранён:", path)

    except (sqlite3.Error, ValueError, OSError) as error:
        print("Ошибка:", error)

    finally:
        db.close()
