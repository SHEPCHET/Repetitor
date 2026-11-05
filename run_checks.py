"""Запуск проверок на временных базах."""

import os
import subprocess
import sys
from pathlib import Path

folder = Path(__file__).resolve().parent
failed = []
checks = sorted((folder / "tests").glob("verify_*.py"))
if not checks:
    print("Проверки не найдены.")
    sys.exit(1)

environment = os.environ.copy()
environment["PYTHONUTF8"] = "1"
for check in checks:
    print("Проверка:", check.name, flush=True)
    result = subprocess.run(
        [sys.executable, "-B", "-X", "utf8", str(check)],
        cwd=folder,
        env=environment,
        timeout=90,
    )
    if result.returncode != 0:
        failed.append(check.name)

print("Всего:", len(checks), "Успешно:", len(checks) - len(failed))
if failed:
    print("Ошибки:", ", ".join(failed))
    sys.exit(1)
