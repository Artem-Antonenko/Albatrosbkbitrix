"""Обработчики событий VK Long Poll — сердце бота.

В отличие от предыдущей версии, бот не знает источника данных:
он работает через объект DataProvider, переданный из main.py.
Это позволяет переключаться между локальным режимом (SQLite + JSON)
и режимом интеграции с CRM (Битрикс24) одной строкой в .env,
не трогая бизнес-логику.
"""
import os
import random
from datetime import date

from vk_api.bot_longpoll import VkBotEvent, VkBotEventType

import states
import keyboards
from providers import DataProvider

# ──────────────────────────────────────────────
# Глобальная ссылка на провайдер.
# Заполняется один раз из main.py через init(provider).
# Так бот.py остаётся подключаемым модулем, а не классом —
# это сохраняет совместимость со всем остальным кодом.
# ──────────────────────────────────────────────
_provider: DataProvider | None = None


def init(provider: DataProvider) -> None:
    """Передать боту источник данных. Вызывается один раз при старте."""
    global _provider
    _provider = provider


def _data() -> DataProvider:
    if _provider is None:
        raise RuntimeError("bot.init(provider) должен быть вызван до handle_event")
    return _provider


OPERATOR_CHAT_ID: int = int(os.getenv("OPERATOR_CHAT_ID", "0"))

# ──────────────────────────────────────────────
# FAQ — тексты по темам (остаются в коде, к источнику не относятся)
# ──────────────────────────────────────────────
FAQ_TEXTS: dict[str, str] = {
    "🕐 Режим работы": (
        "🕐 Режим работы клуба «Альбатрос»\n\n"
        "Пн–Пт:       07:00 – 23:00\n"
        "Суббота:     08:00 – 22:00\n"
        "Воскресенье: 09:00 – 21:00\n"
        "Праздники:   10:00 – 20:00"
    ),
    "💰 Цены и абонементы": (
        "💰 Цены и абонементы\n\n"
        "🔹 Разовое посещение   — 500 ₽\n"
        "🔹 8 занятий           — 3 200 ₽\n"
        "🔹 12 занятий          — 4 500 ₽\n"
        "🔹 24 занятия          — 8 000 ₽\n"
        "🔹 Безлимит на месяц   — 6 000 ₽\n\n"
        "Студентам и пенсионерам — скидка 10%."
    ),
    "❄️ Заморозка абонемента": (
        "❄️ Заморозка абонемента\n\n"
        "Доступна один раз за срок действия абонемента.\n"
        "Срок заморозки: от 7 до 30 дней.\n"
        "Минимальный остаток — 1 занятие.\n\n"
        "Для заморозки обратитесь на ресепшн или напишите оператору — поможем!"
    ),
    "📍 Адреса и контакты": (
        "📍 Адреса и контакты\n\n"
        "🏢 Главный зал:\n"
        "   ул. Морская, 14, ТЦ «Лазурный», 3 этаж\n\n"
        "🏢 Второй зал:\n"
        "   пр. Победы, 88, БЦ «Горизонт», 1 этаж\n\n"
        "📞 Телефон:  +7 (800) 123-45-67\n"
        "📧 Email:    info@albatros-fit.ru\n"
        "🌐 Сайт:     albatros-fit.ru"
    ),
}

# Сокращения дней для сопоставления кнопок и данных
_DAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


# ──────────────────────────────────────────────
# Утилиты
# ──────────────────────────────────────────────
def _send(vk, peer_id: int, message: str, keyboard: str | None = None) -> None:
    params: dict = {
        "peer_id":   peer_id,
        "message":   message,
        "random_id": random.getrandbits(31),
    }
    if keyboard:
        params["keyboard"] = keyboard
    vk.messages.send(**params)


def _send_to_operator(vk, user_id: int, text: str, user_name: str = "Клиент") -> None:
    prefix = f"💬 [{user_name} | ID {user_id}]:\n"
    _send(vk, OPERATOR_CHAT_ID, prefix + text)


def _get_directions() -> list[str]:
    """Список уникальных направлений из расписания, отсортированный."""
    return sorted({item["direction"] for item in _data().list_schedule() if item.get("direction")})


