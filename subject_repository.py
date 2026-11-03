"""Запросы для работы с предметами."""


class SubjectRepository:
    """Справочник предметов."""

    def __init__(self, db):
        """Подключение к базе."""
        self.db = db
        self.db.connect()

    def _check_name(self, name):
        """Проверка названия предмета."""
        name = name.strip()

        if name == "":
            raise ValueError(
                "Название предмета не должно быть пустым."
            )

        return name

    def add(self, name):
        """Добавление предмета и получение ID."""
        name = self._check_name(name)

        cursor = self.db.connection.execute("""
            INSERT INTO subjects (name) VALUES (?);
        """, [name])

        return cursor.lastrowid

    def get_by_id(self, subject_id):
        """Предмет по ID или None."""
        return self.db.connection.execute("""
            SELECT subject_id, name FROM subjects
            WHERE subject_id = ?;
        """, [subject_id]).fetchone()

    def get_all(self):
        """Все предметы: ID и название."""
        return self.db.connection.execute("""
            SELECT subject_id, name FROM subjects
            ORDER BY name, subject_id;
        """).fetchall()

    def update(self, subject_id, name):
        """Изменение названия предмета."""
        name = self._check_name(name)

        cursor = self.db.connection.execute("""
            UPDATE subjects SET name = ?
            WHERE subject_id = ?;
        """, [name, subject_id])

        if cursor.rowcount == 0:
            raise ValueError("Предмет с таким ID не найден.")

    def delete(self, subject_id):
        """Удаление предмета без направлений обучения."""
        enrollment = self.db.connection.execute("""
            SELECT enrollment_id FROM enrollments
            WHERE subject_id = ? LIMIT 1;
        """, [subject_id]).fetchone()

        if enrollment is not None:
            raise ValueError(
                "Предмет используется в направлениях обучения."
            )

        cursor = self.db.connection.execute("""
            DELETE FROM subjects WHERE subject_id = ?;
        """, [subject_id])

        if cursor.rowcount == 0:
            raise ValueError("Предмет с таким ID не найден.")