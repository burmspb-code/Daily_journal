import logging
from celery import shared_task
from daily.services import ReminderNotificationService

# Настраиваем системный логгер для вывода сообщений в консоль Docker
logger = logging.getLogger(__name__)


@shared_task
def check_daily_reminders() -> str:
    """Периодическая задача Celery для проверки напоминаний и контроля просрочки.

    Функция вызывается планировщиком Celery Beat каждую минуту. Она инициализирует
    сервисный класс ReminderNotificationService, запускает конвейер обработки
    базовой таблицы задач и выводит итоговую статистику выполнения в логи Docker.

    Returns:
        str: Текстовый отчёт со статистикой для фиксации в Celery Result Backend.
    """
    logger.info("=== [Celery Beat] Запуск минутного планировщика напоминаний ===")

    try:
        # Инициализируем сервисный класс бизнес-логики
        service = ReminderNotificationService()

        # Выполняем конвейер (поиск новых + проверка просрочки)
        result = service.execute()

        # Формируем красивый отчёт для логов Docker Compose
        report_message = (
            f"Обработка завершена успешно. "
            f"Отправлено: {result['sent']} шт. | "
            f"Просрочено: {result['overdue']} шт."
        )
        logger.info(f"=== [Celery Worker] {report_message} ===")
        return report_message

    except Exception as e:
        # Перехватываем любую ошибку, чтобы Celery Worker не упал,
        # логируем её и пробрасываем дальше для фиксации сбоя в системе
        logger.error(f"❌ Критическая ошибка в планировщике Celery: {str(e)}", exc_info=True)
        raise e