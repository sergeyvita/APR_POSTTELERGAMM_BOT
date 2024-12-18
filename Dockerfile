FROM python:3.11-slim

WORKDIR /app

# Установить ffmpeg для работы с pydub
RUN apt-get update && apt-get install -y ffmpeg

# Установить зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --upgrade pip

# Скопировать остальные файлы
COPY . .

# Установить порт
ENV PORT=8080

# Запуск приложения
CMD ["python", "main.py"]
