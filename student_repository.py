"""Запросы для работы с учениками."""

from database import DatabaseManager
from models import Student


class StudentRepository:
    """Сохранение и получение учеников."""

    def __init__(self, db):
        """Подключение через менеджер базы."""
        self.db = db
        self.db.connect()

    def _make_student(self, row):
        """Преобразование строки базы в ученика."""
        if row is None:
            return None

        return Student(
            student_id=row[0],
            full_name=row[1],
            phone=row[2],
            messenger_type=row[3],
            messenger_contact=row[4],
            is_archived=bool(row[5])
        )

    def _check_student(self, student):
        """Проверка ФИО и признака архива."""
        student.full_name = student.full_name.strip()

        if student.full_name == "":
            raise ValueError("ФИО ученика не должно быть пустым.")

        if student.is_archived not in (False, True):
            raise ValueError("Неверный признак архива.")

    def add(self, student):
        """Добавление ученика и получение его ID."""
        self._check_student(student)

        if student.student_id is not None:
            raise ValueError("У нового ученика ещё не должно быть ID.")

        cursor = self.db.connection.execute("""
            INSERT INTO students (
                full_name, phone, messenger_type,
                messenger_contact, is_archived
            )
            VALUES (?, ?, ?, ?, ?);
        """, [
            student.full_name,
            student.phone,
            student.messenger_type,
            student.messenger_contact,
            int(student.is_archived)
        ])

        student.student_id = cursor.lastrowid

    def get_by_id(self, student_id):
        """Получение ученика по ID или None, если его нет."""
        row = self.db.connection.execute("""
            SELECT student_id, full_name, phone,
                   messenger_type, messenger_contact, is_archived
            FROM students
            WHERE student_id = ?;
        """, [student_id]).fetchone()

        return self._make_student(row)

    def get_all(self, is_archived=False):
        """Список учеников: False — активные, True — архив, None — все."""
        rows = self.db.connection.execute("""
            SELECT student_id, full_name, phone,
                   messenger_type, messenger_contact, is_archived
            FROM students
            WHERE (? IS NULL OR is_archived = ?)
            ORDER BY full_name, student_id;
        """, [is_archived, is_archived]).fetchall()

        students = []
        for row in rows:
            students.append(self._make_student(row))

        return students

    def update(self, student):
        """Изменение данных существующего ученика."""
        self._check_student(student)

        if student.student_id is None:
            raise ValueError("Для изменения ученика нужен его ID.")

        cursor = self.db.connection.execute("""
            UPDATE students
            SET full_name = ?, phone = ?, messenger_type = ?,
                messenger_contact = ?, is_archived = ?
            WHERE student_id = ?;
        """, [
            student.full_name,
            student.phone,
            student.messenger_type,
            student.messenger_contact,
            int(student.is_archived),
            student.student_id
        ])

        if cursor.rowcount == 0:
            raise ValueError("Ученик с таким ID не найден.")

    def search(self, query, is_archived=False):
        """Поиск по ФИО или точному ID с выбранным состоянием архива."""
        query = query.strip()
        students = self.get_all(is_archived)
        found = []

        if query.isdecimal():
            student_id = int(query)

            for student in students:
                if student.student_id == student_id:
                    found.append(student)
        else:
            query = query.casefold()

            for student in students:
                if query in student.full_name.casefold():
                    found.append(student)

        return found


# Проверка чтения
if __name__ == "__main__":
    db = DatabaseManager()

    try:
        repository = StudentRepository(db)
        students = repository.get_all(None)

        print("Количество учеников:", len(students))
        for student in students:
            print("ID:", student.student_id, "ФИО:", student.full_name)
    finally:
        db.close()