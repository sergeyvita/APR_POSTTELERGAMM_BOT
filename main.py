import logging
import os
from dotenv import load_dotenv
from telegram import Bot, Update, Voice
from telegram.ext import CommandHandler, MessageHandler, Filters, Updater, CallbackContext
import openai
import requests
import pandas as pd
from io import StringIO

# Загрузка переменных окружения
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
YANDEX_DISK_TOKEN = os.getenv("YANDEX_DISK_TOKEN")
YANDEX_FILE_URL = os.getenv("YANDEX_FILE_URL")  # Ссылка на файл

openai.api_key = OPENAI_API_KEY

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# PROMPT для GPT-4
PROMPT = """
You are a GPT-4 assistant integrated with a Telegram bot. Your job is to handle user queries effectively. Use the context provided in the uploaded files and conversations.
"""

# Загрузка файла с Яндекс.Диска
def download_file_from_yandex_disk(file_url: str, token: str) -> pd.DataFrame:
    headers = {"Authorization": f"OAuth {token}"}
    response = requests.get(file_url, headers=headers)
    if response.status_code == 200:
        logger.info("Файл успешно загружен с Яндекс.Диска")
        content = StringIO(response.text)
        return pd.read_csv(content, sep=";")
    else:
        logger.error(f"Ошибка загрузки файла: {response.status_code} - {response.text}")
        raise Exception("Не удалось загрузить файл с Яндекс.Диска.")

# Обработчик команды /start
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("Добро пожаловать! Отправьте мне запрос или голосовое сообщение.")

# Обработка текстовых сообщений
def handle_message(update: Update, context: CallbackContext) -> None:
    user_message = update.message.text
    logger.info(f"Получено сообщение: {user_message}")
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.7,
            max_tokens=500,
        )
        bot_response = response["choices"][0]["message"]["content"]
        update.message.reply_text(bot_response)
    except Exception as e:
        logger.error(f"Ошибка обработки запроса OpenAI: {e}")
        update.message.reply_text("Произошла ошибка при обработке вашего запроса.")

# Обработка голосовых сообщений
def handle_voice_message(update: Update, context: CallbackContext) -> None:
    voice: Voice = update.message.voice
    file = voice.get_file()
    logger.info("Голосовое сообщение получено и обрабатывается.")
    try:
        # Скачивание голосового файла
        file_path = file.download()
        # Преобразование голосового сообщения в текст
        # Для примера, здесь стоит интеграция с библиотекой распознавания речи
        text = "Тестовое распознавание текста из голосового сообщения."
        logger.info(f"Распознанный текст: {text}")

        # Отправка распознанного текста в OpenAI
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0.7,
            max_tokens=500,
        )
        bot_response = response["choices"][0]["message"]["content"]
        update.message.reply_text(bot_response)
    except Exception as e:
        logger.error(f"Ошибка обработки голосового сообщения: {e}")
        update.message.reply_text("Ошибка обработки голосового сообщения.")

# Загрузка файла данных по запросу
def handle_file_request(update: Update, context: CallbackContext) -> None:
    try:
        data = download_file_from_yandex_disk(YANDEX_FILE_URL, YANDEX_DISK_TOKEN)
        logger.info("Файл успешно загружен и обработан.")
        update.message.reply_text("Файл загружен. Что вы хотите с ним сделать?")
    except Exception as e:
        logger.error(f"Ошибка загрузки файла: {e}")
        update.message.reply_text("Ошибка загрузки файла.")

def main() -> None:
    # Настройка Telegram-бота
    updater = Updater(token=TELEGRAM_TOKEN)
    dispatcher = updater.dispatcher

    # Обработчики
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dispatcher.add_handler(MessageHandler(Filters.voice, handle_voice_message))
    dispatcher.add_handler(CommandHandler("file", handle_file_request))

    # Запуск бота
    port = int(os.environ.get("PORT", 8080))
    updater.start_polling()
    logger.info(f"Бот запущен на порту {port}")
    updater.idle()

if __name__ == "__main__":
    main()
