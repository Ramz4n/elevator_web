import subprocess
import sys
import time
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_venv_python = os.path.join(BASE_DIR, ".venv", "Scripts", "python.exe")
PYTHON = _venv_python if os.path.exists(_venv_python) else sys.executable
SCRIPT = os.path.join(BASE_DIR, "tester.py")
LOG = os.path.join(BASE_DIR, "app.log")


def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%d.%m.%Y %H:%M:%S')}] {msg}\n")


while True:
    log("Запуск сервера")
    try:
        proc = subprocess.run(
            [PYTHON, SCRIPT],
            cwd=BASE_DIR,
            stdout=open(LOG, "a", encoding="utf-8"),
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        log(f"Сервер остановлен (код: {proc.returncode}). Перезапуск через 5 сек...")
    except Exception as e:
        log(f"Ошибка запуска: {e}. Перезапуск через 5 сек...")
    time.sleep(5)
