"""Сохранение полной карточки ученика."""

from models import Student, Parent, Enrollment
from student_repository import StudentRepository
from parent_repository import ParentRepository
from enrollment_repository import EnrollmentRepository
from subject_repository import SubjectRepository


class StudentService:
    """Ученик, родители и направления обучения."""

    def __init__(self, db):
        """Подготовка данных и элементов объекта."""
        self.db = db
        self.students = StudentRepository(db)
        self.parents = ParentRepository(db)
        self.enrollments = EnrollmentRepository(db)
        self.subjects = SubjectRepository(db)

    def _price(self, text):
        """Перевод рублей в копейки."""
        parts = text.strip().replace(" ", "").replace(",", ".").split(".")
        if len(parts) > 2 or not parts[0].isdecimal():
            raise ValueError("Укажи цену от 0 рублей, например 1400 или 1400,50.")
        kopecks = 0
        if len(parts) == 2:
            if not parts[1].isdecimal() or len(parts[1]) > 2:
                raise ValueError("После запятой в цене должно быть 1–2 цифры.")
            kopecks = int(parts[1].ljust(2, "0"))
        return int(parts[0]) * 100 + kopecks

    def _contact(self, data):
        """Данные ученика или родителя."""
        values = []
        for key in ("full_name", "phone", "messenger_type", "messenger_contact"):
            values.append(data[key].strip())
        return values

    def get_card(self, student_id):
        """Данные для формы изменения."""
        student = self.students.get_by_id(student_id)
        if student is None:
            raise ValueError("Ученик не найден.")

        def contact(person):
            """Данные контакта для заполнения формы."""
            return {
                "full_name": person.full_name,
                "phone": person.phone or "",
                "messenger_type": person.messenger_type or "",
                "messenger_contact": person.messenger_contact or "",
            }

        data = {
            "student_id": student.student_id,
            "student": contact(student),
            "parents": [],
            "enrollments": [],
        }
        data["student"]["is_archived"] = student.is_archived
        for parent, is_primary in self.parents.get_by_student(student_id):
            row = contact(parent)
            row["parent_id"] = parent.parent_id
            row["is_primary"] = is_primary
            data["parents"].append(row)
        for enrollment in self.enrollments.get_by_student(student_id):
            subject = self.subjects.get_by_id(enrollment.subject_id)
            price = enrollment.price_60_kopecks
            data["enrollments"].append(
                {
                    "enrollment_id": enrollment.enrollment_id,
                    "subject_name": subject[1],
                    "preparation_goal": enrollment.preparation_goal,
                    "price": str(price // 100) + "," + str(price % 100).zfill(2),
                }
            )
        return data

    def add(self, data):
        """Добавление карточки."""
        return self._save(data)

    def update(self, student_id, data):
        """Изменение существующей карточки."""
        if (
            not isinstance(student_id, int)
            or isinstance(student_id, bool)
            or student_id <= 0
        ):
            raise ValueError("Неверный ID ученика.")
        return self._save(data, student_id)

    def set_archived(self, student_id, archived):
        """Перемещение в архив или восстановление."""
        if (
            not isinstance(student_id, int)
            or isinstance(student_id, bool)
            or student_id <= 0
        ):
            raise ValueError("Неверный ID ученика.")
        if not isinstance(archived, bool):
            raise ValueError("Неверный признак архива.")
        if self.db.connection.in_transaction:
            raise ValueError("Сначала заверши предыдущую операцию с базой.")

        self.db.connection.execute("BEGIN IMMEDIATE;")
        with self.db.connection:
            student = self.students.get_by_id(student_id)
            if student is None:
                raise ValueError("Ученик не найден.")
            if archived:
                student.archive()
            else:
                student.restore()
            self.students.update(student)

    def _save(self, data, student_id=None):
        """Общая проверка и запись карточки."""
        values = self._contact(data["student"])
        student = Student(
            values[0],
            student_id=student_id,
            phone=values[1],
            messenger_type=values[2],
            messenger_contact=values[3],
            is_archived=data["student"]["is_archived"],
        )

        parents = []
        primary_count = 0
        for row in data["parents"]:
            values = self._contact(row)
            if not any(values):
                continue
            parent = Parent(
                values[0],
                parent_id=row.get("parent_id"),
                phone=values[1],
                messenger_type=values[2],
                messenger_contact=values[3],
            )
            primary_count += int(row["is_primary"])
            parents.append((parent, row["is_primary"]))
        if primary_count > 1:
            raise ValueError("Основным контактом может быть только один родитель.")

        directions = []
        for row in data["enrollments"]:
            name = " ".join(row["subject_name"].split())
            goal = row["preparation_goal"].strip()
            price = row["price"].strip()
            if name == "" and goal == "" and price == "":
                continue
            if name == "":
                raise ValueError("Введи название предмета в заполненном направлении.")
            enrollment = Enrollment(
                student_id,
                None,
                goal,
                self._price(price),
                enrollment_id=row.get("enrollment_id"),
            )
            directions.append((name, enrollment))

        if self.db.connection.in_transaction:
            raise ValueError("Сначала заверши предыдущую операцию с базой.")

        self.db.connection.execute("BEGIN IMMEDIATE;")
        with self.db.connection:
            if student_id is None:
                self.students.add(student)
            else:
                self._check_saved_rows(student_id, parents, directions)
                self.students.update(student)
                # Связи родителей восстанавливаются с выбранным основным контактом
                for old_parent, primary in self.parents.get_by_student(student_id):
                    self.parents.unlink(student_id, old_parent.parent_id)
                kept = [enrollment.enrollment_id for name, enrollment in directions]
                for old in self.enrollments.get_by_student(student_id):
                    if old.enrollment_id not in kept:
                        self.enrollments.delete(old.enrollment_id)
            for parent, is_primary in parents:
                if parent.parent_id is None:
                    self.parents.add(parent)
                elif student_id is not None:
                    self.parents.update(parent)
                else:
                    raise ValueError("У нового родителя ещё не должно быть ID.")
                self.parents.link(student.student_id, parent.parent_id, is_primary)
            subjects = self.subjects.get_all()
            for name, enrollment in directions:
                subject_id = None
                for subject in subjects:
                    saved_name = " ".join(subject[1].split())
                    if saved_name.casefold() == name.casefold():
                        subject_id = subject[0]
                        break
                if subject_id is None:
                    subject_id = self.subjects.add(name)
                    subjects.append((subject_id, name))
                enrollment.subject_id = subject_id
                enrollment.student_id = student.student_id
                if enrollment.enrollment_id is None:
                    self.enrollments.add(enrollment)
                elif student_id is not None:
                    self.enrollments.update(enrollment)
                else:
                    raise ValueError("У нового направления ещё не должно быть ID.")

        return student.student_id

    def _check_saved_rows(self, student_id, parents, directions):
        """Проверка принадлежности записей ученику."""
        if self.students.get_by_id(student_id) is None:
            raise ValueError("Ученик не найден.")
        saved_parents = [
            parent.parent_id
            for parent, primary in self.parents.get_by_student(student_id)
        ]
        saved_directions = [
            row.enrollment_id for row in self.enrollments.get_by_student(student_id)
        ]
        used = []
        for parent, primary in parents:
            if parent.parent_id is not None:
                if parent.parent_id not in saved_parents or parent.parent_id in used:
                    raise ValueError("Неверная запись родителя в карточке.")
                used.append(parent.parent_id)
        used = []
        for name, enrollment in directions:
            if enrollment.enrollment_id is not None:
                if (
                    enrollment.enrollment_id not in saved_directions
                    or enrollment.enrollment_id in used
                ):
                    raise ValueError("Неверное направление в карточке ученика.")
                used.append(enrollment.enrollment_id)
