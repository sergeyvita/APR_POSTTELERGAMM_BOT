import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from aiohttp import web
import asyncio
import pandas as pd
from openai import ChatCompletion

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
            messages=[{"role": "system", "content": "Вы бот, отвечающий на вопросы лаконично и четко."},
                      {"role": "user", "content": user_message}]
        )
        answer = response['choices'][0]['message']['content']
        await update.message.reply_text(answer)
    except Exception as e:
        logger.error(f"Ошибка обработки сообщения: {e}")
        await update.message.reply_text("Произошла ошибка при обработке вашего сообщения.")

# Вебхуковый маршрут
async def webhook_handler(request):
    update_data = await request.json()
    update = Update.de_json(update_data, bot)
    await application.update_queue.put(update)
    return web.Response(text="OK")

# Загрузка данных с Яндекс.Диска
async def download_yandex_file():
    headers = {
        'Authorization': f'OAuth {YANDEX_DISK_TOKEN}'
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(YANDEX_FILE_URL, headers=headers) as response:
            if response.status == 200:
                content = await response.text()
                with open("data.csv", "w", encoding="utf-8") as f:
                    f.write(content)
                logger.info("Файл успешно загружен с Яндекс.Диска.")
            else:
                logger.error(f"Ошибка загрузки файла с Яндекс.Диска: {response.status}")

# Основной процесс
async def main():
    global application

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Обработчики
    application.add_handler(CommandHandler("start", start))
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