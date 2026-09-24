"""Бот и HR-панель одной командой."""

from __future__ import annotations

import subprocess
import sys
import signal
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PYTHON = sys.executable


def start_process(script: str, label: str) -> subprocess.Popen:
    proc = subprocess.Popen(
        [PYTHON, str(BASE_DIR / script)],
        cwd=str(BASE_DIR),
    )
    print(f"[run] {label} запущен (PID {proc.pid})")
    return proc


def stop_all(processes: list[subprocess.Popen]) -> None:
    print("\n[run] Остановка...")
    for proc in processes:
        proc.terminate()
    for proc in processes:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    print("[run] Все процессы остановлены.")


def main() -> None:
    processes: list[subprocess.Popen] = []

    bot_proc = start_process("bot.py", "Telegram-бот")
    processes.append(bot_proc)

    time.sleep(1)

    panel_proc = start_process("hr_panel.py", "HR-панель (http://localhost:5050)")
    processes.append(panel_proc)

    print("\n[run] Всё запущено. Нажмите Ctrl+C для остановки.\n")

    def handle_signal(signum, frame):
        stop_all(processes)
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    while True:
        for proc in processes:
            if proc.poll() is not None:
                print(f"[run] Процесс PID {proc.pid} завершился с кодом {proc.returncode}. Перезапуск...")
                idx = processes.index(proc)
                script = "bot.py" if idx == 0 else "hr_panel.py"
                label = "Telegram-бот" if idx == 0 else "HR-панель"
                processes[idx] = start_process(script, label)
        time.sleep(3)


if __name__ == "__main__":
    main()
