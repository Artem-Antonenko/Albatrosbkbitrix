"""Генераторы inline-клавиатур VK (inline: true — кнопки внутри пузыря сообщения)."""
import json


def _kb(buttons: list[list[dict]], inline: bool = True) -> str:
    return json.dumps({"inline": inline, "buttons": buttons}, ensure_ascii=False)


def _btn(label: str, color: str = "secondary") -> dict:
    return {"action": {"type": "text", "label": label}, "color": color}


# ──────────────────────────────────────────────
# Главное меню
# ──────────────────────────────────────────────
def main_menu() -> str:
    return _kb([
        [_btn("❓ FAQ"), _btn("🎫 Проверить абонемент", "primary")],
        [_btn("📅 Расписание"), _btn("👨‍🏫 Тренеры")],
        [_btn("📞 Оператор", "negative")],
    ])


# ──────────────────────────────────────────────
# FAQ
# ──────────────────────────────────────────────
def faq_menu() -> str:
    return _kb([
        [_btn("🕐 Режим работы")],
        [_btn("💰 Цены и абонементы")],
        [_btn("❄️ Заморозка абонемента")],
        [_btn("📍 Адреса и контакты")],
        [_btn("🔙 Главное меню", "primary")],
    ])


# ──────────────────────────────────────────────
# Расписание
# ──────────────────────────────────────────────
def schedule_filter_menu() -> str:
    return _kb([
        [_btn("📆 По дню недели"), _btn("🏋️ По направлению")],
        [_btn("🔙 Главное меню", "primary")],
    ])


def days_menu() -> str:
    days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    return _kb([
        [_btn(d) for d in days[:4]],
        [_btn(d) for d in days[4:]],
        [_btn("🔙 Назад"), _btn("🔙 Главное меню", "primary")],
    ])


def directions_menu(directions: list[str]) -> str:
    rows = [[_btn(d)] for d in directions]
    rows.append([_btn("🔙 Назад"), _btn("🔙 Главное меню", "primary")])
    return _kb(rows)


# ──────────────────────────────────────────────
# Тренеры
# ──────────────────────────────────────────────
def trainer_nav(has_prev: bool, has_next: bool) -> str:
    nav_row = []
    if has_prev:
        nav_row.append(_btn("◀️ Предыдущий"))
    if has_next:
        nav_row.append(_btn("▶️ Следующий"))
    rows = [nav_row] if nav_row else []
    rows.append([_btn("🔙 Главное меню", "primary")])
    return _kb(rows)


# ──────────────────────────────────────────────
# Оператор
# ──────────────────────────────────────────────
def operator_stop() -> str:
    return _kb([
        [_btn("❌ Завершить диалог с оператором", "negative")],
    ])


# ──────────────────────────────────────────────
# Универсальная «Назад»
# ──────────────────────────────────────────────
def back_button() -> str:
    return _kb([
        [_btn("🔙 Главное меню", "primary")],
    ])
