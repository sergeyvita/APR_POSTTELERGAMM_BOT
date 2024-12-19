# Использование Python 3.11 в качестве базового образа
FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Создание рабочей директории
WORKDIR /app

# Создание и активация виртуальной среды
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Копирование файла зависимостей
COPY requirements.txt .

# Установка Python-зависимостей
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Копирование всех исходников проекта
COPY . .

# Установка переменной среды для порта
ENV PORT=8080

# Указание команды для запуска приложения
CMD ["python", "main.py"]