def _format_schedule(items: list[dict]) -> str:
    if not items:
        return "На выбранный фильтр занятий не найдено."
    lines = [
        f"⏰ {item['time']} — {item['direction']}\n"
        f"   👤 {item['trainer']} | 🏛 {item['hall']}"
        for item in items
    ]
    return "\n\n".join(lines)


def _format_trainer(trainer: dict, index: int, total: int) -> str:
    return (
        f"[{index + 1}/{total}] 👤 {trainer['name']}\n"
        f"🏅 {trainer['specialization']}\n\n"
        f"{trainer['description']}"
    )


def _go_main_menu(vk, user_id: int) -> None:
    states.set_state(user_id, states.MAIN_MENU)
    _send(vk, user_id,
          "Вы в главном меню. Выберите раздел:",
          keyboard=keyboards.main_menu())


# ──────────────────────────────────────────────
# Главный обработчик
# ──────────────────────────────────────────────
def handle_event(vk, event: VkBotEvent, group_id: int) -> None:
    if event.type != VkBotEventType.MESSAGE_NEW:
        return

    msg     = event.obj.message
    user_id = msg["from_id"]
    peer_id = msg["peer_id"]
    text    = (msg.get("text") or "").strip()

    if user_id <= 0:
        return

    current = states.get_state(user_id)

    # ── Сообщение из чата/ЛС оператора ──────────────────────────────
    if peer_id == OPERATOR_CHAT_ID and current == states.MAIN_MENU:
        is_stop    = text.strip().lower() == "/stop"
        has_active = bool(states.get_operator_users())
        if is_stop or has_active:
            print(f"[OPERATOR] text={text!r}")
            _handle_operator_message(vk, text)
            return

    print(f"[MSG] user={user_id} state={current!r} text={text!r}")

    if current == states.OPERATOR_WAIT:
        if _is_back(text):
            _go_main_menu(vk, user_id)
        else:
            _start_operator_session(vk, user_id, text)
        return

    if current == states.OPERATOR_ACTIVE:
        if _is_stop_client(text):
            _end_operator_session(vk, user_id, initiated_by="client")
        else:
            data = states.get_data(user_id)
            _send_to_operator(vk, user_id, text, data.get("user_name", "Клиент"))
        return

    if current == states.CHECK_CARD:
        if _is_back(text):
            _go_main_menu(vk, user_id)
        else:
            _check_card(vk, user_id, text)
        return

    if current == states.SCHEDULE_FILTER:
        data = states.get_data(user_id)
        _handle_schedule(vk, user_id, text, data)
        return

    if current == states.TRAINER_VIEW:
        _handle_trainer_nav(vk, user_id, text)
        return

    if current == states.FAQ_VIEW:
        _handle_faq(vk, user_id, text)
        return

    _handle_main_menu(vk, user_id, text)


# ──────────────────────────────────────────────
# Сообщения от оператора
# ──────────────────────────────────────────────
def _handle_operator_message(vk, text: str) -> None:
    print(f"[OPERATOR] text={text!r}")

    if text.strip().lower() == "/stop":
        active = list(states.get_operator_users())
        for uid in active:
            _end_operator_session(vk, uid, initiated_by="operator")
        reply = (
            f"✅ Все сессии завершены. Уведомлено клиентов: {len(active)}."
            if active else "Нет активных сессий."
        )
        _send(vk, OPERATOR_CHAT_ID, reply)
        return

    for uid in states.get_operator_users():
        _send(vk, uid, f"💼 Оператор:\n{text}")


def _start_operator_session(vk, user_id: int, problem_text: str) -> None:
    try:
        info = vk.users.get(user_ids=user_id)[0]
        user_name = f"{info['first_name']} {info['last_name']}"
    except Exception:
        user_name = f"Клиент #{user_id}"

    states.set_state(user_id, states.OPERATOR_ACTIVE, data={"user_name": user_name})
    states.add_operator_user(user_id)

    _send(vk, user_id,
          "✅ Ваше обращение принято! Оператор скоро ответит.\n\n"
          "Чтобы завершить диалог — нажмите кнопку ниже.",
          keyboard=keyboards.operator_stop())

    _send_to_operator(vk, user_id, problem_text, user_name)


