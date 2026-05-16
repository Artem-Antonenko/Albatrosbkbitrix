"""
Тесты BitrixProvider — без обращения к настоящему Битриксу.
Подменяем urllib.request.urlopen фейковыми ответами и проверяем,
что провайдер корректно разбирает Битрикс-формат и обрабатывает ошибки.

Запуск:
    cd albatrosvk && python -m unittest tests.test_bitrix_provider
"""
import io
import json
import os
import sys
import unittest
import urllib.error
from unittest.mock import patch, MagicMock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

WEBHOOK = "https://test.bitrix24.ru/rest/1/test_token/"


def _fake_response(payload: dict):
    """Имитировать urllib.request.urlopen с заданным JSON-ответом."""
    body = json.dumps(payload).encode("utf-8")
    fake = MagicMock()
    fake.__enter__ = lambda self: self
    fake.__exit__  = lambda self, *a: None
    fake.read      = lambda: body
    return fake


class BitrixProviderTest(unittest.TestCase):

    def _provider(self):
        from providers.bitrix import BitrixProvider
        return BitrixProvider(webhook_url=WEBHOOK)

    # ────────────────────────────────────────────
    def test_find_member_success(self):
        # Контакт + сделка приходят разными запросами,
        # подменяем urlopen так, чтобы возвращать их по очереди
        contact_payload = {"result": [{
            "ID": "42", "NAME": "Мария", "LAST_NAME": "Иванова", "SECOND_NAME": "Петровна",
        }]}
        deal_payload = {"result": [{
            "ID": "100",
            "UF_CRM_SESSIONS_LEFT": "12",
            "UF_CRM_VALID_UNTIL":   "2026-06-15T00:00:00+03:00",
        }]}
        responses = [_fake_response(contact_payload), _fake_response(deal_payload)]

        with patch("urllib.request.urlopen", side_effect=responses):
            m = self._provider().find_member("ALB-001")

        self.assertIsNotNone(m)
        self.assertEqual(m["card_id"],       "ALB-001")
        self.assertEqual(m["name"],          "Иванова Мария Петровна")
        self.assertEqual(m["sessions_left"], 12)
        self.assertEqual(m["valid_until"],   "2026-06-15")

    def test_find_member_no_contact(self):
        with patch("urllib.request.urlopen",
                   return_value=_fake_response({"result": []})):
            m = self._provider().find_member("ALB-999")
        self.assertIsNone(m)

    def test_find_member_network_error(self):
        with patch("urllib.request.urlopen",
                   side_effect=urllib.error.URLError("connection refused")):
            m = self._provider().find_member("ALB-001")
        self.assertIsNone(m)

    def test_find_member_api_error(self):
        # Битрикс отдаёт ошибку API — провайдер должен вернуть None
        with patch("urllib.request.urlopen",
                   return_value=_fake_response({
                       "error":             "QUERY_LIMIT_EXCEEDED",
                       "error_description": "Слишком много запросов",
                   })):
            m = self._provider().find_member("ALB-001")
        self.assertIsNone(m)

    # ────────────────────────────────────────────
    def test_list_trainers(self):
        payload = {"result": [
            {
                "NAME": "Мария Орлова",
                "PROPERTY_SPEC": {"123": "Йога"},
                "PROPERTY_DESC": {"124": "Сертифицированный инструктор"},
            },
            {
                "NAME": "Андрей Громов",
                "PROPERTY_SPEC": {"125": "Кроссфит", "126": "Силовые"},
                "PROPERTY_DESC": {"127": "КМС по тяжёлой атлетике"},
            },
        ]}
        with patch("urllib.request.urlopen",
                   return_value=_fake_response(payload)):
            trainers = self._provider().list_trainers()

        self.assertEqual(len(trainers), 2)
        self.assertEqual(trainers[0]["name"], "Мария Орлова")
        self.assertEqual(trainers[0]["specialization"], "Йога")
        # Множественное значение склеивается через запятую
        self.assertEqual(trainers[1]["specialization"], "Кроссфит, Силовые")

    def test_list_schedule(self):
        payload = {"result": [
            {
                "PROPERTY_DAY":       {"1": "Пн"},
                "PROPERTY_TIME":      {"2": "09:00"},
                "PROPERTY_DIRECTION": {"3": "Йога"},
                "PROPERTY_TRAINER":   {"4": "Мария Орлова"},
                "PROPERTY_HALL":      {"5": "Зал 1"},
            },
        ]}
        with patch("urllib.request.urlopen",
                   return_value=_fake_response(payload)):
            schedule = self._provider().list_schedule()

        self.assertEqual(len(schedule), 1)
        item = schedule[0]
        self.assertEqual(item["day"], "Пн")
        self.assertEqual(item["time"], "09:00")
        self.assertEqual(item["direction"], "Йога")

    def test_health_check(self):
        with patch("urllib.request.urlopen",
                   return_value=_fake_response({"result": {"now": "2026-05-10"}})):
            self.assertTrue(self._provider().health_check())

        with patch("urllib.request.urlopen",
                   side_effect=urllib.error.URLError("down")):
            self.assertFalse(self._provider().health_check())

    def test_constructor_requires_webhook(self):
        from providers.bitrix import BitrixProvider
        with self.assertRaises(RuntimeError):
            # без аргумента и без переменной окружения
            os.environ.pop("BITRIX_WEBHOOK_URL", None)
            BitrixProvider()


if __name__ == "__main__":
    unittest.main()
