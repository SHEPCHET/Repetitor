"""Запросы для работы с занятиями."""

from datetime import datetime

from database import DatabaseManager
from lesson import Lesson


class LessonRepository:
    """Занятия и их темы в базе."""

    def __init__(self, db):
        """Подключение к базе."""
        self.db = db
        self.db.connect()

    def _make_lesson(self, row):
        """Получение занятия из строки базы."""
        if row is None:
            return None

        rows = self.db.connection.execute("""
            SELECT topic_name FROM lesson_topics
            WHERE lesson_id = ? ORDER BY lesson_topic_id;
        """, [row[0]]).fetchall()

        topics = []
        for topic in rows:
            topics.append(topic[0])

        return Lesson(
            lesson_id=row[0],
            enrollment_id=row[1],
            starts_at=datetime.strptime(row[2], "%Y-%m-%d %H:%M:%S"),
            ends_at=datetime.strptime(row[3], "%Y-%m-%d %H:%M:%S"),
            price_kopecks=row[4],
            status=row[5],
            topics=topics
        )

    def _read_list(self, query, parameters):
        """Получение списка занятий по запросу."""
        rows = self.db.connection.execute(query, parameters).fetchall()

        lessons = []
        for row in rows:
            lessons.append(self._make_lesson(row))

        return lessons

    def _check_lesson(self, lesson):
        """Проверка занятия и направления обучения."""
        lesson.validate()

        row = self.db.connection.execute("""
            SELECT student_id FROM enrollments
            WHERE enrollment_id = ?;
        """, [lesson.enrollment_id]).fetchone()

        if row is None:
            raise ValueError("Направление обучения не найдено.")

        return row[0]

    def _save_topics(self, lesson):
        """Запись списка тем занятия."""
        self.db.connection.execute("""
            DELETE FROM lesson_topics WHERE lesson_id = ?;
        """, [lesson.lesson_id])

        for topic in lesson.topics:
            self.db.connection.execute("""
                INSERT INTO lesson_topics (lesson_id, topic_name)
                VALUES (?, ?);
            """, [lesson.lesson_id, topic])

    def add(self, lesson):
        """Добавление занятия вместе с темами."""
        if lesson.lesson_id is not None:
            raise ValueError("У нового занятия ещё не должно быть ID.")

        self._check_lesson(lesson)

        cursor = self.db.connection.execute("""
            INSERT INTO lessons (
                enrollment_id, starts_at, ends_at, price_kopecks, status
            )
            VALUES (?, ?, ?, ?, ?);
        """, [
            lesson.enrollment_id,
            lesson.starts_at.strftime("%Y-%m-%d %H:%M:%S"),
            lesson.ends_at.strftime("%Y-%m-%d %H:%M:%S"),
            lesson.price_kopecks,
            lesson.status
        ])

        lesson.lesson_id = cursor.lastrowid
        self._save_topics(lesson)

    def get_by_id(self, lesson_id):
        """Поиск занятия по ID."""
        row = self.db.connection.execute("""
            SELECT lesson_id, enrollment_id, starts_at, ends_at,
                   price_kopecks, status
            FROM lessons WHERE lesson_id = ?;
        """, [lesson_id]).fetchone()

        return self._make_lesson(row)

    def get_by_enrollment(self, enrollment_id):
        """Занятия выбранного направления."""
        return self._read_list("""
            SELECT lesson_id, enrollment_id, starts_at, ends_at,
                   price_kopecks, status
            FROM lessons WHERE enrollment_id = ?
            ORDER BY starts_at, lesson_id;
        """, [enrollment_id])

    def get_by_student(self, student_id=None, date_from=None, date_to=None):
        """Занятия ученика за период. Без ID — всех учеников."""
        if date_from is not None and date_to is not None:
            if date_from > date_to:
                raise ValueError("Начало периода позже его конца.")

        if date_from is not None:
            date_from = date_from.strftime("%Y-%m-%d")

        if date_to is not None:
            date_to = date_to.strftime("%Y-%m-%d")

        return self._read_list("""
            SELECT l.lesson_id, l.enrollment_id, l.starts_at, l.ends_at,
                   l.price_kopecks, l.status
            FROM lessons AS l
            JOIN enrollments AS e ON l.enrollment_id = e.enrollment_id
            WHERE (? IS NULL OR e.student_id = ?)
              AND (? IS NULL OR date(l.starts_at) >= ?)
              AND (? IS NULL OR date(l.starts_at) <= ?)
            ORDER BY l.starts_at, l.lesson_id;
        """, [
            student_id, student_id,
            date_from, date_from,
            date_to, date_to
        ])

    def get_overlapping(self, starts_at, ends_at, exclude_lesson_id=None):
        """Занятия, пересекающиеся с выбранным временем."""
        return self._read_list("""
            SELECT lesson_id, enrollment_id, starts_at, ends_at,
                   price_kopecks, status
            FROM lessons
            WHERE status != 'Отменено'
              AND starts_at < ? AND ends_at > ?
              AND (? IS NULL OR lesson_id != ?)
            ORDER BY starts_at, lesson_id;
        """, [
            ends_at.strftime("%Y-%m-%d %H:%M:%S"),
            starts_at.strftime("%Y-%m-%d %H:%M:%S"),
            exclude_lesson_id,
            exclude_lesson_id
        ])

    def get_cancelled(self, starts_at, ends_at):
        """Отменённые занятия выбранного периода."""
        return self._read_list("""
            SELECT lesson_id, enrollment_id, starts_at, ends_at,
                   price_kopecks, status
            FROM lessons
            WHERE status = 'Отменено'
              AND starts_at < ? AND ends_at > ?
            ORDER BY starts_at, lesson_id;
        """, [ends_at.strftime("%Y-%m-%d %H:%M:%S"),
              starts_at.strftime("%Y-%m-%d %H:%M:%S")])

    def get_total_completed(self, student_id, as_of=None):
        """Стоимость проведённых занятий в копейках."""
        if as_of is not None:
            as_of = as_of.strftime("%Y-%m-%d")

        row = self.db.connection.execute("""
            SELECT COALESCE(SUM(l.price_kopecks), 0)
            FROM lessons AS l
            JOIN enrollments AS e ON l.enrollment_id = e.enrollment_id
            WHERE e.student_id = ? AND l.status = 'Проведено'
              AND (? IS NULL OR date(l.starts_at) <= ?);
        """, [student_id, as_of, as_of]).fetchone()

        return row[0]

    def update(self, lesson):
        """Изменение занятия и его тем."""
        if self.get_by_id(lesson.lesson_id) is None:
            raise ValueError("Занятие с таким ID не найдено.")

        student_id = self._check_lesson(lesson)

        # Согласованность с оплатой
        payment = self.db.connection.execute("""
            SELECT student_id, amount_kopecks FROM payments
            WHERE lesson_id = ?;
        """, [lesson.lesson_id]).fetchone()

        if payment is not None:
            if payment[0] != student_id:
                raise ValueError(
                    "Оплаченное занятие нельзя передать другому ученику."
                )

            if payment[1] != lesson.price_kopecks:
                raise ValueError(
                    "Нельзя менять стоимость оплаченного занятия."
                )

        self.db.connection.execute("""
            UPDATE lessons
            SET enrollment_id = ?, starts_at = ?, ends_at = ?,
                price_kopecks = ?, status = ?
            WHERE lesson_id = ?;
        """, [
            lesson.enrollment_id,
            lesson.starts_at.strftime("%Y-%m-%d %H:%M:%S"),
            lesson.ends_at.strftime("%Y-%m-%d %H:%M:%S"),
            lesson.price_kopecks,
            lesson.status,
            lesson.lesson_id
        ])

        self._save_topics(lesson)

    def delete(self, lesson_id):
        """Удаление занятия без оплаты."""
        payment = self.db.connection.execute("""
            SELECT payment_id FROM payments WHERE lesson_id = ?;
        """, [lesson_id]).fetchone()

        if payment is not None:
            raise ValueError(
                "У занятия есть оплата. Его нельзя удалить."
            )

        self.db.connection.execute("""
            DELETE FROM lesson_topics WHERE lesson_id = ?;
        """, [lesson_id])

        cursor = self.db.connection.execute("""
            DELETE FROM lessons WHERE lesson_id = ?;
        """, [lesson_id])

        if cursor.rowcount == 0:
            raise ValueError("Занятие с таким ID не найдено.")


# Проверка чтения
if __name__ == "__main__":
    db = DatabaseManager()

    try:
        repository = LessonRepository(db)
        lessons = repository.get_by_student()

        print("Количество занятий:", len(lessons))

        for lesson in lessons:
            print("ID:", lesson.lesson_id)
            print(
                "Начало:",
                lesson.starts_at.strftime("%d.%m.%Y %H:%M")
            )
            print("Статус:", lesson.status)
    finally:
        db.close()
