"""Точка входа — запуск Long Poll цикла VK-бота «Альбатрос»."""
# load_dotenv() ОБЯЗАН быть первым — до импорта bot.py и провайдеров,
# которые читают переменные окружения на уровне модуля.
from dotenv import load_dotenv
load_dotenv()

import os
import sys
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType

import bot
from providers import make_provider

VK_TOKEN = os.getenv("VK_TOKEN")
GROUP_ID  = os.getenv("GROUP_ID")

if not VK_TOKEN or not GROUP_ID:
    sys.exit("[ERROR] Не заданы VK_TOKEN или GROUP_ID в .env")

GROUP_ID = int(GROUP_ID)


def main() -> None:
    # Выбор источника данных (LocalProvider или BitrixProvider).
    # Решение принимается по переменной DATA_PROVIDER из .env.
    provider = make_provider()
    bot.init(provider)

    vk_session = vk_api.VkApi(token=VK_TOKEN)
    vk         = vk_session.get_api()
    longpoll   = VkBotLongPoll(vk_session, GROUP_ID)

    print(f"[BOOT] Бот «Альбатрос» запущен. GROUP_ID={GROUP_ID}")
    print("[BOOT] Ожидание сообщений... (Ctrl+C для остановки)")

    for event in longpoll.listen():
        try:
            bot.handle_event(vk, event, GROUP_ID)
        except Exception as exc:
            print(f"[ERROR] {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
