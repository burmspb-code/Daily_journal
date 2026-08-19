"""
Глобальные настройки и конфигурация для Django-проекта Daily Journal.

Этот модуль содержит все системные параметры проекта: настройки базы данных,
подключение приложений, конфигурацию безопасности, сессий и SMTP-серверов.
Для проверки корректности настроек перед деплоем используйте:
`python manage.py check --deploy`
"""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Загружаем переменные из файла .env, который лежит в корне проекта
load_dotenv(override=True)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-fallback-key")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DEBUG", "True") == "True"

ALLOWED_HOSTS = ["*"]

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "drf_spectacular_sidecar",  # Отвечает за локальные шаблоны и статику UI
    "drf_spectacular",
    "daily",  # Основно пользовательское приложение
    "users",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}

# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = "ru-ru"

TIME_ZONE = "Europe/Moscow"

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = "static/"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# Указываем Django использовать кастомную модель вместо встроенной
AUTH_USER_MODEL = "users.CustomUser"

# Временно комментируем SMTP и включаем вывод в консоль:
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
# EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# Конфигурация SMTP Яндекс
EMAIL_HOST = "smtp.yandex.ru"
EMAIL_PORT = 465  # Яндекс использует порт 465 для SSL
EMAIL_USE_SSL = True  # Использование SSL вместо TLS (для Яндекса это надежнее)
EMAIL_USE_TLS = False  # Отключаем TLS

# Логин и пароль приложения почты
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")

# 16-значный пароль приложения почты
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")

# Email отправителя по умолчанию
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL")

# Email для получения уведомлений о просмотрах
EMAIL_ADMIN_NOTIFICATION = os.getenv("EMAIL_ADMIN_NOTIFICATION")

# Настройки перенаправления для системы аутентификации
LOGIN_REDIRECT_URL = "daily:task_list"  # Куда направлять после успешного входа
LOGIN_URL = "users:login"  # Куда отправлять неавторизованного пользователя
LOGOUT_REDIRECT_URL = "daily:task_list"  # Куда направлять после успешного выхода

# Регион по умолчанию для валидации номеров (ISO 3166-1 alpha-2)
PHONENUMBER_DEFAULT_REGION = "RU"

# Время жизни токена для восстановления пароля и активации аккаунта (24 часа)
PASSWORD_RESET_TIMEOUT = 24 * 60 * 60  # 86400 секунд

# ==============================================================================
# НАСТРОЙКИ CELERY И REDIS
# ==============================================================================

# URL-адрес для подключения к Redis (брокер сообщений)
CELERY_BROKER_URL = "redis://127.0.0.1:6379/0"

# URL-адрес для хранения результатов выполнения задач в Redis
CELERY_RESULT_BACKEND = "redis://127.0.0.1:6379/0"

# Часовой пояс для планировщика Celery (должен совпадать с Django)
CELERY_TIMEZONE = TIME_ZONE  # Берём значение из переменной TIME_ZONE вашего проекта

# Включаем отслеживание запуска задач
CELERY_TASK_TRACK_STARTED = True

# Тайм-аут для хранения результатов задач в Redis (в секундандах - 1 день)
CELERY_RESULT_EXPIRES = 86400

# ==============================================================================

REST_FRAMEWORK = {
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=5),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Daily_Journal API",
    "DESCRIPTION": "Автодокументация REST API V1 для мобильных приложений и фронтенда проекта Daily Journal.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Указываем использовать локальные файлы из sidecar вместо внешних CDN:
    "SWAGGER_UI_DIST": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
    # Включаем поддержку авторизации по кнопке "Authorize" в Swagger
    "SECURITY": [
        {
            "jwtAuth": [],
        }
    ],
    "SECURITY_SCHEMES": {
        "jwtAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
            "description": "Вставьте JWT токен в формате: Bearer <ваш_токен>",
        },
    },
}
