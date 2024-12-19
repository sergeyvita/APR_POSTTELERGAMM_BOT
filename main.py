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

# Стартовая команда
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Привет! Я бот, который анализирует данные из файла на Яндекс.Диске.")

# Обработка текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = update.message.text
    logger.info(f"Получено сообщение: {user_message}")

    try:
        response = chat.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Вы бот, отвечающий на вопросы лаконично и четко."},
                {"role": "user", "content": user_message}
            ]
        )
        answer = response['choices'][0]['message']['content']
        await update.message.reply_text(answer)
    except Exception as e:
        logger.error(f"Ошибка обработки сообщения: {e}")
        await update.message.reply_text("Произошла ошибка при обработке вашего сообщения.")

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

# Обработка файла
async def process_file():
    try:
        # Чтение файла
        df = pd.read_csv("data.csv", encoding="utf-8")
        logger.info(f"Файл успешно обработан. Найдено строк: {len(df)}")
        # Пример анализа данных
        summary = df.describe(include='all')  # Статистика по данным
        return summary.to_string()
    except Exception as e:
        logger.error(f"Ошибка обработки файла: {e}")
        return "Произошла ошибка при обработке файла."

# Команда для анализа данных
async def analyze_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await process_file()
    await update.message.reply_text(f"Анализ файла завершен:\n{result}")

# Вебхуковый маршрут
async def webhook_handler(request):
    update_data = await request.json()
    update = Update.de_json(update_data, application.bot)
    await application.update_queue.put(update)
    return web.Response(text="OK")

# Основной процесс
async def main():
    global application

    # Инициализация приложения
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("analyze", analyze_data))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Настройка вебхука
    app = web.Application()
    app.router.add_post("/webhook", webhook_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    logger.info(f"Запуск вебхука на порту {PORT}")

    # Загрузка файла с Яндекс.Диска
    await download_yandex_file()

    # Запуск бота
    await application.start()
    await application.updater.start_polling()
    await application.idle()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
