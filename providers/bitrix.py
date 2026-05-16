"""
BitrixProvider — источник данных через REST API Битрикс24.

Использует механизм «входящего вебхука» Битрикса: по адресу вида
    https://albatros.bitrix24.ru/rest/<user_id>/<token>/
доступны методы CRM без OAuth-приложения. Лимит — 2 запроса/секунду на вебхук.

Сущности в Битрикс24 (создаются администратором, см. README_BITRIX.md):
  - КОНТАКТ + СДЕЛКА  — для каждого абонемента
        Контакт.UF_CRM_CARD_ID = "ALB-001"           (номер карты)
        Сделка.CATEGORY_ID = ID воронки «Абонементы»
        Сделка.UF_CRM_SESSIONS_LEFT = 12             (осталось занятий)
        Сделка.UF_CRM_VALID_UNTIL  = «2026-06-15»    (срок действия)
  - УНИВЕРСАЛЬНЫЙ СПИСОК «Тренеры»
        Поля: NAME (ФИО), PROPERTY_SPEC (специализация), PROPERTY_DESC (описание)
  - УНИВЕРСАЛЬНЫЙ СПИСОК «Расписание»
        Поля: NAME, PROPERTY_DAY, PROPERTY_TIME, PROPERTY_DIRECTION,
              PROPERTY_TRAINER, PROPERTY_HALL

Если Битрикс недоступен или вернул ошибку — методы возвращают None / пустой
список и пишут в лог. Бот в этом случае сообщает клиенту «временно недоступно,
обратитесь на ресепшн».
"""
import os
import time
import json
import urllib.parse
import urllib.request
import urllib.error

from .base import DataProvider


# Идентификаторы универсальных списков задаются администратором при настройке.
# Их значения читаются из .env, чтобы не править код при переезде на другой портал.
TRAINERS_LIST_IBLOCK_ID  = os.getenv("BITRIX_TRAINERS_IBLOCK_ID",  "0")
SCHEDULE_LIST_IBLOCK_ID  = os.getenv("BITRIX_SCHEDULE_IBLOCK_ID",  "0")