def _end_operator_session(vk, user_id: int, initiated_by: str) -> None:
    states.remove_operator_user(user_id)
    states.set_state(user_id, states.MAIN_MENU)

    if initiated_by == "client":
        _send(vk, user_id,
              "Диалог с оператором завершён. Спасибо, что обратились в «Альбатрос»! 🙏",
              keyboard=keyboards.main_menu())
        _send(vk, OPERATOR_CHAT_ID, f"⚠️ Клиент ID {user_id} завершил диалог.")
    else:
        _send(vk, user_id,
              "Оператор завершил диалог. Спасибо за обращение в «Альбатрос»! 🙏",
              keyboard=keyboards.main_menu())


# ──────────────────────────────────────────────
# Главное меню
# ──────────────────────────────────────────────
def _handle_main_menu(vk, user_id: int, text: str) -> None:
    if text in ("/start", "Начать", ""):
        _send(vk, user_id,
              "👋 Добро пожаловать в фитнес-клуб «Альбатрос»!\n\n"
              "Я помогу узнать расписание, проверить абонемент, "
              "познакомить с тренерами или соединить с оператором.\n\n"
              "Выберите раздел:",
              keyboard=keyboards.main_menu())

    elif text == "❓ FAQ":
        states.set_state(user_id, states.FAQ_VIEW)
        _send(vk, user_id, "📖 FAQ. Выберите тему:", keyboard=keyboards.faq_menu())

    elif text == "🎫 Проверить абонемент":
        states.set_state(user_id, states.CHECK_CARD)
        _send(vk, user_id,
              "🎫 Введите номер карты абонемента\n(например: ALB-001):",
              keyboard=keyboards.back_button())

    elif text == "📅 Расписание":
        states.set_state(user_id, states.SCHEDULE_FILTER, data={"sub": "choose_filter"})
        _send(vk, user_id, "📅 Как отфильтровать расписание?",
              keyboard=keyboards.schedule_filter_menu())

    elif text == "👨‍🏫 Тренеры":
        trainers = _data().list_trainers()
        if not trainers:
            _send(vk, user_id,
                  "⚠️ Список тренеров временно недоступен. "
                  "Попробуйте позже или свяжитесь с оператором.",
                  keyboard=keyboards.main_menu())
            return
        states.set_state(user_id, states.TRAINER_VIEW, data={"index": 0})
        _send(vk, user_id,
              _format_trainer(trainers[0], 0, len(trainers)),
              keyboard=keyboards.trainer_nav(has_prev=False,
                                              has_next=len(trainers) > 1))

    elif text == "📞 Оператор":
        states.set_state(user_id, states.OPERATOR_WAIT)
        _send(vk, user_id,
              "📞 Соединяем с оператором...\n\n"
              "Опишите ваш вопрос или проблему в следующем сообщении:",
              keyboard=keyboards.back_button())

    else:
        _send(vk, user_id, "Используйте кнопки меню 👇", keyboard=keyboards.main_menu())


# ──────────────────────────────────────────────
# FAQ
# ──────────────────────────────────────────────
def _handle_faq(vk, user_id: int, text: str) -> None:
    if _is_back(text):
        _go_main_menu(vk, user_id)
    elif text in FAQ_TEXTS:
        _send(vk, user_id, FAQ_TEXTS[text], keyboard=keyboards.faq_menu())
    else:
        _send(vk, user_id, "Выберите тему из меню:", keyboard=keyboards.faq_menu())


