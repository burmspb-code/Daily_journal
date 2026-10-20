"""Настройки Django для прогона автотестов.

Отдельный модуль нужен, чтобы тесты не зависели от локального PostgreSQL
и работали одинаково на машине разработчика и в CI: используется SQLite
в памяти, облегчённый хэшер паролей и синхронное выполнение Celery-задач.
"""

import os

# Значения по умолчанию задаются ДО импорта settings: в CI файла .env может
# не быть, а settings.py в неотладочном режиме требует явный SECRET_KEY.
os.environ.setdefault("SECRET_KEY", "test-only-secret-key")
os.environ.setdefault("DEBUG", "False")
os.environ.setdefault("ALLOWED_HOSTS", "testserver,localhost,127.0.0.1")

from .settings import *  # noqa: F403

DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# MD5 в разы быстрее PBKDF2: тесты не проверяют стойкость хэширования.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Celery выполняет задачи синхронно, без подключения к Redis.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
