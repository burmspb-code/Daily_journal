"""
Сервисный слой для бизнес-логики приложения управления пользователями (users).

Данный модуль изолирует сложную логику от представлений (views) и содержит
функции для регистрации аккаунтов, отправки писем верификации и сброса пароля,
а также валидации одноразовых токенов активации.
"""
import logging
from datetime import timedelta
from typing import Callable
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.db.models import F
from django.http.request import HttpRequest
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from users.constants import (
    ACTIVATION_RESEND_COOLDOWN_SECONDS,
    ACTIVATION_RESEND_DAILY_LIMIT,
)
from users.models import CustomUser

from .exceptions import EmailActivationError  # Твое кастомное исключение

logger = logging.getLogger(__name__)

# Константа таймаута для HTTP-запроса
REQUEST_TIMEOUT = 15


class InvalidActivationToken(Exception):
    """Исключение для неверного или просроченного токена."""

    # Аккаунт удалён: регистрация сорвалась, письмо ушло в пустоту.
    REASON_ACCOUNT_MISSING = "account_missing"
    # Аккаунт есть, но ссылка не подошла или истекла.
    REASON_LINK_INVALID = "link_invalid"

    def __init__(self, message, reason=REASON_LINK_INVALID):
        super().__init__(message)
        self.reason = reason


def register_inactive_user(request: HttpRequest, save_callback: Callable[[], CustomUser]) -> CustomUser:
    """
    Регистрирует пользователя как неактивного и отправляет письмо активации
    через Cloud Function в Yandex Cloud.
    """
    mail_url = getattr(settings, "MAIL_FUNCTION_URL", None)
    if not mail_url:
        logger.warning("❌ MAIL_FUNCTION_URL не настроен в settings.py")
        raise ImproperlyConfigured("MAIL_FUNCTION_URL не настроен в settings.py")

    # ШАГ 1: Быстрая и изолированная транзакция БД. Закрывается мгновенно!
    with transaction.atomic():
        logger.info("💾 Сохраняем пользователя в БД...")
        user = save_callback()
        user.is_active = False
        user.save()
        logger.info(f"✅ Пользователь {user.email} успешно сохранен (is_active=False).")

    # ШАГ 2: Подготовка данных (уже вне транзакции, соединение с БД свободно)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    relative_url = reverse("users:email_confirm", kwargs={"uidb64": uid, "token": token})
    scheme = "https" if request.is_secure() else "http"
    host = request.get_host()
    activation_url = f"{scheme}://{host}{relative_url}"

    subject = "Подтверждение регистрации"
    message = f"Спасибо за регистрацию!\n\nДля активации аккаунта перейдите по ссылке:\n{activation_url}"

    payload = {
        "to_email": user.email,
        "email_type": "registration",
        "subject": subject,
        "body_text": message,
    }

    clean_url = urlparse(mail_url).path if mail_url else ""
    logger.info(f"📬 Отправляем запрос на эндпоинт вне транзакции БД: {clean_url}")

    # ШАГ 3: Сетевой запрос. Соединение с БД свободно, поэтому к почтовому
    # сервису мы обращаемся вне transaction.atomic.
    # Аккаунт при любом сбое остаётся в БД в статусе is_active=False:
    # удалять его нельзя, так как письмо могло уже уйти, и ссылка из него
    # должна остаться рабочей. Неактивные аккаунты чистит отдельная
    # плановая задача по возрасту записи, а не этот сервис.
    try:
        response = requests.post(mail_url, json=payload, timeout=REQUEST_TIMEOUT)

        logger.info(f"📥 Получен ответ от почтового сервиса: Status={response.status_code}")
        logger.debug(f"📥 Тело ответа Cloud Function: {response.text}")

    except requests.exceptions.Timeout as e:
        # Письмо могло уйти: ответ не дошёл из-за таймаута. Аккаунт сохранён.
        logger.warning("⚠️ Почтовый сервис не ответил вовремя. Аккаунт сохранён.")
        raise EmailActivationError(
            "Не удалось подтвердить доставку письма. Аккаунт создан, но пока "
            "не активирован — проверьте почту или запросите новую ссылку."
        ) from e

    except requests.exceptions.ConnectionError as e:
        logger.error("💥 Почтовый сервис недоступен. Аккаунт сохранён неактивным.")
        raise EmailActivationError(
            "Почтовый сервис временно недоступен. Аккаунт создан, но пока "
            "не активирован — попробуйте позже или запросите новую ссылку."
        ) from e

    except ValueError as e:
        logger.error(f"💥 Ошибка разбора ответа почтового сервиса: {e}")
        raise EmailActivationError("Неверный формат ответа от сервиса.") from e

    except Exception as e:
        logger.error("💥 Непредвиденная ошибка в сервисе регистрации", exc_info=True)
        raise EmailActivationError(
            "Произошла непредвиденная ошибка при отправке письма. "
            "Аккаунт создан, но пока не активирован."
        ) from e

    if response.status_code != 200:
        # Сервис ответил отказом. Аккаунт остаётся неактивным: возможно,
        # письмо всё же ушло, а удаление обрушило бы ссылку из него.
        logger.error(
            f"❌ Cloud Function вернула HTTP {response.status_code}. "
            "Аккаунт сохранён неактивным."
        )
        raise EmailActivationError(
            f"Сервис почты вернул HTTP {response.status_code}: {response.text}"
        )

    logger.info("✅ Письмо успешно отправлено!")
    return user


