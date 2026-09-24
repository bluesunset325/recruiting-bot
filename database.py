
from __future__ import annotations

import json
import logging
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import DB_PATH, DEFAULT_VACANCIES

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                telegram_username TEXT,
                full_name TEXT,
                email_or_phone TEXT,
                experience_years INTEGER,
                programming_languages TEXT,
                specialty_answers TEXT,
                status TEXT,
                start_date TEXT,
                position TEXT DEFAULT 'backend',
                hr_status TEXT DEFAULT 'на рассмотрении',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source TEXT DEFAULT 'telegram'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vacancies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                emoji TEXT DEFAULT '💼',
                description TEXT DEFAULT '',
                questions TEXT DEFAULT '[]',
                scoring_criteria TEXT DEFAULT '',
                active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        _migrate(conn)
        _seed_vacancies(conn)
        conn.commit()
        logger.info("База данных инициализирована: %s", DB_PATH)
    except sqlite3.Error:
        logger.exception("Ошибка при инициализации БД")
        raise
    finally:
        conn.close()


def _seed_vacancies(conn: sqlite3.Connection) -> None:
    count = conn.execute("SELECT COUNT(*) FROM vacancies").fetchone()[0]
    if count:
        return
    for v in DEFAULT_VACANCIES:
        conn.execute(
            """
            INSERT INTO vacancies (slug, title, emoji, description, questions, scoring_criteria)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                v["slug"], v["title"], v["emoji"], v["description"],
                json.dumps(v["questions"], ensure_ascii=False),
                v["scoring_criteria"],
            ),
        )
    logger.info("Загружены дефолтные вакансии: %d", len(DEFAULT_VACANCIES))


def _migrate(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(candidates)")}
    migrations = {
        "specialty_answers": "TEXT",
        "hr_status": "TEXT DEFAULT 'на рассмотрении'",
        "ai_score": "INTEGER",
        "ai_summary": "TEXT",
    }
    for col, col_type in migrations.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE candidates ADD COLUMN {col} {col_type}")
            logger.info("Миграция: добавлена колонка %s", col)


def save_candidate(data: dict) -> int:
    """обновляет, если telegram_id уже есть; возвращает id"""
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO candidates
                (telegram_id, telegram_username, full_name, email_or_phone,
                 experience_years, programming_languages, specialty_answers,
                 status, start_date, position)
            VALUES
                (:telegram_id, :telegram_username, :full_name, :email_or_phone,
                 :experience_years, :programming_languages, :specialty_answers,
                 :status, :start_date, :position)
            ON CONFLICT(telegram_id) DO UPDATE SET
                full_name = excluded.full_name,
                email_or_phone = excluded.email_or_phone,
                experience_years = excluded.experience_years,
                programming_languages = excluded.programming_languages,
                specialty_answers = excluded.specialty_answers,
                status = excluded.status,
                start_date = excluded.start_date,
                position = excluded.position,
                telegram_username = excluded.telegram_username,
                hr_status = 'на рассмотрении',
                ai_score = NULL,
                ai_summary = NULL,
                created_at = CURRENT_TIMESTAMP
            """,
            data,
        )
        conn.commit()
        cursor = conn.execute(
            "SELECT id FROM candidates WHERE telegram_id = :telegram_id",
            {"telegram_id": data["telegram_id"]},
        )
        row = cursor.fetchone()
        logger.info("Кандидат сохранён: telegram_id=%s", data["telegram_id"])
        return row["id"]
    except sqlite3.Error:
        logger.exception("Ошибка при сохранении кандидата")
        raise
    finally:
        conn.close()


def get_all_candidates(
    sort_by: str = "created_at",
    sort_order: str = "DESC",
    status_filter: Optional[str] = None,
    hr_status_filter: Optional[str] = None,
    position_filter: Optional[str] = None,
    min_experience: Optional[int] = None,
    lang_filter: Optional[str] = None,
    search_name: Optional[str] = None,
) -> list[dict]:
    allowed_columns = {
        "created_at", "full_name", "experience_years", "status", "hr_status",
        "ai_score",
    }
    if sort_by not in allowed_columns:
        sort_by = "created_at"
    if sort_order.upper() not in ("ASC", "DESC"):
        sort_order = "DESC"

    query = "SELECT * FROM candidates WHERE 1=1"
    params: list = []

    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)

    if hr_status_filter:
        query += " AND hr_status = ?"
        params.append(hr_status_filter)

    if position_filter:
        query += " AND position = ?"
        params.append(position_filter)

    if min_experience is not None:
        query += " AND experience_years >= ?"
        params.append(min_experience)

    if lang_filter:
        query += " AND LOWER(programming_languages) LIKE ?"
        params.append(f"%{lang_filter.lower()}%")

    if search_name:
        term = f"%{search_name.lower()}%"
        query += (
            " AND (LOWER(full_name) LIKE ? "
            "OR LOWER(programming_languages) LIKE ? "
            "OR LOWER(COALESCE(specialty_answers,'')) LIKE ?)"
        )
        params.extend([term, term, term])

    query += f" ORDER BY {sort_by} {sort_order}"

    conn = get_connection()
    try:
        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error:
        logger.exception("Ошибка при получении кандидатов")
        return []
    finally:
        conn.close()


