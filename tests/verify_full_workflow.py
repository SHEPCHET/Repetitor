"""Общий сценарий с созданием новой базы."""

import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from database import DatabaseManager
from authenticator import Authenticator
from student_service import StudentService
from enrollment_repository import EnrollmentRepository
from lesson_repository import LessonRepository
from lesson_service import LessonService
from journal_service import JournalService
from payment_service import PaymentService
from billing_service import BillingService
from report_generator import ReportGenerator

with tempfile.TemporaryDirectory() as folder:
    folder = Path(folder)
    shutil.copyfile(PROJECT / "init_db.py", folder / "init_db.py")
    # Первый запуск и повторный запуск не требуют ручного SQL.
    for attempt in range(2):
        result = subprocess.run(
            [sys.executable, "-B", "-X", "utf8", str(folder / "init_db.py")],
            cwd=folder,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert result.returncode == 0, result.stderr
        assert "Количество таблиц: 9" in result.stdout
    db = DatabaseManager()
    db.db_path = folder / "repetitor.db"
    try:
        auth = Authenticator(db)
        auth.register(
            "Тестовый репетитор", "test_tutor", "tutor@example.com", "Password-123"
        )
        assert auth.login("test_tutor", "Password-123")
        students = StudentService(db)
        student_id = students.add(
            dict(
                student=dict(
                    full_name="Тестовый ученик",
                    phone="",
                    messenger_type="Telegram",
                    messenger_contact="test_student",
                    is_archived=False,
                ),
                parents=[
                    dict(
                        full_name="Тестовый родитель",
                        phone="",
                        messenger_type="",
                        messenger_contact="",
                        is_primary=True,
                    )
                ],
                enrollments=[
                    dict(subject_name="Физика", preparation_goal="ОГЭ", price="1400")
                ],
            )
        )
        enrollment = EnrollmentRepository(db).get_by_student(student_id)[0]
        lessons = LessonService(db)
        lessons._now = lambda: datetime(2026, 11, 1, 9)
        lesson = lessons.schedule(
            enrollment.enrollment_id, datetime(2026, 11, 2, 10), 90
        )
        assert lesson.price_kopecks == 210000 and lesson.status == "Запланировано"
        # Предоплата до занятия отражается как переплата.
        payment = PaymentService(db).register_payment(lesson.lesson_id, 210000)
        with db.connection:
            db.connection.execute(
                "UPDATE payments SET paid_at = ? WHERE payment_id = ?",
                ["2026-11-01 12:00:00", payment.payment_id],
            )
        assert BillingService(db).get_summary(student_id)["advance"] == 210000
        try:
            PaymentService(db).register_payment(lesson.lesson_id)
        except (ValueError, sqlite3.IntegrityError):
            pass
        else:
            raise AssertionError("Повторная оплата разрешена")
        lessons.reschedule(
            lesson.lesson_id, datetime(2026, 11, 2, 12), datetime(2026, 11, 2, 13, 30)
        )
        lessons._now = lambda: datetime(2026, 11, 3, 9)
        assert lessons.complete_finished() == 1
        JournalService(db).save_topics(
            {lesson.lesson_id: dict(original=[], topics=["Кинематика", "Задачи"])}
        )
        summary = BillingService(db).get_summary(student_id)
        assert summary == dict(
            charged=210000, received=210000, balance=0, debt=0, advance=0
        )
        # Изменение тарифа не переписывает проведённое занятие.
        card = students.get_card(student_id)
        card["enrollments"][0]["price"] = "1600"
        students.update(student_id, card)
        assert LessonRepository(db).get_by_id(lesson.lesson_id).price_kopecks == 210000
        students.set_archived(student_id, True)
        assert JournalService(db).get_items() == []
        assert len(JournalService(db).get_items(archived=True)) == 1
        generator = ReportGenerator(db)
        data = generator.get_data(student_id, date(2026, 11, 1), date(2026, 11, 30))
        assert data["charged"] == data["received"] == 210000 and data["closing"] == 0
        report = generator.make_text(data)
        generator.save(report, folder / "report.txt")
        assert (folder / "report.txt").read_text(encoding="utf-8") == report
        assert "Кинематика" in report and "2100,00" in report
        backup = db.backup()
        expected = list(db.connection.iterdump())
        auth.logout()
        assert auth.current_user_id is None
        db.close()
        restored = sqlite3.connect(backup)
        try:
            assert list(restored.iterdump()) == expected
            assert restored.execute("PRAGMA integrity_check").fetchone() == ("ok",)
            assert restored.execute("PRAGMA foreign_key_check").fetchall() == []
        finally:
            restored.close()
    finally:
        db.close()

print(
    (
        "PASS: clean initialization twice, registration/login, full student card, "
        "prepayment, duplicate rejection, reschedule, completion, topics, saved "
        "tariff, archive, TXT report, backup/restore and logout"
    )
)
