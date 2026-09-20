import logging
import os

import requests
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from daily.models import NotificationAttempt
from users.exceptions import EmailActivationError

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_email_notification(self, attempt_id: int, to_email: str,
                            task_name: str, deadline: str) -> None:
    """Асинхронная задача отправки email-уведомления через Cloud Function.

    Загружает запись NotificationAttempt по ID, выполняет HTTP-запрос к
    облачной функции отправки писем, фиксирует результат в БД.
    При сетевой ошибке — повторяет попытку с задержкой 60 секунд.

    Args:
        attempt_id: ID записи NotificationAttempt (создаётся оркестратором).
        to_email: Email получателя.
        task_name: Название задачи для текста письма.
        deadline: Дедлайн задачи (строка).
    """
    try:
        attempt = NotificationAttempt.objects.get(id=attempt_id)
    except NotificationAttempt.DoesNotExist:
        logger.error(f"❌ NotificationAttempt ID {attempt_id} не существует")
        return

    mail_url = getattr(settings, "MAIL_FUNCTION_URL", None)

    if not mail_url:
        attempt.status = NotificationAttempt.STATUS_FAILED
        attempt.error_message = "MAIL_FUNCTION_URL не настроен в settings.py"
        attempt.save(update_fields=["status", "error_message"])
        logger.error("❌ MAIL_FUNCTION_URL не настроен в settings.py")
        return

    payload = {
        "to_email": to_email,
        "email_type": "reminder",
        "task_name": task_name,
        "deadline": deadline,
    }

    logger.info(f"📬 Отправляем email: {task_name} → {to_email}")

    try:
        attempt.attempts += 1
        attempt.save(update_fields=["attempts"])

        response = requests.post(mail_url, json=payload, timeout=15)

        if response.status_code != 200:
            raise EmailActivationError(
                f"Сервис почты вернул HTTP {response.status_code}: {response.text}"
            )

        attempt.status = NotificationAttempt.STATUS_SENT
        attempt.sent_at = timezone.now()
        attempt.error_message = None
        attempt.save(update_fields=["status", "sent_at", "error_message"])

        logger.info(f"✅ Email отправлен: {task_name} → {to_email}")

    except (requests.exceptions.Timeout,
            requests.exceptions.ConnectionError) as e:
        attempt.status = NotificationAttempt.STATUS_FAILED
        attempt.error_message = str(e)
        attempt.save(update_fields=["status", "error_message"])

        logger.warning(
            f"⚠️ Сетевая ошибка email (попытка {attempt.attempts}/3): {e}"
        )
        raise self.retry(exc=e) from e

    except EmailActivationError as e:
        attempt.status = NotificationAttempt.STATUS_FAILED
        attempt.error_message = str(e)
        attempt.save(update_fields=["status", "error_message"])

        logger.warning(
            f"⚠️ Сервис почты вернул ошибку (попытка {attempt.attempts}/3): {e}"
        )
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e) from e

    except Exception as e:
        attempt.status = NotificationAttempt.STATUS_FAILED
        attempt.error_message = str(e)
        attempt.save(update_fields=["status", "error_message"])

        logger.error(f"❌ Фатальная ошибка отправки email: {e}", exc_info=True)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_telegram_notification(self, attempt_id: int, chat_id: str,
                              task_name: str, deadline: str) -> None:
    """Асинхронная задача отправки Telegram-уведомления через Bot API.

    Загружает запись NotificationAttempt по ID, выполняет запрос к
    Telegram Bot API, фиксирует результат в БД.
    При сетевой ошибке — повторяет попытку с задержкой 60 секунд.

    Args:
        attempt_id: ID записи NotificationAttempt (создаётся оркестратором).
        chat_id: ID чата получателя в Telegram.
        deadline: Дедлайн задачи (строка).
    """
    try:
        attempt = NotificationAttempt.objects.get(id=attempt_id)
    except NotificationAttempt.DoesNotExist:
        logger.error(f"❌ NotificationAttempt ID {attempt_id} не существует")
        return

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        attempt.status = NotificationAttempt.STATUS_FAILED
        attempt.error_message = "TELEGRAM_BOT_TOKEN не задан в .env"
        attempt.save(update_fields=["status", "error_message"])
        logger.error("❌ TELEGRAM_BOT_TOKEN не задан в .env")
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    message_text = (
        f"⏰ *Время выполнить задачу!*\n\n"
        f"💪 *Задача:* {task_name}\n"
        f"⏳ *Дедлайн:* {deadline}"
    )

    payload = {
        "chat_id": chat_id,
        "text": message_text,
        "parse_mode": "Markdown",
    }

    logger.info(f"📬 Отправляем Telegram: {task_name} → {chat_id}")

    try:
        attempt.attempts += 1
        attempt.save(update_fields=["attempts"])

        response = requests.post(url, json=payload, timeout=15)

        if response.status_code != 200:
            raise EmailActivationError(
                f"Telegram API вернул HTTP {response.status_code}: {response.text}"
            )

        attempt.status = NotificationAttempt.STATUS_SENT
        attempt.sent_at = timezone.now()
        attempt.error_message = None
        attempt.save(update_fields=["status", "sent_at", "error_message"])

        logger.info(f"✅ Telegram отправлен: {task_name} → {chat_id}")

    except (requests.exceptions.Timeout,
            requests.exceptions.ConnectionError) as e:
        attempt.status = NotificationAttempt.STATUS_FAILED
        attempt.error_message = str(e)
        attempt.save(update_fields=["status", "error_message"])

        logger.warning(
            f"⚠️ Сетевая ошибка Telegram (попытка {attempt.attempts}/3): {e}"
        )
        raise self.retry(exc=e) from e

    except EmailActivationError as e:
        attempt.status = NotificationAttempt.STATUS_FAILED
        attempt.error_message = str(e)
        attempt.save(update_fields=["status", "error_message"])

        logger.warning(
            f"⚠️ Telegram API вернул ошибку (попытка {attempt.attempts}/3): {e}"
        )
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e) from e

    except Exception as e:
        attempt.status = NotificationAttempt.STATUS_FAILED
        attempt.error_message = str(e)
        attempt.save(update_fields=["status", "error_message"])

        logger.error(f"❌ Фатальная ошибка отправки в Telegram: {e}", exc_info=True)


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
        from daily.services import ReminderNotificationService

        service = ReminderNotificationService()
        result = service.execute()

        report_message = (
            f"Обработка завершена успешно. "
            f"Отправлено: {result['sent']} шт. | "
            f"Просрочено: {result['overdue']} шт."
        )
        logger.info(f"=== [Celery Worker] {report_message} ===")
        return report_message

    except Exception as e:
        logger.error(
            f"❌ Критическая ошибка в планировщике Celery: {e!s}",
            exc_info=True,
        )
        raise
