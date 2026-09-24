"""Наполнение БД демо-кандидатами для показа HR-панели клиентам.

Запуск: python3 seed_demo.py
Повторный запуск обновляет тех же кандидатов (без дублей).
"""

from __future__ import annotations

import json
import logging
import random
import sqlite3
from datetime import datetime, timedelta

from config import DB_PATH
from database import get_connection, init_db

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

DEMO_CANDIDATES = [
    {
        "telegram_id": 100001, "telegram_username": "demo_a_petrov",
        "full_name": "Александр Петров", "email_or_phone": "+79000000001",
        "experience_years": 5, "position": "backend",
        "specialty_answers": {"languages": "Python, Go", "databases": "PostgreSQL, Redis", "arch": "Kafka, gRPC — 3 года"},
        "status": "Ищу работу", "start_date": "Готов приступить немедленно",
        "hr_status": "на рассмотрении", "days_ago": 1,
    },
    {
        "telegram_id": 100002, "telegram_username": "demo_maria_dev",
        "full_name": "Мария Соколова", "email_or_phone": "m.sokolova@example.com",
        "experience_years": 3, "position": "frontend",
        "specialty_answers": {"frameworks": "React, Next.js", "typescript": "Уверенный уровень, 3 года в продакшене", "tools_fe": "Vite, Figma, Storybook"},
        "status": "Работаю", "start_date": "Через две недели",
        "hr_status": "приглашён", "days_ago": 2,
    },
    {
        "telegram_id": 100003, "telegram_username": "demo_d_volkov",
        "full_name": "Дмитрий Волков", "email_or_phone": "+79000000002",
        "experience_years": 7, "position": "devops",
        "specialty_answers": {"tools": "Docker, Kubernetes, Terraform, Ansible", "clouds": "AWS, Yandex Cloud", "ci_cd": "GitLab CI, ArgoCD"},
        "status": "Работаю", "start_date": "Через месяц",
        "hr_status": "приглашён", "days_ago": 3,
    },
    {
        "telegram_id": 100004, "telegram_username": "demo_elena_k",
        "full_name": "Елена Кузнецова", "email_or_phone": "elena.kuz@example.com",
        "experience_years": 1, "position": "frontend",
        "specialty_answers": {"frameworks": "Vue 3", "typescript": "Базовый уровень", "tools_fe": "Vite, Figma"},
        "status": "Ищу работу", "start_date": "Готов приступить немедленно",
        "hr_status": "отказано", "days_ago": 5,
    },
    {
        "telegram_id": 100005, "telegram_username": "demo_ivan_backend",
        "full_name": "Иван Морозов", "email_or_phone": "+79000000003",
        "experience_years": 4, "position": "backend",
        "specialty_answers": {"languages": "Python, Java", "databases": "PostgreSQL, MongoDB", "arch": "RabbitMQ, микросервисы"},
        "status": "Фрилансер", "start_date": "В течение одной рабочей недели",
        "hr_status": "принят", "days_ago": 8,
    },
    {
        "telegram_id": 100006, "telegram_username": "demo_olga_devops",
        "full_name": "Ольга Новикова", "email_or_phone": "o.novikova@example.com",
        "experience_years": 6, "position": "devops",
        "specialty_answers": {"tools": "Docker, K8s, Helm", "clouds": "GCP, Selectel", "ci_cd": "GitHub Actions, Jenkins"},
        "status": "Работаю", "start_date": "Готов обсудить сроки с менеджером",
        "hr_status": "на рассмотрении", "days_ago": 0,
    },
    {
        "telegram_id": 100007, "telegram_username": "demo_sergey_js",
        "full_name": "Сергей Лебедев", "email_or_phone": "+79000000004",
        "experience_years": 2, "position": "frontend",
        "specialty_answers": {"frameworks": "React", "typescript": "Средний уровень, 1 год", "tools_fe": "Webpack, Figma"},
        "status": "Ищу работу", "start_date": "В течение 1–2 рабочих дней",
        "hr_status": "на рассмотрении", "days_ago": 0,
    },
    {
        "telegram_id": 100008, "telegram_username": "",
        "full_name": "Андрей Козлов", "email_or_phone": "a.kozlov@example.com",
        "experience_years": 10, "position": "backend",
        "specialty_answers": {"languages": "Go, Rust, Python", "databases": "PostgreSQL, ClickHouse", "arch": "Kafka, NATS, 5 лет микросервисов"},
        "status": "Работаю", "start_date": "Через месяц",
        "hr_status": "на рассмотрении", "days_ago": 4,
    },
]


def seed() -> None:
    init_db()
    conn = get_connection()
    try:
        for c in DEMO_CANDIDATES:
            created_at = (datetime.now() - timedelta(days=c["days_ago"], hours=random.randint(0, 8))).strftime("%Y-%m-%d %H:%M:%S")
            answers = c["specialty_answers"]
            conn.execute(
                """
                INSERT INTO candidates
                    (telegram_id, telegram_username, full_name, email_or_phone,
                     experience_years, programming_languages, specialty_answers,
                     status, start_date, position, hr_status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    full_name = excluded.full_name,
                    hr_status = excluded.hr_status,
                    created_at = excluded.created_at
                """,
                (
                    c["telegram_id"], c["telegram_username"], c["full_name"],
                    c["email_or_phone"], c["experience_years"],
                    ", ".join(answers.values()),
                    json.dumps(answers, ensure_ascii=False),
                    c["status"], c["start_date"], c["position"],
                    c["hr_status"], created_at,
                ),
            )
        conn.commit()
        logger.info("✅ Загружено %d демо-кандидатов в %s", len(DEMO_CANDIDATES), DB_PATH)
        logger.info("Откройте HR-панель: http://localhost:5050 (пароль: admin)")
    except sqlite3.Error:
        logger.exception("Ошибка при загрузке демо-данных")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
