import os
import logging
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext
from openai import ChatCompletion
import requests
import pandas as pd

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Переменные среды
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
YANDEX_DISK_TOKEN = os.getenv("YANDEX_DISK_TOKEN")
YANDEX_FILE_URL = os.getenv("YANDEX_FILE_URL")
PORT = int(os.getenv("PORT", "8080"))

# Настройки OpenAI GPT-4
PROMPT = "Вы являетесь ботом-помощником. Отвечайте на вопросы лаконично и понятно."
chat = ChatCompletion(api_key=OPENAI_API_KEY)

async def start(update: Update, context: CallbackContext):
    """Обработка команды /start."""
    await update.message.reply_text("Привет! Я бот-помощник. Чем могу помочь?")

async def handle_text(update: Update, context: CallbackContext):
    """Обработка текстовых сообщений."""
    user_input = update.message.text
    logger.info(f"Получено сообщение от пользователя: {user_input}")

    # Обработка текста через GPT-4
    try:
        response = chat.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": user_input},
            ],
            temperature=0.7,
        )
        bot_response = response["choices"][0]["message"]["content"]
        await update.message.reply_text(bot_response)
    except Exception as e:
        logger.error(f"Ошибка при обработке текста через GPT-4: {e}")
        await update.message.reply_text("Произошла ошибка при обработке запроса.")

async def analyze_file(update: Update, context: CallbackContext):
    """Загрузка и анализ файла с Yandex Disk."""
    try:
        headers = {"Authorization": f"OAuth {YANDEX_DISK_TOKEN}"}
        response = requests.get(YANDEX_FILE_URL, headers=headers)
        response.raise_for_status()

        with open("data.csv", "wb") as file:
            file.write(response.content)
        logger.info("Файл успешно загружен с Yandex Disk.")

        # Чтение файла
        df = pd.read_csv("data.csv", sep=";")
        await update.message.reply_text(f"Файл успешно загружен и содержит {len(df)} строк.")
    except Exception as e:
        logger.error(f"Ошибка при загрузке или анализе файла: {e}")
        await update.message.reply_text("Не удалось загрузить или проанализировать файл.")

async def main():
    """Основная функция для запуска бота."""
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Добавление обработчиков команд и сообщений
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("analyze", analyze_file))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Настройка вебхуков
    webhook_url = f"{WEBHOOK_URL}:{PORT}/bot{TELEGRAM_BOT_TOKEN}"
    await application.start_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=f"bot{TELEGRAM_BOT_TOKEN}",
        webhook_url=webhook_url,
    )

    logger.info(f"Бот запущен и слушает вебхуки на {webhook_url}")

    # Ожидание завершения приложения
    await application.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
