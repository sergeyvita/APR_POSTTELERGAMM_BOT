import os
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет сообщение при вводе команды /start."""
    await update.message.reply_text("Привет! Я ваш бот-помощник. Чем могу помочь?")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает текстовые сообщения."""
    user_message = update.message.text
    logger.info(f"Получено сообщение от пользователя: {user_message}")

    try:
        response = chat.create(
            model="gpt-4",
            messages=[{"role": "system", "content": PROMPT}, {"role": "user", "content": user_message}],
            max_tokens=100,
            temperature=0.7,
        )
        reply = response.choices[0].message["content"]
        await update.message.reply_text(reply)
    except Exception as e:
        logger.error(f"Ошибка обработки сообщения: {e}")
        await update.message.reply_text("Извините, произошла ошибка при обработке вашего сообщения.")

async def fetch_file_from_yandex_disk() -> pd.DataFrame:
    """Загружает файл с Яндекс.Диска и возвращает DataFrame."""
    headers = {"Authorization": f"OAuth {YANDEX_DISK_TOKEN}"}
    response = requests.get(YANDEX_FILE_URL, headers=headers)

    if response.status_code == 200:
        with open("data.csv", "wb") as file:
            file.write(response.content)
        logger.info("Файл успешно загружен с Яндекс.Диска.")
        return pd.read_csv("data.csv", sep=";", encoding="utf-8")
    else:
        logger.error(f"Ошибка загрузки файла: {response.status_code}, {response.text}")
        raise Exception("Не удалось загрузить файл с Яндекс.Диска.")

async def analyze_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Анализирует файл с Яндекс.Диска и отправляет результат пользователю."""
    try:
        df = await fetch_file_from_yandex_disk()
        summary = df.describe().to_string()
        await update.message.reply_text(f"Анализ данных:\n{summary}")
    except Exception as e:
        logger.error(f"Ошибка анализа файла: {e}")
        await update.message.reply_text("Не удалось выполнить анализ файла.")

async def main() -> None:
    """Основная функция для запуска бота."""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("analyze", analyze_file))

    # Обработчики текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запуск вебхука
    logger.info(f"Запуск вебхука на порту {PORT}")
    await application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=f"/{TELEGRAM_BOT_TOKEN}",
        webhook_url=f"{WEBHOOK_URL}/{TELEGRAM_BOT_TOKEN}",
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