def get_candidate_by_id(candidate_id: int) -> Optional[dict]:
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT * FROM candidates WHERE id = ?", (candidate_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    except sqlite3.Error:
        logger.exception("Ошибка при получении кандидата id=%s", candidate_id)
        return None
    finally:
        conn.close()


def get_candidate_by_telegram_id(telegram_id: int) -> Optional[dict]:
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT * FROM candidates WHERE telegram_id = ?", (telegram_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    except sqlite3.Error:
        logger.exception("Ошибка при поиске кандидата tg_id=%s", telegram_id)
        return None
    finally:
        conn.close()


def update_ai_score(candidate_id: int, score: int, summary: str) -> bool:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE candidates SET ai_score = ?, ai_summary = ? WHERE id = ?",
            (score, summary, candidate_id),
        )
        conn.commit()
        logger.info("AI-оценка сохранена: id=%s, score=%s", candidate_id, score)
        return True
    except sqlite3.Error:
        logger.exception("Ошибка сохранения AI-оценки id=%s", candidate_id)
        return False
    finally:
        conn.close()


def update_hr_status(candidate_id: int, hr_status: str) -> bool:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE candidates SET hr_status = ? WHERE id = ?",
            (hr_status, candidate_id),
        )
        conn.commit()
        logger.info("HR-статус обновлён: id=%s → %s", candidate_id, hr_status)
        return True
    except sqlite3.Error:
        logger.exception("Ошибка обновления hr_status id=%s", candidate_id)
        return False
    finally:
        conn.close()


def _row_to_vacancy(row: sqlite3.Row) -> dict:
    v = dict(row)
    try:
        v["questions"] = json.loads(v.get("questions") or "[]")
    except json.JSONDecodeError:
        v["questions"] = []
    return v


def get_vacancies(active_only: bool = False) -> list[dict]:
    query = "SELECT * FROM vacancies"
    if active_only:
        query += " WHERE active = 1"
    query += " ORDER BY id"
    conn = get_connection()
    try:
        return [_row_to_vacancy(r) for r in conn.execute(query).fetchall()]
    except sqlite3.Error:
        logger.exception("Ошибка получения вакансий")
        return []
    finally:
        conn.close()


def get_vacancy_by_slug(slug: str) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM vacancies WHERE slug = ?", (slug,)
        ).fetchone()
        return _row_to_vacancy(row) if row else None
    except sqlite3.Error:
        logger.exception("Ошибка поиска вакансии slug=%s", slug)
        return None
    finally:
        conn.close()


def get_vacancy_by_id(vacancy_id: int) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM vacancies WHERE id = ?", (vacancy_id,)
        ).fetchone()
        return _row_to_vacancy(row) if row else None
    except sqlite3.Error:
        logger.exception("Ошибка поиска вакансии id=%s", vacancy_id)
        return None
    finally:
        conn.close()


def save_vacancy(data: dict, vacancy_id: Optional[int] = None) -> bool:
    """data: slug, title, emoji, description, questions, scoring_criteria"""
    questions_json = json.dumps(data.get("questions", []), ensure_ascii=False)
    conn = get_connection()
    try:
        if vacancy_id:
            conn.execute(
                """
                UPDATE vacancies
                SET slug = ?, title = ?, emoji = ?, description = ?,
                    questions = ?, scoring_criteria = ?
                WHERE id = ?
                """,
                (
                    data["slug"], data["title"], data.get("emoji", "💼"),
                    data.get("description", ""), questions_json,
                    data.get("scoring_criteria", ""), vacancy_id,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO vacancies (slug, title, emoji, description, questions, scoring_criteria)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    data["slug"], data["title"], data.get("emoji", "💼"),
                    data.get("description", ""), questions_json,
                    data.get("scoring_criteria", ""),
                ),
            )
        conn.commit()
        logger.info("Вакансия сохранена: %s", data["title"])
        return True
    except sqlite3.Error:
        logger.exception("Ошибка сохранения вакансии %s", data.get("title"))
        return False
    finally:
        conn.close()


def toggle_vacancy(vacancy_id: int) -> bool:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE vacancies SET active = 1 - active WHERE id = ?",
            (vacancy_id,),
        )
        conn.commit()
        return True
    except sqlite3.Error:
        logger.exception("Ошибка переключения вакансии id=%s", vacancy_id)
        return False
    finally:
        conn.close()


def backup_db(backup_dir: Optional[Path] = None) -> Path:
    """возвращает путь к бэкапу"""
    backup_dir = backup_dir or DB_PATH.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"candidates_backup_{timestamp}.db"

    shutil.copy2(str(DB_PATH), str(backup_path))
    logger.info("Бэкап создан: %s", backup_path)
    return backup_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
    print(f"БД создана: {DB_PATH}")
