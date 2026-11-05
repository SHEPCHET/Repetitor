"""Проверка добавления ученика."""

import sqlite3

from database import DatabaseManager
from models import Student
from student_repository import StudentRepository

db = DatabaseManager()

try:
    repository = StudentRepository(db)

    # Ввод данных
    full_name = input("ФИО ученика: ")
    phone = input("Телефон ученика: ").strip()

    student = Student(full_name, phone=phone)

    # Добавление и чтение
    repository.add(student)
    saved_student = repository.get_by_id(student.student_id)

    # Сохранение изменений
    db.connection.commit()

    print("Ученик сохранён.")
    print("ID:", saved_student.student_id)
    print("ФИО:", saved_student.full_name)
    print("Телефон:", saved_student.phone)

except (sqlite3.Error, ValueError) as error:
    if db.connection is not None:
        db.connection.rollback()

    print("Ошибка:", error)

finally:
    db.close()
