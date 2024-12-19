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

# Парсер текстовых запросов
def parse_user_query(query):
    criteria = {
        "rooms": None,  # Количество комнат
        "min_area": None,  # Минимальная площадь
        "max_area": None,  # Максимальная площадь
        "complex": None,  # Название ЖК
        "min_floor": None,  # Минимальный этаж
        "max_floor": None,  # Максимальный этаж
        "metric": None  # Метрика: средняя цена, минимальная цена, максимальная цена
    }

    # Извлечение параметров
    rooms_match = re.search(r"(\d+)-комнат", query)
    if rooms_match:
        criteria["rooms"] = int(rooms_match.group(1))

    area_match = re.search(r"(\d+)\s*квадрат", query)
    if area_match:
        area = int(area_match.group(1))
        criteria["min_area"] = area - 1  # Погрешность ±1 м²
        criteria["max_area"] = area + 1

    complex_match = re.search(r"в ЖК (\w+)", query)
    if complex_match:
        criteria["complex"] = complex_match.group(1)

    floor_match = re.search(r"на этажах от (\d+) до (\d+)", query)
    if floor_match:
        criteria["min_floor"] = int(floor_match.group(1))
        criteria["max_floor"] = int(floor_match.group(2))

    # Определение метрики
    if "средняя цена" in query:
        criteria["metric"] = "average"
    elif "минимальная цена" in query:
        criteria["metric"] = "min"
    elif "максимальная цена" in query:
        criteria["metric"] = "max"

    logger.info(f"Распознанные критерии: {criteria}")
    return criteria

# Фильтрация данных
def filter_data(df, criteria):
    logger.info(f"Начата фильтрация данных с критериями: {criteria}")
    if criteria["rooms"] is not None:
        df = df[df["Комнат"] == criteria["rooms"]]

    if criteria["min_area"] is not None and criteria["max_area"] is not None:
        df = df[df["Площадь"].between(criteria["min_area"], criteria["max_area"])]

    if criteria["complex"] is not None:
        df = df[df["Жилой комплекс Раздел 1"].str.contains(criteria["complex"], na=False)]

    if criteria["min_floor"] is not None and criteria["max_floor"] is not None:
        df = df[df["Этаж"].between(criteria["min_floor"], criteria["max_floor"])]

    logger.info(f"Фильтрация завершена. Найдено строк: {len(df)}")
    return df

# Генерация ответа
def generate_response(filtered_df, metric):
    logger.info(f"Генерация ответа. Метрика: {metric}, Количество строк: {len(filtered_df)}")
    if filtered_df.empty:
        return "По вашему запросу ничего не найдено."

    if metric == "average":
        avg_price = filtered_df["Цена"].mean()
        return f"Средняя цена для выбранных квартир: {avg_price:.2f} рублей."
    elif metric == "min":
        min_price = filtered_df["Цена"].min()
        return f"Минимальная цена для выбранных квартир: {min_price:.2f} рублей."
    elif metric == "max":
        max_price = filtered_df["Цена"].max()
        return f"Максимальная цена для выбранных квартир: {max_price:.2f} рублей."

    response = "Вот подходящие квартиры:\n"
    for _, row in filtered_df.iterrows():
        response += (
            f"- ЖК: {row['Жилой комплекс Раздел 1']}, Площадь: {row['Площадь']} м², "
            f"Этаж: {row['Этаж']}, Цена: {row['Цена']} рублей\n"
        )
    return response

# Обработка текстовых запросов
async def process_user_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    logger.info(f"Получен текстовый запрос от пользователя: {user_message}")

    try:
        # Загрузка данных
        logger.info("Загрузка данных из CSV файла...")
        df = pd.read_csv("data.csv", encoding="utf-8", sep=";", on_bad_lines="skip", low_memory=False)
        df["Комнат"] = pd.to_numeric(df["Комнат"], errors="coerce")
        df["Площадь"] = pd.to_numeric(df["Площадь"], errors="coerce")
        df["Цена"] = pd.to_numeric(df["Цена"], errors="coerce")

        # Парсинг запроса
        criteria = parse_user_query(user_message)

        # Фильтрация данных
        filtered_df = filter_data(df, criteria)

        # Формирование ответа
        response = generate_response(filtered_df, criteria["metric"])
        logger.info(f"Сформированный ответ: {response}")

        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Ошибка обработки запроса: {e}", exc_info=True)
        await update.message.reply_text("Произошла ошибка при обработке данных.")

# Вебхуковый маршрут
async def webhook_handler(request):
    update_data = await request.json()
    logger.info(f"Получены данные вебхука: {update_data}")
    update = Update.de_json(update_data, application.bot)
    await application.update_queue.put(update)
    return web.Response(text="OK")

# Основной процесс
async def main():
    global application

    # Инициализация приложения Telegram
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    await application.initialize()  # Инициализация приложения
    await application.start()  # Запуск приложения

    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_user_query))

    # Настройка вебхуков
    app = web.Application()
    app.router.add_post("/webhook", webhook_handler)

    # Запуск веб-сервера
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    logger.info(f"Запуск вебхука на порту {PORT}")

    # Загрузка файла с Яндекс.Диска
    await download_yandex_file()

    try:
        # Ожидание завершения
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Завершение приложения...")
    finally:
        # Корректная остановка приложения
        await application.stop()
        await runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
