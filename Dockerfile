FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

# Создание рабочей директории
WORKDIR /app

# Создание и активация виртуальной среды
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Копирование файлов
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Копирование всех исходников
COPY . .

# Установка порта
ENV PORT=8080

# Запуск приложения
CMD ["python", "main.py"]
