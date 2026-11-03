"""Запросы для работы с направлениями обучения."""

from database import DatabaseManager
from models import Enrollment


class EnrollmentRepository:
    """Сохранение предмета, цели подготовки и цены."""

    def __init__(self, db):
        """Подключение к базе."""
        self.db = db
        self.db.connect()

    def _make_enrollment(self, row):
        """Получение направления из строки базы."""
        if row is None:
            return None

        return Enrollment(
            enrollment_id=row[0],
            student_id=row[1],
            subject_id=row[2],
            preparation_goal=row[3],
            price_60_kopecks=row[4]
        )

    def _check_enrollment(self, enrollment):
        """Проверка данных перед записью."""
        enrollment.change_goal(enrollment.preparation_goal)
        price = enrollment.price_60_kopecks

        if not isinstance(price, int) or isinstance(price, bool) or price < 0:
            raise ValueError("Цена должна быть целым числом копеек от 0.")

        student = self.db.connection.execute("""
            SELECT student_id FROM students WHERE student_id = ?;
        """, [enrollment.student_id]).fetchone()

        if student is None:
            raise ValueError("Ученик не найден.")

        subject = self.db.connection.execute("""
            SELECT subject_id FROM subjects WHERE subject_id = ?;
        """, [enrollment.subject_id]).fetchone()

        if subject is None:
            raise ValueError("Предмет не найден.")

    def add(self, enrollment):
        """Добавление направления обучения."""
        self._check_enrollment(enrollment)

        if enrollment.enrollment_id is not None:
            raise ValueError("У нового направления ещё не должно быть ID.")

        cursor = self.db.connection.execute("""
            INSERT INTO enrollments (
                student_id, subject_id, preparation_goal, price_60_kopecks
            )
            VALUES (?, ?, ?, ?);
        """, [
            enrollment.student_id,
            enrollment.subject_id,
            enrollment.preparation_goal,
            enrollment.price_60_kopecks
        ])

        enrollment.enrollment_id = cursor.lastrowid

    def get_by_id(self, enrollment_id):
        """Поиск направления по ID."""
        row = self.db.connection.execute("""
            SELECT enrollment_id, student_id, subject_id,
                   preparation_goal, price_60_kopecks
            FROM enrollments
            WHERE enrollment_id = ?;
        """, [enrollment_id]).fetchone()

        return self._make_enrollment(row)

    def get_by_student(self, student_id):
        """Направления выбранного ученика."""
        rows = self.db.connection.execute("""
            SELECT enrollment_id, student_id, subject_id,
                   preparation_goal, price_60_kopecks
            FROM enrollments
            WHERE student_id = ?
            ORDER BY enrollment_id;
        """, [student_id]).fetchall()

        enrollments = []
        for row in rows:
            enrollments.append(self._make_enrollment(row))

        return enrollments

    def update(self, enrollment):
        """Изменение направления обучения."""
        self._check_enrollment(enrollment)

        saved = self.get_by_id(enrollment.enrollment_id)
        if saved is None:
            raise ValueError("Направление с таким ID не найдено.")

        # Сохранение истории занятий
        if (
            saved.student_id != enrollment.student_id
            or saved.subject_id != enrollment.subject_id
        ):
            lesson = self.db.connection.execute("""
                SELECT lesson_id FROM lessons
                WHERE enrollment_id = ? LIMIT 1;
            """, [enrollment.enrollment_id]).fetchone()

            if lesson is not None:
                raise ValueError(
                    "У направления есть занятия. "
                    "Для другого ученика или предмета создай новое направление."
                )

        self.db.connection.execute("""
            UPDATE enrollments
            SET student_id = ?, subject_id = ?, preparation_goal = ?,
                price_60_kopecks = ?
            WHERE enrollment_id = ?;
        """, [
            enrollment.student_id,
            enrollment.subject_id,
            enrollment.preparation_goal,
            enrollment.price_60_kopecks,
            enrollment.enrollment_id
        ])

    def delete(self, enrollment_id):
        """Удаление направления без занятий."""
        lesson = self.db.connection.execute("""
            SELECT lesson_id FROM lessons
            WHERE enrollment_id = ? LIMIT 1;
        """, [enrollment_id]).fetchone()

        if lesson is not None:
            raise ValueError(
                "Нельзя удалить направление, у которого есть занятия."
            )

        cursor = self.db.connection.execute("""
            DELETE FROM enrollments WHERE enrollment_id = ?;
        """, [enrollment_id])

        if cursor.rowcount == 0:
            raise ValueError("Направление с таким ID не найдено.")


# Проверка чтения
if __name__ == "__main__":
    db = DatabaseManager()

    try:
        repository = EnrollmentRepository(db)
        student_id = int(input("ID ученика: "))
        enrollments = repository.get_by_student(student_id)

        print("Количество направлений:", len(enrollments))
        for enrollment in enrollments:
            print("ID:", enrollment.enrollment_id)
            print("ID предмета:", enrollment.subject_id)
            print("Цель подготовки:", enrollment.preparation_goal)
            print(
                "Цена за 60 минут:",
                enrollment.price_60_kopecks,
                "коп."
            )
    finally:
        db.close()