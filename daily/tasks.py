import html
import logging
import smtplib

import requests
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from daily.exceptions import RETRYABLE_STATUS_CODES, NotificationError
from daily.models import NotificationAttempt

logger = logging.getLogger(__name__)

# Единый таймаут для всех исходящих HTTP-запросов к внешним сервисам
REQUEST_TIMEOUT = 15


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_email_notification(self, attempt_id: int, to_email: str,
                            task_name: str, deadline: str,
                            is_late: bool = False) -> None:
    """Асинхронная задача отправки email-уведомления через настроенный Django email backend.

    Загружает запись NotificationAttempt по ID, отправляет письмо через
    настроенный почтовый бэкенд Django (send_mail) и фиксирует результат в БД.

    Повторяет попытку с экспоненциальной задержкой только при временных сбоях
    (сетевые таймауты, разрывы соединения и временные коды ошибок SMTP 4xx).
    Постоянные ошибки (например, ошибка авторизации или отклонение писем 5xx)
    считаются терминальными: повтор не изменит результат, поэтому попытка
    фиксируется как failed.

    Args:
        attempt_id: ID записи NotificationAttempt (создаётся оркестратором).
        to_email: Email получателя.
        task_name: Название задачи для текста письма.
        deadline: Дедлайн задачи (строка).
        is_late: True, если напоминание доставляется с опозданием (простоем
            сервера); в текст добавляется пометка «Пропущенное напоминание».
    """
    try:
        attempt = NotificationAttempt.objects.get(id=attempt_id)
    except NotificationAttempt.DoesNotExist:
        logger.error(f"❌ NotificationAttempt ID {attempt_id} не существует")
        return

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or getattr(
        settings, "EMAIL_HOST_USER", None
    )

    if not from_email:
        attempt.status = NotificationAttempt.STATUS_FAILED
        attempt.error_message = "DEFAULT_FROM_EMAIL / EMAIL_HOST_USER не настроены в settings.py"
        attempt.save(update_fields=["status", "error_message"])
        logger.error("❌ DEFAULT_FROM_EMAIL / EMAIL_HOST_USER не настроены в settings.py")
        return

    if is_late:
        subject = "Пропущенное напоминание о задаче — Daily Journal"
        header = "⚠️ Пропущенное напоминание! Время выполнить задачу:"
    else:
        subject = "Напоминание о задаче — Daily Journal"
        header = "⏰ Время выполнить задачу!"

    message = (
        f"{header}\n\n"
        f"Задача: {task_name}\n"
        f"Дедлайн: {deadline}"
    )

    logger.info(f"📬 Отправляем email: {task_name} → {to_email}")

    try:
        attempt.attempts += 1
        attempt.save(update_fields=["attempts"])

        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[to_email],
            fail_silently=False,
        )

    except (TimeoutError, ConnectionError, smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError) as e:
        attempt.status = NotificationAttempt.STATUS_FAILED
        attempt.error_message = f"Сетевая ошибка SMTP: {e}"
        attempt.save(update_fields=["status", "error_message"])

        logger.warning(
            f"⚠️ Сетевая ошибка email (попытка {attempt.attempts}/3): {e}"
        )
        countdown = self.default_retry_delay * (2 ** self.request.retries)
        raise self.retry(exc=e, countdown=countdown) from e

    except smtplib.SMTPAuthenticationError as e:
        # Неверный логин или пароль приложения — повторять бессмысленно
        attempt.status = NotificationAttempt.STATUS_FAILED
        attempt.error_message = f"Ошибка авторизации SMTP ({e.smtp_code}): {e.smtp_error}"
        attempt.save(update_fields=["status", "error_message"])

        logger.error(f"❌ Неустранимая ошибка авторизации SMTP: {e}")

    except smtplib.SMTPRecipientsRefused as e:
        attempt.status = NotificationAttempt.STATUS_FAILED
        attempt.error_message = f"Получатель отклонён SMTP: {e.recipients}"
        attempt.save(update_fields=["status", "error_message"])

        recipient_codes = [code for code, _ in e.recipients.values()]
        if recipient_codes and all(400 <= code < 500 for code in recipient_codes):
            logger.warning(
                f"⚠️ SMTP временно отклонил получателя "
                f"(попытка {attempt.attempts}/3): {e.recipients}"
            )
            countdown = self.default_retry_delay * (2 ** self.request.retries)
            raise self.retry(exc=e, countdown=countdown) from e

        logger.error(f"❌ Неустранимая ошибка SMTP: получатель отклонён: {e.recipients}")

    except smtplib.SMTPResponseException as e:
        attempt.status = NotificationAttempt.STATUS_FAILED
        attempt.error_message = f"SMTP вернул код {e.smtp_code}: {e.smtp_error}"
        attempt.save(update_fields=["status", "error_message"])

        # Коды 4xx (например, 421, 451) — временные сбои/лимиты, повторяем
        if 400 <= e.smtp_code < 500:
            logger.warning(
                f"⚠️ SMTP вернул временный код {e.smtp_code} "
                f"(попытка {attempt.attempts}/3). Перезапуск: {e}"
            )
            countdown = self.default_retry_delay * (2 ** self.request.retries)
            raise self.retry(exc=e, countdown=countdown) from e

        # Коды 5xx (несуществующий ящик, спам-блок и т.д.) — терминальные
        logger.error(
            f"❌ Неустранимая ошибка SMTP. Код {e.smtp_code}: {e}"
        )

    except smtplib.SMTPException as e:
        attempt.status = NotificationAttempt.STATUS_FAILED
        attempt.error_message = f"Ошибка SMTP: {e}"
        attempt.save(update_fields=["status", "error_message"])

        logger.error(f"❌ Неустранимая ошибка SMTP: {e}", exc_info=True)

    except Exception as e:
        attempt.status = NotificationAttempt.STATUS_FAILED
        attempt.error_message = f"Непредвиденная ошибка: {e}"
        attempt.save(update_fields=["status", "error_message"])

        logger.error(f"❌ Фатальная ошибка отправки email: {e}", exc_info=True)
        raise

    else:
        attempt.status = NotificationAttempt.STATUS_SENT
        attempt.sent_at = timezone.now()
        # Поле NOT NULL (blank=True без null=True): очищаем пустой строкой,
        # а не None, иначе PostgreSQL падает на IntegrityError и попытка
        # остаётся pending, хотя письмо уже доставлено.
        attempt.error_message = ""
        attempt.save(update_fields=["status", "sent_at", "error_message"])

        logger.info(f"✅ Email отправлен: {task_name} → {to_email}")


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_telegram_notification(self, attempt_id: int, chat_id: str,
                               task_name: str, deadline: str,
                               is_late: bool = False) -> None:
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
        is_late: True, если напоминание доставляется с опозданием (простом
            сервера); в текст добавляется пометка «Пропущенное напоминание».
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
    header = (
        "⏰ <b>Пропущенное напоминание</b>"
        if is_late
        else "⏰ <b>Время выполнить задачу!</b>"
    )
    message_text = (
        f"{header}\n\n"
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
        # Поле NOT NULL (blank=True без null=True): очищаем пустой строкой,
        # а не None, иначе PostgreSQL падает на IntegrityError и попытка
        # остаётся pending, хотя письмо уже доставлено.
        attempt.error_message = ""
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
