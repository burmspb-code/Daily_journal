from celery import shared_task
from django.utils import timezone
from .models import Task


@shared_task
def check_daily_reminders():
    """
    Фоновая задача Celery Beat. Проверяет наступившие дедлайны
    в PostgreSQL и готовит отправку Web Push уведомлений.
    """
    now = timezone.now()

    # Ищем задачи по вашим реальным полям:
    # 1. Время напоминания пришло или уже прошло (reminder_at__lte=now)
    # 2. Флаг отправки еще не стоит (is_notified=False)
    due_tasks = Task.objects.filter(
        reminder_at__lte=now,
        is_notified=False
    )

    # Быстрая проверка через exists() без загрузки данных в память
    if not due_tasks.exists():
        return f"[{now}] Нет активных задач для отправки пушей."

    count = 0
    for task in due_tasks:
        # Пока у нас нет фронтенда пушей, выводим информацию в лог Celery
        print(f"!!! НАПОМИНАНИЕ !!! Задача №{task.id}: {task.title} | Комментарий: {task.comment}")

        # Меняем флаг, чтобы зафиксировать отправку в базе данных
        task.is_notified = True
        task.save()
        count += 1

    return f"[{now}] Успешно обработано напоминаний в PostgreSQL: {count}"
