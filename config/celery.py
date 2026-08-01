import os

from celery import Celery
from celery.schedules import crontab

# 1. Указываем Django, что настройки лежат в config.settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# 2. Создаем экземпляр Celery с именем config
app = Celery('config')

# 3. Читаем настройки Celery из settings.py с префиксом CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# 4. Автоматически ищем файлы tasks.py в приложениях (например, в daily и users)
app.autodiscover_tasks()

# Настраиваем расписание для автономных задач
app.conf.beat_schedule = {
    'check-reminders-every-minute': {
        'task': 'daily.tasks.check_daily_reminders',  # Путь к нашей функции
        'schedule': crontab(minute='*'),  # Выполнять каждую минуту
    },
}
