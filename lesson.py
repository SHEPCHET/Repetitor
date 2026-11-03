"""Данные занятия."""

from datetime import datetime


class Lesson:
    """Время, стоимость, статус и темы занятия."""

    def __init__(
        self,
        enrollment_id,
        starts_at,
        ends_at,
        price_kopecks,
        lesson_id=None,
        status="Запланировано",
        topics=None
    ):
        """Заполнение данных занятия."""
        self.lesson_id = lesson_id
        self.enrollment_id = enrollment_id
        self.starts_at = starts_at
        self.ends_at = ends_at
        self.price_kopecks = price_kopecks
        self.status = status

        if topics is None:
            self.topics = []
        else:
            self.topics = topics

        self.validate()

    def validate(self):
        """Проверка данных занятия."""
        if not isinstance(self.starts_at, datetime):
            raise ValueError(
                "Начало занятия должно содержать дату и время."
            )

        if not isinstance(self.ends_at, datetime):
            raise ValueError(
                "Конец занятия должен содержать дату и время."
            )

        # Время указываем по Москве
        if (
            self.starts_at.tzinfo is not None
            or self.ends_at.tzinfo is not None
        ):
            raise ValueError(
                "Укажи московское время без часового пояса в объекте."
            )

        if (
            self.starts_at.second != 0
            or self.starts_at.microsecond != 0
            or self.ends_at.second != 0
            or self.ends_at.microsecond != 0
        ):
            raise ValueError(
                "Время нужно указывать с точностью до минуты."
            )

        if self.starts_at.minute not in (0, 30):
            raise ValueError(
                "Занятие должно начинаться в 00 или 30 минут."
            )

        duration = (self.ends_at - self.starts_at).total_seconds()

        if duration <= 0 or duration % 1800 != 0:
            raise ValueError(
                "Длительность должна быть больше 0 и кратна 30 минутам."
            )

        if (
            not isinstance(self.price_kopecks, int)
            or isinstance(self.price_kopecks, bool)
            or self.price_kopecks < 0
        ):
            raise ValueError(
                "Цена должна быть целым числом копеек от 0."
            )

        if self.status not in (
            "Запланировано", "Проведено", "Отменено"
        ):
            raise ValueError("Неизвестный статус занятия.")

        if not isinstance(self.topics, list):
            raise ValueError("Темы нужно передать списком.")

        # Проверка тем
        topics = []

        for topic in self.topics:
            if not isinstance(topic, str) or topic.strip() == "":
                raise ValueError(
                    "Название темы не должно быть пустым."
                )

            topics.append(topic.strip())

        self.topics = topics

    def complete(self):
        """Отметка о проведении занятия."""
        if self.status == "Отменено":
            raise ValueError(
                "Сначала восстанови отменённое занятие."
            )

        self.status = "Проведено"

    def cancel(self):
        """Отмена занятия."""
        self.status = "Отменено"

    def restore(self):
        """Восстановление отменённого занятия."""
        if self.status != "Отменено":
            raise ValueError("Это занятие не отменено.")

        self.status = "Запланировано"


# Проверка модели
if __name__ == "__main__":
    lesson = Lesson(
        enrollment_id=1,
        starts_at=datetime(2026, 11, 10, 10, 0),
        ends_at=datetime(2026, 11, 10, 11, 0),
        price_kopecks=140000
    )

    print("Начало:", lesson.starts_at.strftime("%d.%m.%Y %H:%M"))
    print("Конец:", lesson.ends_at.strftime("%d.%m.%Y %H:%M"))
    print("Стоимость:", lesson.price_kopecks, "коп.")
    print("Статус:", lesson.status)

    lesson.cancel()
    print("После отмены:", lesson.status)

    lesson.restore()
    print("После восстановления:", lesson.status)

    lesson.complete()
    print("После проведения:", lesson.status)