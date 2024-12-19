import os
import logging
from telegram import Update
from telegram.ext import (Updater, CommandHandler, MessageHandler, 
                          CallbackContext, ApplicationBuilder, filters)
from openai import ChatCompletion
from pydub import AudioSegment
import requests
from io import BytesIO

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
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

# Инициализация OpenAI
chat = ChatCompletion(api_key=OPENAI_API_KEY)

# Функция обработки команды /start
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Привет! Я бот, готов помочь. Отправьте текст или голосовое сообщение.")

# Функция обработки текстовых сообщений
async def handle_message(update: Update, context: CallbackContext):
    user_message = update.message.text
    logger.info(f"Получено сообщение: {user_message}")

    response = chat.create(
        model="gpt-4",
        messages=[{"role": "system", "content": PROMPT}, {"role": "user", "content": user_message}],
        temperature=0.7,
        max_tokens=1500
    )
    reply = response['choices'][0]['message']['content']
    await update.message.reply_text(reply)

# Функция обработки голосовых сообщений
async def handle_voice(update: Update, context: CallbackContext):
    file_id = update.message.voice.file_id
    file = await context.bot.get_file(file_id)
    file_bytes = requests.get(file.file_path).content

    audio = AudioSegment.from_file(BytesIO(file_bytes))
    audio.export("voice.ogg", format="ogg")

    response = chat.create(
        model="gpt-4",
        messages=[{"role": "system", "content": PROMPT}, {"role": "user", "content": "[Голосовое сообщение]"}],
        temperature=0.7,
        max_tokens=1500
    )
    reply = response['choices'][0]['message']['content']
    await update.message.reply_text(reply)

# Функция загрузки файла с Яндекс.Диска
async def load_yandex_file():
    headers = {"Authorization": f"OAuth {YANDEX_DISK_TOKEN}"}
    response = requests.get(YANDEX_FILE_URL, headers=headers)

    if response.status_code == 200:
        logger.info("Файл успешно загружен с Яндекс.Диска.")
        return response.content
    else:
        logger.error(f"Ошибка загрузки файла: {response.status_code}")
        return None

# Основная функция запуска бота
async def main():
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))

    logger.info(f"Бот запущен на порту {PORT}")
    await application.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
