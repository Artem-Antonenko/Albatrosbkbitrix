"""
LocalProvider — провайдер на базе локальных данных:
  - абонементы → SQLite (через существующий модуль db.py)
  - тренеры и расписание → файл data/data.json

Не требует никаких внешних сервисов и интернета. Используется по умолчанию,
а также для разработки и демонстрации.
"""
import json
import os

import db
from .base import DataProvider


class LocalProvider(DataProvider):
    """Источник данных: локальный SQLite + JSON-файл."""

    def __init__(self, data_json_path: str | None = None) -> None:
        if data_json_path is None:
            data_json_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "data", "data.json",
            )
        self._data_json_path = data_json_path
        self._cached_data: dict | None = None

        # БД инициализируется при первом обращении или при старте main.py
        db.init_db()
        print(f"[PROVIDER] LocalProvider запущен; data.json={data_json_path}")

    # ── Внутреннее: читаем JSON один раз, держим в памяти ─────────
    def _load_json(self) -> dict:
        if self._cached_data is None:
            with open(self._data_json_path, encoding="utf-8") as f:
                self._cached_data = json.load(f)
        return self._cached_data

    # ── Контракт DataProvider ─────────────────────────────────────
    def find_member(self, card_id: str) -> dict | None:
        return db.find_member(card_id)

    def list_trainers(self) -> list[dict]:
        return self._load_json().get("trainers", [])

    def list_schedule(self) -> list[dict]:
        return self._load_json().get("schedule", [])
