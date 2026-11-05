"""Запросы для работы с оплатами."""

from datetime import datetime

from database import DatabaseManager
from payment import Payment


class PaymentRepository:
    """Сохранение и чтение оплат занятий."""

    def __init__(self, db):
        """Подключение к базе."""
        self.db = db
        self.db.connect()

    def _make_payment(self, row):
        """Получение оплаты из строки базы."""
        if row is None:
            return None

        return Payment(
            payment_id=row[0],
            student_id=row[1],
            lesson_id=row[2],
            paid_at=datetime.strptime(row[3], "%Y-%m-%d %H:%M:%S"),
            amount_kopecks=row[4],
        )

    def add(self, payment):
        """Добавление полной оплаты одного занятия."""
        payment.validate()

        if payment.payment_id is not None:
            raise ValueError("У новой оплаты ещё не должно быть ID.")

        lesson = self.db.connection.execute(
            """
            SELECT e.student_id, l.price_kopecks
            FROM lessons AS l
            JOIN enrollments AS e ON l.enrollment_id = e.enrollment_id
            WHERE l.lesson_id = ?;
        """,
            [payment.lesson_id],
        ).fetchone()

        if lesson is None:
            raise ValueError("Занятие не найдено.")

        if lesson[0] != payment.student_id:
            raise ValueError("Это занятие принадлежит другому ученику.")

        if lesson[1] != payment.amount_kopecks:
            raise ValueError("Сумма оплаты должна совпадать со стоимостью занятия.")

        if self.get_by_lesson(payment.lesson_id) is not None:
            raise ValueError("Это занятие уже оплачено.")

        cursor = self.db.connection.execute(
            """
            INSERT INTO payments (
                student_id, lesson_id, paid_at, amount_kopecks
            )
            VALUES (?, ?, ?, ?);
        """,
            [
                payment.student_id,
                payment.lesson_id,
                payment.paid_at.strftime("%Y-%m-%d %H:%M:%S"),
                payment.amount_kopecks,
            ],
        )

        payment.payment_id = cursor.lastrowid

    def get_by_id(self, payment_id):
        """Поиск оплаты по ID."""
        row = self.db.connection.execute(
            """
            SELECT payment_id, student_id, lesson_id,
                   paid_at, amount_kopecks
            FROM payments WHERE payment_id = ?;
        """,
            [payment_id],
        ).fetchone()

        return self._make_payment(row)

    def get_by_lesson(self, lesson_id):
        """Оплата выбранного занятия или None."""
        row = self.db.connection.execute(
            """
            SELECT payment_id, student_id, lesson_id,
                   paid_at, amount_kopecks
            FROM payments WHERE lesson_id = ?;
        """,
            [lesson_id],
        ).fetchone()

        return self._make_payment(row)

    def get_by_student(self, student_id=None, date_from=None, date_to=None):
        """Оплаты за период. Без ID — всех учеников."""
        if date_from is not None and date_to is not None:
            if date_from > date_to:
                raise ValueError("Начало периода позже его конца.")

        if date_from is not None:
            date_from = date_from.strftime("%Y-%m-%d")

        if date_to is not None:
            date_to = date_to.strftime("%Y-%m-%d")

        rows = self.db.connection.execute(
            """
            SELECT payment_id, student_id, lesson_id,
                   paid_at, amount_kopecks
            FROM payments
            WHERE (? IS NULL OR student_id = ?)
              AND (? IS NULL OR date(paid_at) >= ?)
              AND (? IS NULL OR date(paid_at) <= ?)
            ORDER BY paid_at DESC, payment_id DESC;
        """,
            [student_id, student_id, date_from, date_from, date_to, date_to],
        ).fetchall()

        payments = []
        for row in rows:
            payments.append(self._make_payment(row))

        return payments

    def get_total(self, student_id, as_of=None):
        """Все полученные оплаты ученика в копейках."""
        if as_of is not None:
            as_of = as_of.strftime("%Y-%m-%d")

        row = self.db.connection.execute(
            """
            SELECT COALESCE(SUM(amount_kopecks), 0)
            FROM payments
            WHERE student_id = ?
              AND (? IS NULL OR date(paid_at) <= ?);
        """,
            [student_id, as_of, as_of],
        ).fetchone()

        return row[0]


# Проверка чтения
if __name__ == "__main__":
    db = DatabaseManager()

    try:
        repository = PaymentRepository(db)
        payments = repository.get_by_student()

        print("Количество оплат:", len(payments))

        for payment in payments:
            print("ID оплаты:", payment.payment_id)
            print("ID занятия:", payment.lesson_id)
            print("Сумма:", payment.amount_kopecks, "коп.")
    finally:
        db.close()
