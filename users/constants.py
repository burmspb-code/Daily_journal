# Словари с лимитами для каждого тарифного плана
TARIFF_LIMITS = {
    "BASE": {
        "MAX_TASKS": 50,
        "MAX_BOOKMARKS": 5,
    },
    "STANDARD": {
        "MAX_TASKS": 150,
        "MAX_BOOKMARKS": 10,
    },
    "PREMIUM": {
        "MAX_TASKS": 250,
        "MAX_BOOKMARKS": 20,
    },
}

# Минимальный интервал между повторными отправками ссылки активации.
# Защищает почтовый сервис от спама и не даёт злоупотреблять эндпоинтом.
ACTIVATION_RESEND_COOLDOWN_SECONDS = 60

# Максимум попыток отправки ссылки активации на один аккаунт за сутки.
ACTIVATION_RESEND_DAILY_LIMIT = 5