class BitrixProvider(DataProvider):
    """Источник данных: Битрикс24 (входящий вебхук)."""

    # Сколько секунд кешировать справочные данные (тренеры, расписание).
    # Абонементы НЕ кешируются — всегда свежие.
    CACHE_TTL_SEC = 60

    def __init__(self, webhook_url: str | None = None) -> None:
        if webhook_url is None:
            webhook_url = os.getenv("BITRIX_WEBHOOK_URL", "").strip()
        if not webhook_url:
            raise RuntimeError(
                "BitrixProvider: не задан BITRIX_WEBHOOK_URL в .env. "
                "Получите URL в Битрикс24: Разработчикам → Другое → "
                "Входящий вебхук → выдайте права crm + lists."
            )
        # Гарантируем завершающий слэш — Битрикс к этому требователен
        if not webhook_url.endswith("/"):
            webhook_url += "/"
        self._webhook_url = webhook_url

        # Кеш: ключ → (timestamp, value)
        self._cache: dict[str, tuple[float, object]] = {}

        print(f"[PROVIDER] BitrixProvider запущен; webhook={webhook_url[:40]}…")

    # ─────────────────────────────────────────────────────────────
    # Низкоуровневый вызов метода REST API
    # ─────────────────────────────────────────────────────────────
    def _call(self, method: str, params: dict | None = None) -> dict | None:
        """
        Вызвать метод Битрикс REST API. Возвращает разобранный JSON-ответ
        либо None при сетевой/HTTP-ошибке.

        Параметры передаются как form-urlencoded (стандарт для входящих вебхуков).
        """
        url  = self._webhook_url + method
        data = urllib.parse.urlencode(params or {}, doseq=True).encode("utf-8")
        req  = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            print(f"[BITRIX] Сетевая ошибка при вызове {method}: {exc}")
            return None
        except (ValueError, json.JSONDecodeError) as exc:
            print(f"[BITRIX] Невалидный JSON от {method}: {exc}")
            return None

        if "error" in payload:
            print(f"[BITRIX] API-ошибка {method}: "
                  f"{payload.get('error')} — {payload.get('error_description')}")
            return None
        return payload

    # ─────────────────────────────────────────────────────────────
    # Простой in-memory кеш с TTL
    # ─────────────────────────────────────────────────────────────
    def _cached(self, key: str, fetch_fn) -> object:
        now = time.time()
        if key in self._cache:
            ts, value = self._cache[key]
            if now - ts < self.CACHE_TTL_SEC:
                return value
        value = fetch_fn()
        self._cache[key] = (now, value)
        return value

    # ─────────────────────────────────────────────────────────────
    # Метод 1: поиск абонемента по номеру карты
    # ─────────────────────────────────────────────────────────────
    def find_member(self, card_id: str) -> dict | None:
        """
        Алгоритм:
          1) Найти Контакт по UF_CRM_CARD_ID = card_id (метод crm.contact.list).
          2) По ID контакта найти связанную с ним Сделку
             (метод crm.deal.list, фильтр CONTACT_ID).
          3) Собрать ответ из ФИО контакта + полей сделки.
        """
        contact_resp = self._call("crm.contact.list", {
            "filter[UF_CRM_CARD_ID]": card_id,
            "select[]":               ["ID", "NAME", "LAST_NAME", "SECOND_NAME"],
        })
        if contact_resp is None:
            return None
        contacts = contact_resp.get("result", [])
        if not contacts:
            return None
        contact = contacts[0]

        deal_resp = self._call("crm.deal.list", {
            "filter[CONTACT_ID]": contact["ID"],
            "filter[CLOSED]":     "N",  # только открытые сделки
            "select[]":           ["ID", "UF_CRM_SESSIONS_LEFT", "UF_CRM_VALID_UNTIL"],
            "order[ID]":          "DESC",  # самая свежая сделка
        })
        if deal_resp is None:
            return None
        deals = deal_resp.get("result", [])
        if not deals:
            # Контакт есть, но активной сделки-абонемента нет
            return None
        deal = deals[0]

        full_name = " ".join(
            part for part in (
                contact.get("LAST_NAME"),
                contact.get("NAME"),
                contact.get("SECOND_NAME"),
            ) if part
        ).strip() or "(имя не указано)"

        return {
            "card_id":       card_id,
            "name":          full_name,
            "sessions_left": int(deal.get("UF_CRM_SESSIONS_LEFT") or 0),
            "valid_until":   (deal.get("UF_CRM_VALID_UNTIL") or "")[:10],  # YYYY-MM-DD
        }

    # ─────────────────────────────────────────────────────────────
    # Метод 2: список тренеров
    # ─────────────────────────────────────────────────────────────
    def list_trainers(self) -> list[dict]:
        return self._cached("trainers", self._fetch_trainers)

    def _fetch_trainers(self) -> list[dict]:
        resp = self._call("lists.element.get", {
            "IBLOCK_TYPE_ID": "lists",
            "IBLOCK_ID":      TRAINERS_LIST_IBLOCK_ID,
        })
        if resp is None:
            return []
        result = []
        for el in resp.get("result", []):
            result.append({
                "name":           (el.get("NAME") or "").strip(),
                "specialization": _first_value(el.get("PROPERTY_SPEC", {})),
                "description":    _first_value(el.get("PROPERTY_DESC", {})),
            })
        return [t for t in result if t["name"]]

    # ─────────────────────────────────────────────────────────────
    # Метод 3: расписание
    # ─────────────────────────────────────────────────────────────
    def list_schedule(self) -> list[dict]:
        return self._cached("schedule", self._fetch_schedule)

    def _fetch_schedule(self) -> list[dict]:
        resp = self._call("lists.element.get", {
            "IBLOCK_TYPE_ID": "lists",
            "IBLOCK_ID":      SCHEDULE_LIST_IBLOCK_ID,
        })
        if resp is None:
            return []
        result = []
        for el in resp.get("result", []):
            result.append({
                "day":       _first_value(el.get("PROPERTY_DAY",       {})),
                "time":      _first_value(el.get("PROPERTY_TIME",      {})),
                "direction": _first_value(el.get("PROPERTY_DIRECTION", {})),
                "trainer":   _first_value(el.get("PROPERTY_TRAINER",   {})),
                "hall":      _first_value(el.get("PROPERTY_HALL",      {})),
            })
        return [r for r in result if r["day"] and r["time"]]

    # ─────────────────────────────────────────────────────────────
    # Health-check: бьёмся коротким запросом server.time
    # ─────────────────────────────────────────────────────────────
    def health_check(self) -> bool:
        return self._call("server.time") is not None


def _first_value(prop: dict) -> str:
    """
    В ответах lists.element.get свойства приходят как dict вида
        {"123": "Йога"}      — для одиночных значений
        {"123": "Йога", "124": "Медитация"} — для множественных
    Берём первое значение или склеиваем через запятую.
    """
    if not isinstance(prop, dict) or not prop:
        return ""
    values = [str(v).strip() for v in prop.values() if v]
    return ", ".join(values)
