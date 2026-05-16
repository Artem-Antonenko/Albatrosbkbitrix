# Состояния пользователя в State Machine
MAIN_MENU      = "MAIN_MENU"
OPERATOR_WAIT  = "OPERATOR_WAIT"   # описание проблемы ещё не получено
OPERATOR_ACTIVE = "OPERATOR_ACTIVE" # активный диалог с оператором
SCHEDULE_FILTER = "SCHEDULE_FILTER" # выбор фильтра / просмотр расписания
CHECK_CARD     = "CHECK_CARD"      # ожидание ввода номера карты
TRAINER_VIEW   = "TRAINER_VIEW"    # просмотр карточек тренеров
FAQ_VIEW       = "FAQ_VIEW"        # просмотр FAQ

# Хранилище: {user_id: {"state": str, "data": dict}}
_user_states: dict[int, dict] = {}

# Множество user_id-ов в активном диалоге с оператором
_operator_users: set[int] = set()


def get_state(user_id: int) -> str:
    return _user_states.get(user_id, {}).get("state", MAIN_MENU)


def set_state(user_id: int, state: str, data: dict | None = None) -> None:
    if user_id not in _user_states:
        _user_states[user_id] = {}
    _user_states[user_id]["state"] = state
    if data is not None:
        _user_states[user_id]["data"] = data
    print(f"[STATE] user_id={user_id} -> {state}")


def get_data(user_id: int) -> dict:
    return _user_states.get(user_id, {}).get("data", {})


def set_data(user_id: int, data: dict) -> None:
    if user_id not in _user_states:
        _user_states[user_id] = {"state": MAIN_MENU}
    _user_states[user_id]["data"] = data


def add_operator_user(user_id: int) -> None:
    _operator_users.add(user_id)


def remove_operator_user(user_id: int) -> None:
    _operator_users.discard(user_id)


def get_operator_users() -> set[int]:
    return _operator_users.copy()
