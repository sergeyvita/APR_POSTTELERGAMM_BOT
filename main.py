import os
import logging
import pandas as pd
from aiohttp import web, ClientSession
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import ChatCompletion
import asyncio
import re

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Переменные окружения
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
YANDEX_DISK_TOKEN = os.getenv("YANDEX_DISK_TOKEN")
YANDEX_FILE_URL = os.getenv("YANDEX_FILE_URL")
PORT = int(os.getenv("PORT", "8080"))

# Инициализация OpenAI
chat = ChatCompletion(api_key=OPENAI_API_KEY)

# Описание столбцов файла
COLUMN_MAPPING = {
    "Жилой комплекс Раздел 1": "Название ЖК",
    "Город": "Город",
    "Литер Раздел 2": "Номер литера",
    "Подъезд Раздел 3": "Номер подъезда",
    "Этаж": "Номер этажа",
    "Номер квартиры": "Номер квартиры",
    "Цена": "Цена без скидок",
    "Цена со скидкой": "Цена со скидкой",
    "Цена за м2": "Цена за м2",
    "Цена за кв.м. со скидкой": "Цена за м2 со скидкой",
    "Комнат": "Количество комнат",
    "Площадь": "Общая площадь",
    "Продано": "Продано",
    "Бронь": "Бронь",
    "Акция": "Акция",
    "ДКП": "Договор купли-продажи",
    "Очередь": "Очередь строительства",
    "Литер": "Литер",
    "Подъезд": "Подъезд",
    "Дата обновления": "Дата обновления"
}

IGNORE_COLUMNS = [
    "Картинка для анонса", "Доп фото", "Позиция в шахматке", "Жилой комплекс", "Путь до картинок"
]

shutdown_event = asyncio.Event()

# Загрузка данных с Яндекс.Диска
async def download_yandex_file():
    public_url = YANDEX_FILE_URL
    headers = {
        'Authorization': f'OAuth {YANDEX_DISK_TOKEN}'
    }
    try:
        async with ClientSession() as session:
            async with session.get(
                f"https://cloud-api.yandex.net/v1/disk/public/resources/download?public_key={public_url}",
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    direct_link = data.get("href")
                    if direct_link:
                        async with session.get(direct_link) as file_response:
                            if file_response.status == 200:
                                content = await file_response.text()
                                with open("data.csv", "w", encoding="utf-8") as f:
                                    f.write(content)
                                logger.info("Файл успешно загружен с Яндекс.Диска.")
                            else:
                                logger.error(f"Ошибка загрузки файла: {file_response.status}")
                else:
                    logger.error(f"Ошибка получения прямой ссылки: {response.status}")
    except Exception as e:
        logger.error(f"Ошибка при загрузке файла: {e}")

# Добавление корневого маршрута для проверки
async def root_handler(request):
    return web.Response(text="Сервер работает!")

# Вебхуковый маршрут
async def webhook_handler(request):
    try:
        logger.info("Получен запрос на маршрут /webhook")
        update_data = await request.json()
        logger.info(f"Полученные данные: {update_data}")
        update = Update.de_json(update_data, application.bot)
        await application.update_queue.put(update)
        return web.Response(text="OK")
    except Exception as e:
        logger.error(f"Ошибка обработки вебхука: {e}", exc_info=True)
        return web.Response(status=500)

# Основной процесс
async def main():
    global application

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    await application.initialize()
    await application.start()

    # Настройка маршрутов веб-сервера
    app = web.Application()
    app.router.add_get("/", root_handler)  # Корневой маршрут
    app.router.add_post("/webhook", webhook_handler)  # Вебхук

    try:
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()
        logger.info(f"Сервер запущен и слушает порт {PORT}")

        # Загрузка данных
        await download_yandex_file()

        await shutdown_event.wait()
    except Exception as e:
        logger.error(f"Ошибка в основном цикле: {e}")
    finally:
        await application.stop()
        await runner.cleanup()
        logger.info("Приложение завершено корректно")

# Для управления остановкой
def signal_handler(*_):
    shutdown_event.set()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)