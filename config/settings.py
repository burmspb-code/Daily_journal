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

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Загружаем переменные из файла .env, который лежит в корне проекта.
# override=False означает, что реальные переменные окружения (docker-compose,
# systemd, CI/CD) имеют приоритет над .env. Иначе, например, DEBUG=False,
# переданный при запуске, был бы молча перекрыт значением из .env.
load_dotenv(override=False)

# SECURITY WARNING: don't run with debug turned on in production!
# Явное включение обязательно: любое значение, кроме перечисленных,
# трактуется как False. Так случайно забытый DEBUG в .env не откроет
# отладочные страницы с трассировками стека на продакшене.
DEBUG = os.getenv("DEBUG", "False").strip().lower() in ("1", "true", "yes", "on")

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("SECRET_KEY")

if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured(
            "SECRET_KEY не задан. Добавьте его в .env (см. .env.sample). "
            "Запуск в продакшене с отладочным ключом запрещён."
        )
    # Резервный ключ допустим только для локальной отладки.
    SECRET_KEY = "django-insecure-dev-only-fallback-key"

# Загружаем токен для Телеграм
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Список хостов задаётся через .env, например:
# ALLOWED_HOSTS=localhost,127.0.0.1,example.com
# Пустое значение трактуется как «не задано» — подставляются локальные хосты,
# чтобы случайно не заблокировать весь сайт.
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "").split(",")
    if host.strip()
] or ["localhost", "127.0.0.1", "[::1]"]

# Домены, которым доверяется CSRF при работе через HTTPS.
# Указываются СО СХЕМОЙ, например: https://example.com,https://www.example.com
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

# ======================== НАСТРОЙКИ HTTPS ==========================================
# Nginx передаёт X-Forwarded-Proto, чтобы Django считал запрос защищённым.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Все HTTP-запросы перенаправляются на HTTPS. Nginx тоже делает редирект,
# это дополнительная защита для прямых запросов к Gunicorn.
SECURE_SSL_REDIRECT = True

# Cookie сессии и CSRF передаются только по HTTPS.
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# HSTS для IP-адреса браузерами не применяется. Включим SECURE_HSTS_SECONDS
# при переходе на домен, чтобы не сломать доступ по IP.

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',

    "drf_spectacular_sidecar",
    "drf_spectacular",

    "django_celery_beat",

    "daily",
    # Явно указываем конфигурационный класс для корректного запуска ready()
    "users.apps.UsersConfig",
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
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST", "host.docker.internal"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}

# Password validation
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
LANGUAGE_CODE = "ru-ru"

TIME_ZONE = "Europe/Moscow"

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]
# КРИТИЧЕСКИ ВАЖНО ДЛЯ ПРОДАКШЕНА:
# Папка, КУДА Django СБЕРЕТ всю статику проекта для веб-сервера Nginx
STATIC_ROOT = BASE_DIR / "staticfiles"

# Указываем Django использовать кастомную модель вместо встроенной
AUTH_USER_MODEL = "users.CustomUser"

# Настройка таймаутов для исходящей почты
EMAIL_TIMEOUT = 15

# Почта переведена на SMTP, MAIL_FUNCTION_URL больше не используется
# MAIL_FUNCTION_URL = ...
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# Указываем сервера Яндекса
EMAIL_HOST = "smtp.yandex.ru"
EMAIL_PORT = 465
EMAIL_USE_SSL = True  # Яндекс строго требует шифрование SSL

# Привязываем авторизацию к переменным из вашего .env
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")         # Ваш логин Яндекса (например, info@yoursite.ru)
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD") # Пароль приложения!
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

# Email для получения уведомлений для администрирования ресурса
EMAIL_ADMIN_NOTIFICATION = os.getenv("EMAIL_ADMIN_NOTIFICATION")


# ============= Настройки перенаправления для системы аутентификации ============

LOGIN_REDIRECT_URL = "daily:task_list"  # Куда направлять после успешного входа
LOGIN_URL = "users:login"  # Куда отправлять неавторизованного пользователя
LOGOUT_REDIRECT_URL = "daily:task_list"  # Куда направлять после успешного выхода

# Регион по умолчанию для валидации номеров (ISO 3166-1 alpha-2)
PHONENUMBER_DEFAULT_REGION = "RU"

# Время жизни токена для восстановления пароля и активации аккаунта (24 часа)
PASSWORD_RESET_TIMEOUT = 24 * 60 * 60  # 86400 секунд


# ==================== НАСТРОЙКИ CELERY И REDIS ================================

# Приоритет отдается переменной из окружения Docker.
# На случай локального запуска без Docker (редкий кейс) оставлен безопасный дефолт на localhost.
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL") or "redis://127.0.0.1:6379/0"
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND") or CELERY_BROKER_URL

# Часовой пояс для планировщика Celery (должен совпадать с Django)
CELERY_TIMEZONE = TIME_ZONE

# Включаем отслеживание запуска задач
CELERY_TASK_TRACK_STARTED = True

# Тайм-аут для хранения результатов задач в Redis (в секундах - 1 день)
CELERY_RESULT_EXPIRES = 86400

# Указываем Celery Beat читать расписание из базы данных через Django ORM
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# ======================== НАСТРОЙКИ REST FRAMEWORK =================================

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


# =========================== НАСТРОЙКИ JWT ТОКЕНА ===================================

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=5),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
}


# ======================= НАСТРОЙКИ АВТОДУКОМЕНТАЦИИ =================================

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
