"""Правила работы с занятиями."""

from datetime import datetime, timedelta, timezone

from database import DatabaseManager
from enrollment_repository import EnrollmentRepository
from lesson import Lesson
from lesson_repository import LessonRepository


class LessonService:
    """Создание, перенос и изменение занятий."""

    def __init__(self, db):
        """Подключение репозиториев."""
        self.db = db
        self.lesson_repository = LessonRepository(db)
        self.enrollment_repository = EnrollmentRepository(db)

    def _now(self):
        """Текущее московское время."""
        moscow = timezone(timedelta(hours=3))
        return datetime.now(moscow).replace(tzinfo=None)

    def _begin(self):
        """Начало отдельной операции."""
        if self.db.connection.in_transaction:
            raise ValueError("Сначала сохрани или отмени предыдущие изменения.")

        self.db.connection.execute("BEGIN IMMEDIATE;")

    def _get_lesson(self, lesson_id):
        """Получение существующего занятия."""
        lesson = self.lesson_repository.get_by_id(lesson_id)

        if lesson is None:
            raise ValueError("Занятие с таким ID не найдено.")

        return lesson

    def _get_enrollment(self, enrollment_id):
        """Получение направления обучения."""
        enrollment = self.enrollment_repository.get_by_id(enrollment_id)

        if enrollment is None:
            raise ValueError("Направление обучения не найдено.")

        return enrollment

    def _check_slot(self, lesson):
        """Проверка времени по всему расписанию."""
        lesson.validate()

        if lesson.status == "Отменено":
            return

        overlapping = self.lesson_repository.get_overlapping(
            lesson.starts_at, lesson.ends_at, lesson.lesson_id
        )

        if overlapping:
            raise ValueError("На это время уже назначено другое занятие.")

    def _set_current_status(self, lesson):
        """Определение статуса по времени окончания."""
        if lesson.status != "Отменено":
            if lesson.ends_at <= self._now():
                lesson.status = "Проведено"
            else:
                lesson.status = "Запланировано"

    def schedule(self, enrollment_id, starts_at, duration_minutes):
        """Создание занятия с расчётом стоимости."""
        self._begin()

        with self.db.connection:
            enrollment = self._get_enrollment(enrollment_id)
            price = enrollment.calculate_price(duration_minutes)

            if not isinstance(starts_at, datetime):
                raise ValueError("Укажи дату и время начала занятия.")

            lesson = Lesson(
                enrollment_id=enrollment_id,
                starts_at=starts_at,
                ends_at=starts_at + timedelta(minutes=duration_minutes),
                price_kopecks=price,
            )

            self._set_current_status(lesson)
            self._check_slot(lesson)
            self.lesson_repository.add(lesson)

            return lesson

    def reschedule(self, lesson_id, starts_at, ends_at):
        """Перенос занятия и изменение длительности."""
        self._begin()

        with self.db.connection:
            lesson = self._get_lesson(lesson_id)
            old_duration = lesson.ends_at - lesson.starts_at

            lesson.starts_at = starts_at
            lesson.ends_at = ends_at
            lesson.validate()

            new_duration = ends_at - starts_at

            # Обычный перенос сохраняет стоимость
            if new_duration != old_duration:
                enrollment = self._get_enrollment(lesson.enrollment_id)
                minutes = int(new_duration.total_seconds() // 60)
                lesson.price_kopecks = enrollment.calculate_price(minutes)

            self._set_current_status(lesson)
            self._check_slot(lesson)
            self.lesson_repository.update(lesson)

            return lesson

    def cancel(self, lesson_id):
        """Отмена занятия с сохранением его данных."""
        self._begin()

        with self.db.connection:
            lesson = self._get_lesson(lesson_id)
            lesson.cancel()
            self.lesson_repository.update(lesson)

            return lesson

    def restore(self, lesson_id):
        """Восстановление с проверкой свободного времени."""
        self._begin()

        with self.db.connection:
            lesson = self._get_lesson(lesson_id)
            lesson.restore()

            self._set_current_status(lesson)
            self._check_slot(lesson)
            self.lesson_repository.update(lesson)

            return lesson

    def complete(self, lesson_id):
        """Отметка о проведении завершившегося занятия."""
        self._begin()

        with self.db.connection:
            lesson = self._get_lesson(lesson_id)

            if lesson.ends_at > self._now():
                raise ValueError("Время занятия ещё не закончилось.")

            lesson.complete()
            self.lesson_repository.update(lesson)

            return lesson

    def complete_finished(self):
        """Обновление статусов после окончания занятий."""
        self._begin()

        with self.db.connection:
            now = self._now()
            count = 0

            for lesson in self.lesson_repository.get_by_student():
                if lesson.status == "Запланировано" and lesson.ends_at <= now:
                    lesson.complete()
                    self.lesson_repository.update(lesson)
                    count += 1

            return count

    def set_topics(self, lesson_id, topics):
        """Сохранение тем занятия."""
        self._begin()

        with self.db.connection:
            lesson = self._get_lesson(lesson_id)
            lesson.topics = topics
            self.lesson_repository.update(lesson)

            return lesson

    def delete(self, lesson_id):
        """Удаление занятия с проверкой наличия оплаты."""
        self._begin()

        with self.db.connection:
            self.lesson_repository.delete(lesson_id)


# Проверка подключения
if __name__ == "__main__":
    db = DatabaseManager()

    try:
        service = LessonService(db)
        print("Сервис занятий готов.")
    finally:
        db.close()
