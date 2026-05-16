"""
Тесты LocalProvider — убеждаемся, что обёртка корректно отдаёт данные
из существующих SQLite и data.json в формате, который ожидает бот.

Запуск:
    cd albatrosvk && python -m unittest tests.test_local_provider
"""
import json
import os
import sys
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta

# Чтобы импортировать модули проекта без установки пакета
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


class LocalProviderTest(unittest.TestCase):
    """Изолированный тест: подменяет DB_PATH временным файлом."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir   = tempfile.mkdtemp(prefix="albatros_test_")
        cls.db_path  = os.path.join(cls.tmpdir, "members.db")
        cls.json_path = os.path.join(cls.tmpdir, "data.json")

        # Подмена DB_PATH в модуле db
        import db
        cls._orig_db_path = db.DB_PATH
        db.DB_PATH = cls.db_path

        # Создать тестовую БД
        today = date.today()
        with sqlite3.connect(cls.db_path) as conn:
            conn.execute("""
                CREATE TABLE members (
                    card_id TEXT PRIMARY KEY, name TEXT,
                    sessions_left INTEGER, valid_until TEXT
                )
            """)
            conn.executemany(
                "INSERT INTO members VALUES (?, ?, ?, ?)",
                [
                    ("ALB-001", "Тестовый Активный",  10, (today + timedelta(days=30)).isoformat()),
                    ("ALB-002", "Тестовый Истёкший",   0, (today - timedelta(days=10)).isoformat()),
                ],
            )

        # Создать тестовый JSON
        with open(cls.json_path, "w", encoding="utf-8") as f:
            json.dump({
                "schedule": [
                    {"day": "Пн", "time": "09:00", "direction": "Йога",
                     "trainer": "Тренер Один", "hall": "Зал 1"},
                    {"day": "Вт", "time": "10:00", "direction": "Пилатес",
                     "trainer": "Тренер Два",  "hall": "Зал 2"},
                ],
                "trainers": [
                    {"name": "Тренер Один", "specialization": "Йога",
                     "description": "Описание один"},
                    {"name": "Тренер Два",  "specialization": "Пилатес",
                     "description": "Описание два"},
                ],
            }, f)

    @classmethod
    def tearDownClass(cls):
        import db, shutil
        db.DB_PATH = cls._orig_db_path
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def _provider(self):
        from providers.local import LocalProvider
        return LocalProvider(data_json_path=self.json_path)

    # ────────────────────────────────────────────
    def test_find_member_existing(self):
        m = self._provider().find_member("ALB-001")
        self.assertIsNotNone(m)
        self.assertEqual(m["card_id"], "ALB-001")
        self.assertEqual(m["name"], "Тестовый Активный")
        self.assertEqual(m["sessions_left"], 10)

    def test_find_member_missing(self):
        m = self._provider().find_member("ALB-999")
        self.assertIsNone(m)

    def test_list_trainers(self):
        trainers = self._provider().list_trainers()
        self.assertEqual(len(trainers), 2)
        self.assertEqual(trainers[0]["name"], "Тренер Один")
        self.assertIn("specialization", trainers[0])
        self.assertIn("description",    trainers[0])

    def test_list_schedule(self):
        schedule = self._provider().list_schedule()
        self.assertEqual(len(schedule), 2)
        self.assertEqual(schedule[0]["day"], "Пн")
        for item in schedule:
            for key in ("day", "time", "direction", "trainer", "hall"):
                self.assertIn(key, item)


if __name__ == "__main__":
    unittest.main()