def activate_user_by_token(uidb64: str, token: str) -> CustomUser:
    """Проверяет токен, активирует пользователя и меняет статус почты."""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = CustomUser.objects.get(pk=uid)
    except (
        TypeError,
        ValueError,
        OverflowError,
        CustomUser.DoesNotExist,
    ):
        # Пользователя нет — значит регистрация оборвалась на отправке письма.
        # Сообщаем причину отдельно, чтобы показать точное объяснение.
        raise InvalidActivationToken(
            "Аккаунт не найден: вероятно, при регистрации произошёл сбой.",
            reason=InvalidActivationToken.REASON_ACCOUNT_MISSING,
        ) from None

    if not default_token_generator.check_token(user, token):
        raise InvalidActivationToken(
            "Ссылка недействительна или её срок действия истёк.",
            reason=InvalidActivationToken.REASON_LINK_INVALID,
        )

    # Переносим логику смены статусов в сервис
    user.is_active = True
    user.email_status = "verified"
    user.save()

    return user


def _build_activation_payload(request: HttpRequest, user: CustomUser) -> dict:
    """Собирает payload письма активации для конкретного пользователя.

    Args:
        request: HTTP-запрос (нужен для определения схемы и хоста).
        user: Пользователь, которому отправляется письмо.

    Returns:
        dict: Тело запроса к почтовой Cloud Function.
    """
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    relative_url = reverse(
        "users:email_confirm", kwargs={"uidb64": uid, "token": token}
    )
    scheme = "https" if request.is_secure() else "http"
    activation_url = f"{scheme}://{request.get_host()}{relative_url}"

    return {
        "to_email": user.email,
        "email_type": "registration",
        "subject": "Подтверждение регистрации",
        "body_text": (
            "Спасибо за регистрацию!\n\n"
            "Для активации аккаунта перейдите по ссылке:\n"
            f"{activation_url}"
        ),
    }


