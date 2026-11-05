"""Данные оплаты занятия."""

from datetime import datetime


class Payment:
    """Оплата одного занятия."""

    def __init__(self, student_id, lesson_id, paid_at, amount_kopecks, payment_id=None):
        """Заполнение данных оплаты."""
        self.payment_id = payment_id
        self.student_id = student_id
        self.lesson_id = lesson_id
        self.paid_at = paid_at
        self.amount_kopecks = amount_kopecks
        self.validate()

    def validate(self):
        """Проверка данных оплаты."""
        for value in (self.student_id, self.lesson_id):
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(
                    "ID ученика и занятия должны быть целыми числами больше 0."
                )

        if not isinstance(self.paid_at, datetime):
            raise ValueError("Укажи дату и время оплаты.")

        if self.paid_at.tzinfo is not None:
            raise ValueError("Укажи московское время без часового пояса в объекте.")

        if (
            not isinstance(self.amount_kopecks, int)
            or isinstance(self.amount_kopecks, bool)
            or self.amount_kopecks <= 0
        ):
            raise ValueError("Сумма должна быть целым числом копеек больше 0.")

        return True


# Проверка модели
if __name__ == "__main__":
    payment = Payment(
        student_id=1,
        lesson_id=1,
        paid_at=datetime(2026, 11, 3, 12, 0),
        amount_kopecks=210000,
    )

    print("ID ученика:", payment.student_id)
    print("ID занятия:", payment.lesson_id)
    print("Дата оплаты:", payment.paid_at.strftime("%d.%m.%Y %H:%M"))
    print("Сумма:", payment.amount_kopecks, "коп.")
    print("Проверка данных:", payment.validate())