# ──────────────────────────────────────────────
# Проверка абонемента
# ──────────────────────────────────────────────
def _check_card(vk, user_id: int, card_id: str) -> None:
    member = _data().find_member(card_id.upper().strip())
    if not member:
        _send(vk, user_id,
              f"❌ Абонемент «{card_id}» не найден или временно недоступен.\n\n"
              "Проверьте номер или обратитесь на ресепшн.",
              keyboard=keyboards.back_button())
        return

    valid_until = member["valid_until"]
    sessions    = member["sessions_left"]
    is_active   = valid_until >= date.today().isoformat()

    if not is_active:
        status = "🔴 Истёк"
    elif sessions == 0:
        status = "🟡 Занятия исчерпаны"
    elif sessions <= 3:
        status = "🟡 Заканчивается"
    else:
        status = "🟢 Активен"

    msg = (
        f"🎫 Информация об абонементе\n\n"
        f"👤 Владелец:         {member['name']}\n"
        f"🔑 Номер карты:      {member['card_id']}\n"
        f"📊 Статус:           {status}\n"
        f"🎯 Осталось занятий: {sessions}\n"
        f"📅 Действителен до:  {valid_until}"
    )
    states.set_state(user_id, states.MAIN_MENU)
    _send(vk, user_id, msg, keyboard=keyboards.main_menu())


# ──────────────────────────────────────────────
# Расписание
# ──────────────────────────────────────────────
def _handle_schedule(vk, user_id: int, text: str, data: dict) -> None:
    if _is_back(text):
        _go_main_menu(vk, user_id)
        return

    sub = data.get("sub", "choose_filter")

    if text == "🔙 Назад":
        states.set_data(user_id, {"sub": "choose_filter"})
        _send(vk, user_id, "📅 Как отфильтровать расписание?",
              keyboard=keyboards.schedule_filter_menu())
        return

    if sub == "choose_filter":
        if text == "📆 По дню недели":
            states.set_data(user_id, {"sub": "choose_day"})
            _send(vk, user_id, "Выберите день недели:", keyboard=keyboards.days_menu())
        elif text == "🏋️ По направлению":
            directions = _get_directions()
            if not directions:
                _send(vk, user_id,
                      "⚠️ Расписание временно недоступно. Попробуйте позже.",
                      keyboard=keyboards.schedule_filter_menu())
                return
            states.set_data(user_id, {"sub": "choose_direction", "directions": directions})
            _send(vk, user_id, "Выберите направление:", keyboard=keyboards.directions_menu(directions))
        else:
            _send(vk, user_id, "Выберите фильтр:", keyboard=keyboards.schedule_filter_menu())

    elif sub == "choose_day":
        if text in _DAYS:
            items = [s for s in _data().list_schedule() if s["day"] == text]
            _send(vk, user_id,
                  f"📅 Расписание на {text}:\n\n" + _format_schedule(items),
                  keyboard=keyboards.days_menu())
        else:
            _send(vk, user_id, "Выберите день из списка:", keyboard=keyboards.days_menu())

    elif sub == "choose_direction":
        directions = data.get("directions", _get_directions())
        if text in directions:
            items = [s for s in _data().list_schedule() if s["direction"] == text]
            _send(vk, user_id,
                  f"🏋️ {text}:\n\n" + _format_schedule(items),
                  keyboard=keyboards.directions_menu(directions))
        else:
            _send(vk, user_id, "Выберите направление:", keyboard=keyboards.directions_menu(directions))


# ──────────────────────────────────────────────
# Тренеры
# ──────────────────────────────────────────────
def _handle_trainer_nav(vk, user_id: int, text: str) -> None:
    if _is_back(text):
        _go_main_menu(vk, user_id)
        return

    data     = states.get_data(user_id)
    trainers = _data().list_trainers()
    total    = len(trainers)
    if total == 0:
        _go_main_menu(vk, user_id)
        return

    idx = data.get("index", 0)
    if text == "▶️ Следующий":
        idx = min(idx + 1, total - 1)
    elif text == "◀️ Предыдущий":
        idx = max(idx - 1, 0)

    states.set_data(user_id, {"index": idx})
    _send(vk, user_id,
          _format_trainer(trainers[idx], idx, total),
          keyboard=keyboards.trainer_nav(has_prev=idx > 0, has_next=idx < total - 1))


# ──────────────────────────────────────────────
# Вспомогательные предикаты
# ──────────────────────────────────────────────
def _is_back(text: str) -> bool:
    return text in ("🔙 Главное меню",)


def _is_stop_client(text: str) -> bool:
    return text in ("❌ Завершить диалог с оператором", "🔙 Главное меню")
