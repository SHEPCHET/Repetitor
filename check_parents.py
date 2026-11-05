"""Проверка добавления родителя."""

import sqlite3

from database import DatabaseManager
from models import Parent
from parent_repository import ParentRepository
from student_repository import StudentRepository

db = DatabaseManager()

try:
    parent_repository = ParentRepository(db)
    student_repository = StudentRepository(db)

    # Выбор ученика
    student_id = int(input("ID ученика: "))
    student = student_repository.get_by_id(student_id)

    if student is None:
        raise ValueError("Ученик с таким ID не найден.")

    print("Ученик:", student.full_name)

    # Данные родителя
    full_name = input("ФИО родителя: ")
    phone = input("Телефон родителя: ").strip()

    parent = Parent(full_name, phone=phone)

    # Добавление и привязка
    parent_repository.add(parent)
    parent_repository.link(student_id, parent.parent_id, True)

    parents = parent_repository.get_by_student(student_id)
    db.connection.commit()

    print("Родитель сохранён и привязан к ученику.")

    for saved_parent, is_primary in parents:
        print("ID:", saved_parent.parent_id)
        print("ФИО:", saved_parent.full_name)
        print("Телефон:", saved_parent.phone)
        print("Основной контакт:", is_primary)

except (sqlite3.Error, ValueError) as error:
    if db.connection is not None:
        db.connection.rollback()

    print("Ошибка:", error)

finally:
    db.close()
