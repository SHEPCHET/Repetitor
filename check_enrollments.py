"""Проверка добавления направления обучения."""

import sqlite3

from database import DatabaseManager
from models import Enrollment
from enrollment_repository import EnrollmentRepository
from student_repository import StudentRepository


db = DatabaseManager()

try:
    repository = EnrollmentRepository(db)
    student_repository = StudentRepository(db)

    # Выбор ученика
    student_id = int(input("ID ученика: "))
    student = student_repository.get_by_id(student_id)

    if student is None:
        raise ValueError("Ученик с таким ID не найден.")

    print("Ученик:", student.full_name)

    # Список предметов
    subjects = db.connection.execute("""
        SELECT subject_id, name
        FROM subjects
        ORDER BY subject_id;
    """).fetchall()

    for subject in subjects:
        print("ID:", subject[0], "Предмет:", subject[1])

    # Данные направления
    subject_id = int(input("ID предмета: "))
    goal = input("Цель подготовки: ")
    price_rubles = int(input("Цена за 60 минут в целых рублях: "))

    enrollment = Enrollment(
        student_id=student_id,
        subject_id=subject_id,
        preparation_goal=goal,
        price_60_kopecks=price_rubles * 100
    )

    # Добавление и чтение
    repository.add(enrollment)
    saved = repository.get_by_id(enrollment.enrollment_id)
    db.connection.commit()

    print("Направление сохранено.")
    print("ID направления:", saved.enrollment_id)
    print("ID ученика:", saved.student_id)
    print("ID предмета:", saved.subject_id)
    print("Цель подготовки:", saved.preparation_goal)
    print("Цена за 60 минут:", saved.price_60_kopecks, "коп.")

except (sqlite3.Error, ValueError) as error:
    if db.connection is not None:
        db.connection.rollback()

    print("Ошибка:", error)

finally:
    db.close()