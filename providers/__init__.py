"""
Фабрика провайдеров данных. Используется в main.py:

    from providers import make_provider
    provider = make_provider()

Источник выбирается по переменной окружения DATA_PROVIDER:
    DATA_PROVIDER=local   → LocalProvider  (по умолчанию, SQLite + JSON)
    DATA_PROVIDER=bitrix  → BitrixProvider (Битрикс24 через вебхук)
"""
import os

from .base   import DataProvider
from .local  import LocalProvider
from .bitrix import BitrixProvider


def make_provider() -> DataProvider:
    """Прочитать DATA_PROVIDER и вернуть готовый экземпляр провайдера."""
    name = os.getenv("DATA_PROVIDER", "local").strip().lower()

    if name == "local":
        return LocalProvider()
    if name == "bitrix":
        return BitrixProvider()

    raise RuntimeError(
        f"Неизвестное значение DATA_PROVIDER={name!r}. "
        f"Допустимые: 'local', 'bitrix'."
    )


__all__ = ["DataProvider", "LocalProvider", "BitrixProvider", "make_provider"]
