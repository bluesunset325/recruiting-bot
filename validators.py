
from __future__ import annotations

import re
from typing import Optional, Tuple


def normalize_phone(phone: str) -> Optional[str]:
    """-> +7XXXXXXXXXX"""
    if not phone:
        return None

    digits = re.sub(r"\D", "", phone)

    if len(digits) == 11 and digits[0] in ("7", "8"):
        digits = "7" + digits[1:]
    elif len(digits) == 10:
        digits = "7" + digits
    else:
        return None

    if digits[1] != "9":
        return None

    return f"+{digits}"


def validate_phone(text: str) -> Tuple[bool, str]:
    """(is_valid, normalized_or_error)"""
    normalized = normalize_phone(text)
    if normalized:
        return True, normalized
    return False, "Введите корректный российский номер (например +79991234567)"


def validate_email(text: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", text))


def validate_contact(text: str) -> Tuple[bool, str]:
    """телефон или email; (is_valid, value_or_error)"""
    text = text.strip()
    if not text or len(text) < 5:
        return False, "Введите email или телефон для связи"

    phone_ok, phone_result = validate_phone(text)
    if phone_ok:
        return True, phone_result

    if validate_email(text):
        return True, text

    if any(ch.isdigit() for ch in text):
        return False, "Номер телефона не распознан. Формат: +79991234567"

    return False, "Введите корректный email или телефон"


def validate_name(text: str) -> Tuple[bool, str]:
    if not text or len(text.strip()) < 2:
        return False, "Введите имя (минимум 2 символа)"
    return True, text.strip()


def validate_experience(text: str) -> Tuple[bool, float]:
    """Разобрать опыт работы: число, дробь или текст.

    Принимает: «5», «0.5», «1,5», «3 года», «6 месяцев», «1 год 6 месяцев»,
    «полгода», «полтора года», «месяц», «нет опыта».
    Возвращает (is_valid, годы_числом). Месяцы переводятся в доли года.
    """
    t = text.strip().lower().replace(",", ".")
    if not t:
        return False, 0

    # Словесные формы без цифр
    if re.search(r"\b(нет|без)\s*(опыта)?\b", t) and not re.search(r"\d", t):
        return True, 0
    if "полтора" in t:
        return True, 1.5
    if re.search(r"пол\s*года", t):
        return True, 0.5

    years = 0.0
    found = False

    # «3 года», «1 год», «5 лет», «2.5 г»
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:год|года|лет|г\b)", t)
    if m:
        years += float(m.group(1))
        found = True

    # «6 месяцев», «1 месяц», «3 мес»
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:месяц|мес)", t)
    if m:
        years += float(m.group(1)) / 12
        found = True

    # «год» / «месяц» без числа
    if not found:
        if re.search(r"\bгод\b", t):
            years, found = 1.0, True
        elif re.search(r"\bмесяц\b", t):
            years, found = 1 / 12, True

    # Просто число: «5», «0.1», «1.5»
    if not found:
        try:
            years = float(t)
            found = True
        except ValueError:
            return False, 0

    if 0 <= years <= 50:
        return True, round(years, 2)
    return False, 0
