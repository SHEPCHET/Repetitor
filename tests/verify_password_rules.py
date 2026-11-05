"""Новые пароли и совместимость существующих аккаунтов."""

import ast
import sqlite3
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from authenticator import Authenticator
from database import DatabaseManager
from remembered_login import RememberedLogin

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
    db.db_path = Path(folder) / "rules.db"
    con = sqlite3.connect(db.db_path)
    con.executescript(schema)
    con.close()
    try:
        auth = Authenticator(db)
        for password, text in [
            ("", "8 символов"),
            ("Abc1234", "8 символов"),
            ("12345678", "букву"),
            ("abcdefgh", "цифру"),
            ("!!!!!!!!", "букву"),
            ("        ", "букву"),
        ]:
            before = tuple(db.connection.iterdump())
            try:
                auth.register("Проверка", "invalid", "test@example.com", password)
            except ValueError as error:
                assert text in str(error)
            else:
                raise AssertionError("Invalid new password accepted")
            assert tuple(db.connection.iterdump()) == before
        for number, password in enumerate(
            ["Abcdefg1", "Пароль12", " abcde1 ", "Проверочный123!"]
        ):
            login = "valid" + str(number)
            auth.register("Проверка", login, "test@example.com", password)
            assert auth.login(login, password)

        # Старый пароль без букв продолжает подходить для входа.
        digest, salt = auth._make_password("12345678")
        with db.connection:
            cursor = db.connection.execute(
                (
                    "INSERT INTO users(login,name,email,password_hash,password_salt) "
                    "VALUES(?,?,?,?,?)"
                ),
                ["legacy", "Старый аккаунт", "old@example.com", digest, salt],
            )
            user_id = cursor.lastrowid
        assert auth.login("legacy", "12345678")
        saved = RememberedLogin(db)
        saved.remember(user_id)
        assert saved.restore() == user_id
        for password, text in [
            ("letters-only", "цифру"),
            ("123456789", "букву"),
            ("a1", "8 символов"),
        ]:
            before = tuple(db.connection.iterdump())
            try:
                auth.change_password("12345678", password)
            except ValueError as error:
                assert text in str(error)
            else:
                raise AssertionError("Invalid replacement accepted")
            assert (
                tuple(db.connection.iterdump()) == before and saved.restore() == user_id
            )
        assert not auth.change_password("wrong", "NewPass123")
        assert auth.change_password("12345678", "NewPass123")
        assert not auth.login("legacy", "12345678") and auth.login(
            "legacy", "NewPass123"
        )
        assert saved.restore() is None
        saved.remember(user_id)
        assert saved.restore() == user_id
    finally:
        db.close()

print(
    (
        "PASS: minimum length, letters and digits, Cyrillic, spaces preserved, "
        "invalid registration/password-change rollback, legacy login and remembered "
        "account preserved"
    )
)
