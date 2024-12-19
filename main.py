import os
import logging
import pandas as pd
from aiohttp import web, ClientSession
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import ChatCompletion
import asyncio

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

# Глобальный кэш для данных
cached_df = None

# Загрузка данных с файла
def load_file():
    global cached_df
    if cached_df is None:
        cached_df = pd.read_csv("data.csv", encoding="utf-8", sep=";", on_bad_lines="skip", low_memory=False)
        cached_df["Комнат"] = pd.to_numeric(cached_df["Комнат"], errors="coerce")
        cached_df["Площадь"] = pd.to_numeric(cached_df["Площадь"], errors="coerce")
        cached_df["Цена"] = pd.to_numeric(cached_df["Цена"], errors="coerce")
    return cached_df

# Стартовая команда
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Привет! Я бот, который анализирует данные из файла на Яндекс.Диске.")

# Обработка текстового запроса пользователя
async def process_user_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text

    try:
        # Загрузка данных
        df = load_file()

        # Извлечение критериев из запроса
        if "1 комнатная" in user_message and "43 квадратных" in user_message:
            filtered_df = df[(df["Комнат"] == 1) & (df["Площадь"].between(42, 44))]
        else:
            await update.message.reply_text("Не удалось понять ваш запрос. Уточните, пожалуйста.")
            return

        # Формируем текст для OpenAI
        if not filtered_df.empty:
            data_summary = filtered_df[["Жилой комплекс Раздел 1", "Площадь", "Цена"]].to_string(index=False)
            prompt = (
                f"Вот данные о квартирах:\n{data_summary}\n"
                f"На основе этих данных, ответьте на запрос пользователя: {user_message}"
            )
        else:
            prompt = f"На основе данных в файле не найдено подходящих квартир. Запрос: {user_message}"

        # Отправка запроса в OpenAI
        response = chat.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Вы помощник по анализу недвижимости."},
                {"role": "user", "content": prompt}
            ]
        )
        answer = response['choices'][0]['message']['content']
        await update.message.reply_text(answer)
    except Exception as e:
        logger.error(f"Ошибка обработки запроса: {e}")
        await update.message.reply_text("Произошла ошибка при обработке данных.")

# Загрузка данных с Яндекс.Диска
async def download_yandex_file():
    public_url = YANDEX_FILE_URL
    headers = {
        'Authorization': f'OAuth {YANDEX_DISK_TOKEN}'
    }
    try:
        # Запрос прямой ссылки
        async with ClientSession() as session:
            async with session.get(
                f"https://cloud-api.yandex.net/v1/disk/public/resources/download?public_key={public_url}",
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    direct_link = data.get("href")
                    if direct_link:
                        # Загрузка файла
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

# Вебхуковый маршрут
async def webhook_handler(request):
    update_data = await request.json()
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
        logger.error(f"Критическая ошибка: {e}")
