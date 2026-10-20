import html
import logging

import requests
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from daily.exceptions import RETRYABLE_STATUS_CODES, NotificationError
from daily.models import NotificationAttempt

logger = logging.getLogger(__name__)

# Единый таймаут для всех исходящих HTTP-запросов к внешним сервисам
REQUEST_TIMEOUT = 15


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_email_notification(self, attempt_id: int, to_email: str,
                            task_name: str, deadline: str) -> None:
    """Асинхронная задача отправки email-уведомления через Cloud Function.

    Загружает запись NotificationAttempt по ID, выполняет HTTP-запрос к
    облачной функции отправки писем, фиксирует результат в БД.

    Повторяет попытку с экспоненциальной задержкой только при временных сбоях
    (сетевые ошибки, 429 и 5xx). Остальные коды считаются терминальными:
    повтор не изменит результат, поэтому попытка фиксируется как failed.

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

        response = requests.post(mail_url, json=payload, timeout=REQUEST_TIMEOUT)

        if response.status_code != 200:
            raise NotificationError(
                message=f"Сервис почты вернул HTTP {response.status_code}: {response.text}",
                details={
                    "status_code": response.status_code,
                    "response_text": response.text,
                },
            )

    except (requests.exceptions.Timeout,
            requests.exceptions.ConnectionError) as e:
        attempt.status = NotificationAttempt.STATUS_FAILED
        attempt.error_message = f"Сетевая ошибка: {e}"
        attempt.save(update_fields=["status", "error_message"])

        logger.warning(
            f"⚠️ Сетевая ошибка email (попытка {attempt.attempts}/3): {e}"
        )
        countdown = self.default_retry_delay * (2 ** self.request.retries)
        raise self.retry(exc=e, countdown=countdown) from e

    except NotificationError as e:
        attempt.status = NotificationAttempt.STATUS_FAILED
        attempt.error_message = str(e)
        attempt.save(update_fields=["status", "error_message"])

        status_code = e.details.get("status_code")

        # Повторяем только при временных сбоях сервиса, а не при ошибках запроса.
        if status_code in RETRYABLE_STATUS_CODES:
            logger.warning(
                f"⚠️ Сервис почты вернул {status_code} "
                f"(попытка {attempt.attempts}/3). Перезапуск: {e}"
            )
            countdown = self.default_retry_delay * (2 ** self.request.retries)
            raise self.retry(exc=e, countdown=countdown) from e

        logger.error(
            f"❌ Неустранимая ошибка сервиса почты. HTTP {status_code}: {e}"
        )

    except Exception as e:
        attempt.status = NotificationAttempt.STATUS_FAILED
        attempt.error_message = f"Непредвиденная ошибка: {e}"
        attempt.save(update_fields=["status", "error_message"])

        logger.error(f"❌ Фатальная ошибка отправки email: {e}", exc_info=True)
        raise

    else:
        attempt.status = NotificationAttempt.STATUS_SENT
        attempt.sent_at = timezone.now()
        attempt.error_message = None
        attempt.save(update_fields=["status", "sent_at", "error_message"])

        logger.info(f"✅ Email отправлен: {task_name} → {to_email}")


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_telegram_notification(self, attempt_id: int, chat_id: str,
                               task_name: str, deadline: str) -> None:
    """Асинхронная задача отправки Telegram-уведомления через Bot API.

    Загружает запись NotificationAttempt по ID, выполняет запрос к
    Telegram Bot API, фиксирует результат в БД.

    Повторяет попытку с экспоненциальной задержкой только при временных сбоях
    (сетевые ошибки, 429 и 5xx). Остальные коды считаются терминальными:
    например, 400 из-за неэкранированной разметки повтором не лечится.

    Args:
        attempt_id: ID записи NotificationAttempt (создаётся оркестратором).
        chat_id: ID чата получателя в Telegram.
        task_name: Название задачи для текста сообщения.
        deadline: Дедлайн задачи (строка).
    """

    # БЛОК 1: Подготовка данных (без логики перезапусков)
    try:
        attempt = NotificationAttempt.objects.get(id=attempt_id)
    except NotificationAttempt.DoesNotExist:
        logger.error(f"❌ NotificationAttempt ID {attempt_id} не существует")
        return

    bot_token = settings.TELEGRAM_BOT_TOKEN
    if not bot_token:
        attempt.status = NotificationAttempt.STATUS_FAILED
        attempt.error_message = "TELEGRAM_BOT_TOKEN не задан в конфигурации Django"
        attempt.save(update_fields=["status", "error_message"])
        logger.error("❌ TELEGRAM_BOT_TOKEN не задан в конфигурации Django")
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    # task_name приходит из пользовательского ввода. Без экранирования
    # символы < > & ломают разметку HTML, и Telegram отвечает 400
    # "can't parse entities", из-за чего уведомление не доставляется вовсе.
    message_text = (
        f"⏰ <b>Время выполнить задачу!</b>\n\n"
        f"💪 <b>Задача:</b> {html.escape(task_name)}\n"
        f"⏳ <b>Дедлайн:</b> {html.escape(deadline)}"
    )
    payload = {
        "chat_id": chat_id,
        "text": message_text,
        "parse_mode": "HTML",
    }

    logger.info(f"📬 Отправляем Telegram: {task_name} → {chat_id}")

    # БЛОК 2: Отправка и обработка исключений
    try:
        attempt.attempts += 1
        attempt.save(update_fields=["attempts"])

        response = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)

        if response.status_code != 200:
            raise NotificationError(
                message=f"Telegram API вернул HTTP {response.status_code}: {response.text}",
                details={
                    "status_code": response.status_code,
                    "response_text": response.text,
                },
            )

    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
        attempt.status = NotificationAttempt.STATUS_FAILED
        attempt.error_message = f"Сетевая ошибка: {e}"
        attempt.save(update_fields=["status", "error_message"])
        logger.warning(f"⚠️ Сетевая ошибка Telegram (попытка {attempt.attempts}/3): {e}")

        # Вычисляем задержку и вызываем ретрай
        countdown = self.default_retry_delay * (2 ** self.request.retries)
        raise self.retry(exc=e, countdown=countdown) from e

    except NotificationError as e:
        attempt.status = NotificationAttempt.STATUS_FAILED
        attempt.error_message = str(e)
        attempt.save(update_fields=["status", "error_message"])

        status_code = e.details.get("status_code")

        # Исправлено: добавлен список кодов [429, 500, 502, 503, 504]
        if status_code in RETRYABLE_STATUS_CODES:
            logger.warning(f"⚠️ Ошибка Telegram API (попытка {attempt.attempts}/3). Перезапуск... Ошибка: {e}")
            countdown = self.default_retry_delay * (2 ** self.request.retries)
            raise self.retry(exc=e, countdown=countdown) from e

        logger.error(f"❌ Фатальная ошибка Telegram API (повторы не требуются). HTTP {status_code}. Ошибка: {e}")

    except Exception as e:
        attempt.status = NotificationAttempt.STATUS_FAILED
        attempt.error_message = f"Непредвиденная ошибка: {e}"
        attempt.save(update_fields=["status", "error_message"])
        logger.error(f"❌ Фатальная ошибка отправки в Telegram: {e}", exc_info=True)
        raise

    else:
        # Успешный исход
        attempt.status = NotificationAttempt.STATUS_SENT
        attempt.sent_at = timezone.now()
        attempt.error_message = None
        attempt.save(update_fields=["status", "sent_at", "error_message"])
        logger.info(f"✅ Telegram отправлен: {task_name} → {chat_id}")


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
