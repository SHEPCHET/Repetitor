"""Запросы для работы с родителями."""

from database import DatabaseManager
from models import Parent


class ParentRepository:
    """Родители и их связи с учениками."""

    def __init__(self, db):
        """Подключение к базе."""
        self.db = db
        self.db.connect()

    def _make_parent(self, row):
        """Получение родителя из строки базы."""
        if row is None:
            return None

        return Parent(
            parent_id=row[0],
            full_name=row[1],
            phone=row[2],
            messenger_type=row[3],
            messenger_contact=row[4]
        )

    def _check_parent(self, parent):
        """Проверка ФИО."""
        parent.full_name = parent.full_name.strip()

        if parent.full_name == "":
            raise ValueError("ФИО родителя не должно быть пустым.")

    def add(self, parent):
        """Добавление родителя."""
        self._check_parent(parent)

        if parent.parent_id is not None:
            raise ValueError("У нового родителя ещё не должно быть ID.")

        cursor = self.db.connection.execute("""
            INSERT INTO parents (
                full_name, phone, messenger_type, messenger_contact
            )
            VALUES (?, ?, ?, ?);
        """, [
            parent.full_name,
            parent.phone,
            parent.messenger_type,
            parent.messenger_contact
        ])

        parent.parent_id = cursor.lastrowid

    def get_by_id(self, parent_id):
        """Поиск родителя по ID."""
        row = self.db.connection.execute("""
            SELECT parent_id, full_name, phone,
                   messenger_type, messenger_contact
            FROM parents
            WHERE parent_id = ?;
        """, [parent_id]).fetchone()

        return self._make_parent(row)

    def get_all(self):
        """Список всех родителей."""
        rows = self.db.connection.execute("""
            SELECT parent_id, full_name, phone,
                   messenger_type, messenger_contact
            FROM parents
            ORDER BY full_name, parent_id;
        """).fetchall()

        parents = []
        for row in rows:
            parents.append(self._make_parent(row))

        return parents

    def update(self, parent):
        """Изменение данных родителя."""
        self._check_parent(parent)

        if parent.parent_id is None:
            raise ValueError("Для изменения родителя нужен его ID.")

        cursor = self.db.connection.execute("""
            UPDATE parents
            SET full_name = ?, phone = ?, messenger_type = ?,
                messenger_contact = ?
            WHERE parent_id = ?;
        """, [
            parent.full_name,
            parent.phone,
            parent.messenger_type,
            parent.messenger_contact,
            parent.parent_id
        ])

        if cursor.rowcount == 0:
            raise ValueError("Родитель с таким ID не найден.")

    def link(self, student_id, parent_id, is_primary=False):
        """Привязка родителя к ученику."""
        if is_primary not in (False, True):
            raise ValueError("Неверный признак основного контакта.")

        student = self.db.connection.execute("""
            SELECT student_id FROM students WHERE student_id = ?;
        """, [student_id]).fetchone()

        if student is None:
            raise ValueError("Ученик не найден.")

        if self.get_by_id(parent_id) is None:
            raise ValueError("Родитель не найден.")

        # Смена основного контакта
        if is_primary:
            self.db.connection.execute("""
                UPDATE student_parents
                SET is_primary = 0
                WHERE student_id = ? AND is_primary = 1;
            """, [student_id])

        self.db.connection.execute("""
            INSERT INTO student_parents (student_id, parent_id, is_primary)
            VALUES (?, ?, ?)
            ON CONFLICT(student_id, parent_id)
            DO UPDATE SET is_primary = excluded.is_primary;
        """, [student_id, parent_id, int(is_primary)])

    def get_by_student(self, student_id):
        """Список родителей выбранного ученика."""
        rows = self.db.connection.execute("""
            SELECT p.parent_id, p.full_name, p.phone,
                   p.messenger_type, p.messenger_contact, sp.is_primary
            FROM parents AS p
            JOIN student_parents AS sp ON p.parent_id = sp.parent_id
            WHERE sp.student_id = ?
            ORDER BY sp.is_primary DESC, p.parent_id;
        """, [student_id]).fetchall()

        parents = []
        for row in rows:
            parent = self._make_parent(row)
            parents.append((parent, bool(row[5])))

        return parents

    def set_primary(self, student_id, parent_id):
        """Выбор основного родителя."""
        link = self.db.connection.execute("""
            SELECT parent_id FROM student_parents
            WHERE student_id = ? AND parent_id = ?;
        """, [student_id, parent_id]).fetchone()

        if link is None:
            raise ValueError("Этот родитель не привязан к ученику.")

        self.link(student_id, parent_id, True)

    def unlink(self, student_id, parent_id):
        """Удаление связи с учеником."""
        self.db.connection.execute("""
            DELETE FROM student_parents
            WHERE student_id = ? AND parent_id = ?;
        """, [student_id, parent_id])

    def delete(self, parent_id):
        """Удаление родителя без связей с учениками."""
        link = self.db.connection.execute("""
            SELECT student_id FROM student_parents
            WHERE parent_id = ? LIMIT 1;
        """, [parent_id]).fetchone()

        if link is not None:
            raise ValueError(
                "Родитель связан с учениками. Сначала убери связь."
            )

        cursor = self.db.connection.execute("""
            DELETE FROM parents WHERE parent_id = ?;
        """, [parent_id])

        if cursor.rowcount == 0:
            raise ValueError("Родитель с таким ID не найден.")


# Проверка чтения
if __name__ == "__main__":
    db = DatabaseManager()

    try:
        repository = ParentRepository(db)
        parents = repository.get_all()

        print("Количество родителей:", len(parents))
        for parent in parents:
            print("ID:", parent.parent_id, "ФИО:", parent.full_name)
    finally:
        db.close()