def _send_activation_mail(request: HttpRequest, user: CustomUser) -> None:
    """Отправляет письмо со ссылкой активации.

    Бросает `EmailActivationError` при любом сбое доставки. Аккаунт при этом
    не трогается: он остаётся неактивным, и пользователь сможет запросить
    ссылку повторно.

    Raises:
        EmailActivationError: Если письмо не удалось отправить.
    """
    mail_url = getattr(settings, "MAIL_FUNCTION_URL", None)
    if not mail_url:
        logger.error("❌ MAIL_FUNCTION_URL не настроен в settings.py")
        raise ImproperlyConfigured("MAIL_FUNCTION_URL не настроен в settings.py")

    payload = _build_activation_payload(request, user)

    clean_url = urlparse(mail_url).path
    logger.info(f"📬 Отправляем ссылку активации на эндпоинт: {clean_url}")

    try:
        response = requests.post(mail_url, json=payload, timeout=REQUEST_TIMEOUT)

        logger.info(f"📥 Ответ почтового сервиса: Status={response.status_code}")
        logger.debug(f"📥 Тело ответа Cloud Function: {response.text}")

    except requests.exceptions.Timeout as e:
        logger.warning("⚠️ Почтовый сервис не ответил вовремя.")
        raise EmailActivationError("Не удалось подтвердить доставку письма.") from e

    except requests.exceptions.ConnectionError as e:
        logger.error("💥 Почтовый сервис недоступен.")
        raise EmailActivationError(
            "Почтовый сервис временно недоступен."
        ) from e

    except ValueError as e:
        logger.error(f"💥 Ошибка разбора ответа почтового сервиса: {e}")
        raise EmailActivationError("Неверный формат ответа от сервиса.") from e

    except Exception as e:
        logger.error("💥 Непредвиденная ошибка при отправке письма", exc_info=True)
        raise EmailActivationError(
            "Произошла непредвиденная ошибка при отправке письма."
        ) from e

    if response.status_code != 200:
        logger.error(f"❌ Cloud Function вернула HTTP {response.status_code}.")
        raise EmailActivationError(
            f"Сервис почты вернул HTTP {response.status_code}"
        )

    logger.info("✅ Письмо со ссылкой активации отправлено.")


def _can_resend_activation(user: CustomUser) -> bool:
    """Проверяет, можно ли отправить ссылку активации повторно.

    Ограничивает частоту отправок двумя правилами: пауза между попытками
    и суточный лимит. Счётчик хранится прямо в записи пользователя, поэтому
    ограничение работает во всех процессах и переживает перезапуск.

    Args:
        user: Пользователь, для которого проверяется возможность отправки.

    Returns:
        bool: True, если повторную отправку разрешено.
    """
    if not user.last_activation_sent_at:
        return True

    now = timezone.now()
    cooldown_passed = (
        now - user.last_activation_sent_at
        >= timedelta(seconds=ACTIVATION_RESEND_COOLDOWN_SECONDS)
    )
    daily_limit_passed = (
        user.last_activation_sent_at >= now - timedelta(days=1)
        and user.activation_emails_sent_today >= ACTIVATION_RESEND_DAILY_LIMIT
    )

    if not cooldown_passed:
        return False
    if daily_limit_passed:
        return False

    return True


def resend_activation_email(request: HttpRequest, email: str) -> bool:
    """Повторно отправляет ссылку активации для неактивного аккаунта.

    Функция намеренно возвращает одинаковый результат для существующего и
    несуществующего адреса, иначе по ней можно было бы перебирать зарегистрированные
    email. Реальная причина отказа пишется только в лог.

    Args:
        request: HTTP-запрос (нужен для сбора ссылки активации).
        email: Адрес электронной почты, указанный пользователем.

    Returns:
        bool: True, если письмо отправлено; False — если отправка невозможна.
    """
    user = CustomUser.objects.filter(email__iexact=email).first()

    # Пользователь не найден либо уже активирован — отвечаем так же, как при успехе
    if user is None or user.is_active:
        logger.info("↩️ Запрос ссылки активации: аккаунт не найден или уже активен.")
        return False

    if not _can_resend_activation(user):
        logger.info(
            f"⏳ Запрос ссылки активации для user_id={user.pk}: "
            "сработало ограничение частоты."
        )
        return False

    _send_activation_mail(request, user)

    # Фиксируем время отправки атомарно, чтобы параллельные запросы
    # не прошли проверку частоты одновременно
    CustomUser.objects.filter(pk=user.pk).update(
        last_activation_sent_at=timezone.now(),
        activation_emails_sent_today=F("activation_emails_sent_today") + 1,
    )
    return True


def mark_activation_sent(user: CustomUser) -> None:
    """Запоминает факт отправки ссылки активации при регистрации.

    Args:
        user: Пользователь, которому только что отправлено письмо.
    """
    CustomUser.objects.filter(pk=user.pk).update(
        last_activation_sent_at=timezone.now(),
        activation_emails_sent_today=F("activation_emails_sent_today") + 1,
    )
