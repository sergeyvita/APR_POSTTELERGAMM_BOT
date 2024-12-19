import os
import asyncio
from aiohttp import web
from dotenv import load_dotenv
import openai
import aiohttp
import pandas as pd
from pydub import AudioSegment
from asyncio import Event
import logging

# Настройка логирования
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Загрузка переменных окружения из .env файла
load_dotenv()

# Переменные окружения
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

# Установка API-ключа OpenAI
openai.api_key = OPENAI_API_KEY

# PROMPT для OpenAI
PROMPT = (
    "Этот GPT выступает в роли профессионального создателя контента для Телеграм-канала Ассоциации застройщиков. "
    "Он создает максимально продающие посты на темы недвижимости, строительства, законодательства, инвестиций и связанных отраслей. "
    "Контент ориентирован на привлечение внимания, удержание аудитории и стимулирование действий (например, обращения за консультацией или покупки). "
    "Посты красиво оформляются с использованием эмодзи в стиле \"энергичный и современный\", добавляя динамичности и вовлеченности. "
    "Например: 🏠 для темы недвижимости, 🚀 для роста, 📢 для новостей. "
    "Все посты структурированные и содержат четкие призывы к действию, информацию о контактах и гиперссылки. "
    "В конце каждого поста перед хэштегами указывается название компании \"Ассоциация застройщиков\", номер телефона 8-800-550-23-93. "
    "В конце хэштеги на тему поста."
)

# Создание приложения Aiohttp
app = web.Application()

async def handle_home(request):
    return web.Response(text="Сервис работает!")

async def handle_webhook(request):
    try:
        data = await request.json()
        logger.info(f"Получены данные от Telegram: {data}")

        if "message" in data:
            chat_id = data["message"]["chat"]["id"]

            if "text" in data["message"]:
                user_message = data["message"]["text"]

                if user_message.lower() == "/analyze_file":
                    response = await analyze_file()
                    await send_message(chat_id, response)
                elif user_message.lower().startswith("/find_price"):
                    query = user_message.replace("/find_price", "").strip()
                    response = await analyze_file_with_query(query)
                    await send_message(chat_id, response)
                else:
                    response = await generate_openai_response(user_message)
                    await send_message(chat_id, response)

        return web.json_response({"status": "ok"})
    except Exception as e:
        logger.error(f"Ошибка обработки вебхука: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)

async def analyze_file():
    save_path = "downloaded_file.xlsx"
    try:
        # Ссылка на файл на Яндекс.Диске
        file_url = "https://disk.yandex.ru/i/5t9-Cg1G3Q76sw"

        # Преобразование ссылки в прямую
        direct_url = f"{file_url}?export=download"
        logger.debug(f"Скачивание файла по URL: {direct_url}")

        # Скачивание файла
        async with aiohttp.ClientSession() as session:
            async with session.get(direct_url) as response:
                response.raise_for_status()
                with open(save_path, "wb") as f:
                    f.write(await response.read())
        logger.info("Файл успешно скачан.")

        # Чтение и анализ данных
        df = pd.read_excel(save_path)
        result = df.describe()  # Генерация простой статистики
        logger.info("Анализ файла завершен.")

        return f"Файл успешно проанализирован:\n{result.to_string()}"
    except Exception as e:
        logger.error(f"Ошибка анализа файла: {e}", exc_info=True)
        return "Не удалось обработать файл."
    finally:
        if os.path.exists(save_path):
            os.remove(save_path)
            logger.debug("Временный файл удален.")

async def analyze_file_with_query(query):
    save_path = "downloaded_file.xlsx"
    try:
        # Ссылка на файл на Яндекс.Диске
        file_url = "https://disk.yandex.ru/i/e-AmdWzRu43L3g"

        # Преобразование ссылки в прямую
        direct_url = f"{file_url}?export=download"
        logger.debug(f"Скачивание файла по URL: {direct_url}")

        # Скачивание файла
        async with aiohttp.ClientSession() as session:
            async with session.get(direct_url) as response:
                response.raise_for_status()
                with open(save_path, "wb") as f:
                    f.write(await response.read())
        logger.info("Файл успешно скачан.")

        # Чтение данных
        df = pd.read_excel(save_path)

        # Проверка на наличие колонки "Цена"
        if "Цена" not in df.columns:
            logger.warning("Колонка 'Цена' не найдена в файле.")
            return "Колонка 'Цена' не найдена в файле."

        # Фильтрация данных по запросу
        try:
            condition = eval(f"df['Цена'] {query}")  # Пример: "< 5000000"
            filtered_data = df[condition]
            if filtered_data.empty:
                logger.info("Не найдено записей, соответствующих запросу.")
                return "Не найдено записей, соответствующих запросу."
            return f"Найдены цены:\n{filtered_data['Цена'].to_list()}"
        except Exception as e:
            logger.error(f"Ошибка при обработке условия: {e}", exc_info=True)
            return f"Ошибка при обработке условия: {e}"
    except Exception as e:
        logger.error(f"Ошибка анализа файла: {e}", exc_info=True)
        return "Не удалось обработать файл."
    finally:
        if os.path.exists(save_path):
            os.remove(save_path)
            logger.debug("Временный файл удален.")

async def send_message(chat_id, text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                response.raise_for_status()
                result = await response.json()
                logger.info(f"Ответ Telegram API: {result}")
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {e}", exc_info=True)

async def generate_openai_response(user_message):
    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-4",
            messages=[
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=1,
            max_tokens=1500,
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        logger.error(f"Ошибка при обращении к OpenAI: {e}", exc_info=True)
        return "Произошла ошибка при генерации ответа."

# Роуты приложения
app.router.add_get('/', handle_home)
app.router.add_post('/webhook', handle_webhook)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    logger.info(f"Запуск приложения на порту {port}")
    web.run_app(app, host="0.0.0.0", port=port)