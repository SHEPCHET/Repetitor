"""Пакетное чтение тем через границу блока без изменения данных."""

import ast
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from database import DatabaseManager
from lesson_repository import LessonRepository
from student_service import StudentService

tree = ast.parse((PROJECT / "init_db.py").read_text(encoding="utf-8-sig"))
schema = next(
    ast.literal_eval(node.args[0])
    for node in ast.walk(tree)
    if isinstance(node, ast.Call)
    and isinstance(node.func, ast.Attribute)
    and node.func.attr == "executescript"
)

with tempfile.TemporaryDirectory() as folder:
    db = DatabaseManager()
    db.db_path = Path(folder) / "batch.db"
    con = sqlite3.connect(db.db_path)
    con.executescript(schema)
    con.close()
    try:
        StudentService(db).add(
            {
                "student": dict(
                    full_name="Тестовый ученик",
                    phone="",
                    messenger_type="",
                    messenger_contact="",
                    is_archived=False,
                ),
                "parents": [],
                "enrollments": [
                    dict(subject_name="Физика", preparation_goal="ОГЭ", price="1400")
                ],
            }
        )
        with db.connection:
            for lesson_id in range(1, 502):
                start = datetime(2024, 1, 1) + timedelta(hours=lesson_id)
                end = start + timedelta(hours=1)
                db.connection.execute(
                    "INSERT INTO lessons VALUES (?,?,?,?,?,?)",
                    [
                        lesson_id,
                        1,
                        start.strftime("%Y-%m-%d %H:%M:%S"),
                        end.strftime("%Y-%m-%d %H:%M:%S"),
                        140000,
                        "Проведено",
                    ],
                )
                if lesson_id != 250:
                    db.connection.executemany(
                        "INSERT INTO lesson_topics(lesson_id, topic_name) VALUES (?,?)",
                        [(lesson_id, "Первая тема"), (lesson_id, "Вторая тема")],
                    )
        before = tuple(db.connection.iterdump())
        queries = []
        db.connection.set_trace_callback(queries.append)
        lessons = LessonRepository(db).get_by_student(1)
        db.connection.set_trace_callback(None)
        assert len(lessons) == 501
        assert lessons[0].topics == lessons[-1].topics == ["Первая тема", "Вторая тема"]
        assert lessons[249].topics == []
        selects = [
            query for query in queries if query.lstrip().upper().startswith("SELECT")
        ]
        assert len(selects) == 3
        assert LessonRepository(db).get_by_student(999) == []
        assert LessonRepository(db).get_by_id(501).topics == lessons[-1].topics
        assert LessonRepository(db).get_by_id(999) is None
        assert tuple(db.connection.iterdump()) == before
    finally:
        db.close()

print(
    (
        "PASS: 501 lessons in two topic batches, topic order and empty topics, three "
        "SELECTs, missing IDs and no writes"
    )
)
