# ==========================================
# ШАГ 1: ВЫБОР БАЗОВОГО ОБРАЗА
# ==========================================
FROM python:3.14-slim

# ==========================================
# ШАГ 2: УСТАНОВКА СИСТЕМНЫХ ЗАВИСИМОСТЕЙ
# ==========================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ==========================================
# ШАГ 3: НАСТРОЙКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ
# ==========================================
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=2.2.1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1 \
    PATH="/opt/poetry/bin:$PATH"

# ==========================================
# ШАГ 4: УСТАНОВКА POETRY
# ==========================================
RUN curl -sSL https://install.python-poetry.org | python3 - --version $POETRY_VERSION \
    && test -x "$POETRY_HOME/bin/poetry"

# ==========================================
# ШАГ 5: ПОДГОТОВКА СЛОЯ ЗАВИСИМОСТЕЙ
# ==========================================
WORKDIR /app
COPY pyproject.toml poetry.lock* /app/
RUN poetry install --no-interaction --no-ansi --with dev

# ==========================================
# ШАГ 6: КОПИРОВАНИЕ КОДА И НАСТРОЙКА ПОЛЬЗОВАТЕЛЯ
# ==========================================
COPY . /app/

# Создаем системного пользователя с домашней директорией
# Это решит ошибку доступа к /nonexistent
RUN addgroup --system appgroup && \
    adduser --system --group --home /home/appuser appuser

# Создаем папки для статики и медиа до смены пользователя
RUN mkdir -p /app/staticfiles /app/mediafiles

# Назначаем владельцев
RUN chown -R appuser:appgroup /app /home/appuser /opt/poetry

# Открываем порт
EXPOSE 8000

# Переключаемся на пользователя
USER appuser