"""Проверка создания занятия."""

import sqlite3
from datetime import datetime

from database import DatabaseManager
from lesson_service import LessonService


db = DatabaseManager()

try:
    service = LessonService(db)

    # Данные занятия
    enrollment_id = int(input("ID направления обучения: "))
    date_text = input("Дата занятия (ДД.ММ.ГГГГ): ").strip()
    time_text = input("Время начала (ЧЧ:ММ): ").strip()
    duration = int(input("Длительность в минутах: "))

    starts_at = datetime.strptime(
        date_text + " " + time_text,
        "%d.%m.%Y %H:%M"
    )

    # Создание и сохранение
    lesson = service.schedule(enrollment_id, starts_at, duration)

    print("Занятие сохранено.")
    print("ID занятия:", lesson.lesson_id)
    print("Начало:", lesson.starts_at.strftime("%d.%m.%Y %H:%M"))
    print("Конец:", lesson.ends_at.strftime("%d.%m.%Y %H:%M"))
    print("Стоимость:", lesson.price_kopecks, "коп.")
    print("Статус:", lesson.status)

except (sqlite3.Error, ValueError) as error:
    print("Ошибка:", error)

finally:
    db.close()