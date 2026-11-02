"""
Сервисный слой для бизнес-логики приложения управления пользователями (users).

Данный модуль изолирует сложную логику от представлений (views) и содержит
функции для регистрации аккаунтов, отправки писем верификации и сброса пароля,
а также валидации одноразовых токенов активации.
"""
import logging
from datetime import timedelta
from typing import Callable

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Case, F, Value, When
from django.http.request import HttpRequest
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.html import strip_tags
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from users.constants import (
    ACTIVATION_RESEND_COOLDOWN_SECONDS,
    ACTIVATION_RESEND_DAILY_LIMIT,
    ACTIVATION_RESEND_WINDOW,
)
from users.models import CustomUser

from .exceptions import EmailActivationError  # Твое кастомное исключение

logger = logging.getLogger(__name__)


class InvalidActivationToken(Exception):
    """Исключение для неверного или просроченного токена."""

    # Аккаунт удалён: регистрация сорвалась, письмо ушло в пустоту.
    REASON_ACCOUNT_MISSING = "account_missing"
    # Аккаунт есть, но ссылка не подошла или истекла.
    REASON_LINK_INVALID = "link_invalid"

    def __init__(self, message, reason=REASON_LINK_INVALID):
        super().__init__(message)
        self.reason = reason


def _send_email(
    *,
    subject: str,
    message: str,
    recipient: str,
    html_message: str | None = None,
    error_message: str = "Не удалось отправить письмо через почтовый сервер.",
) -> None:
    """Отправляет письмо через настроенный email-backend (сейчас Brevo API).

    ``send_mail`` с ``fail_silently=False`` бросает исключения почтового
    провайдера, поэтому представления получают единый тип ошибки и могут
    показать пользователю понятное сообщение вместо страницы 500.
    """
    try:
        sent = send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            html_message=html_message,
            fail_silently=False,
        )
    except Exception as e:
        logger.error("💥 Ошибка отправки письма на %s", recipient, exc_info=True)
        raise EmailActivationError(error_message) from e

    if sent != 1:
        logger.error(
            "❌ Почтовый сервис принял %s писем вместо одного для %s",
            sent,
            recipient,
        )
        raise EmailActivationError(error_message)

    logger.info("✅ Письмо отправлено на %s", recipient)


def register_inactive_user(request: HttpRequest, save_callback: Callable[[], CustomUser]) -> CustomUser:
    """
    Регистрирует пользователя как неактивного и отправляет письмо активации
    через настроенный email-backend.

    Аккаунт при любом сбое отправки остаётся в БД в статусе is_active=False:
    удалять его нельзя, так как письмо могло уже уйти, и ссылка из него
    должна остаться рабочей. Неактивные аккаунты чистит отдельная плановая
    задача по возрасту записи, а не этот сервис.
    """
    # ШАГ 1: Быстрая и изолированная транзакция БД. Закрывается мгновенно!
    with transaction.atomic():
        logger.info("💾 Сохраняем пользователя в БД...")
        user = save_callback()
        user.is_active = False
        user.save()
        logger.info(f"✅ Пользователь {user.email} успешно сохранен (is_active=False).")

    # ШАГ 2: Подготовка письма уже вне транзакции, соединение с БД свободно.
    payload = _build_activation_payload(request, user)

    # ШАГ 3: Отправка через email-backend. Аккаунт остаётся неактивным при ошибке.
    try:
        _send_email(
            subject=payload["subject"],
            message=payload["body_text"],
            recipient=user.email,
            error_message=(
                "Не удалось отправить письмо активации. Аккаунт создан, но пока "
                "не активирован — запросите новую ссылку."
            ),
        )
    except EmailActivationError:
        logger.error("💥 Не удалось отправить письмо активации для %s", user.email)
        raise

    # Фиксируем факт отправки, чтобы кулдаун и суточный лимит повторных
    # запросов учитывали письмо, отправленное при регистрации.
    mark_activation_sent(user)

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

    if user.is_active:
        raise InvalidActivationToken(
            "Аккаунт уже активирован.",
            reason=InvalidActivationToken.REASON_LINK_INVALID,
        )

    # Переносим логику смены статусов в сервис
    user.is_active = True
    user.save()

    return user


def send_password_reset_mail(request: HttpRequest, user: CustomUser) -> None:
    """Отправляет письмо со ссылкой для сброса пароля через стандартный email-backend Django.

    Бросает `EmailActivationError` при любом сбое доставки.
    """
    try:
        # Генерируем uid и токен
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        # Формируем контекст для ссылки (учитываем глобальный алиас или users:)
        # Если вы перенесли алиас в config/urls.py, имя будет просто 'password_reset_confirm'
        # Если оставили внутри users, то 'users:password_reset_confirm'
        url_name = "password_reset_confirm"

        protocol = "https" if request.is_secure() else "http"
        domain = request.get_host()

        # Строим полноценную ссылку для сброса пароля
        reset_link = f"{protocol}://{domain}/users/password-reset/confirm/{uid}/{token}/"

        logger.info(f"📬 Сформирована ссылка для сброса: {reset_link}")

        # Собираем контекст для шаблона письма
        context = {
            "user": user,
            "reset_link": reset_link,
        }

        # Рендерим HTML-письмо (укажите ваш путь к шаблону письма)
        html_message = render_to_string("users/password_reset_email.html", context)
        # Создаем текстовую копию письма на случай, если почтовик клиента не поддерживает HTML
        plain_message = strip_tags(html_message)

        # Отправляем встроенным методом Django
        logger.info(f"📧 Отправляем письмо на {user.email}...")
        send_mail(
            subject="Сброс пароля — Daily Journal",
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,  # Чтобы Django честно бросал ошибку, если сервис недоступен
        )

    except Exception as e:
        logger.error("💥 Ошибка при отправке письма сброса пароля", exc_info=True)
        raise EmailActivationError("Произошла ошибка при отправке письма через почтовый сервис.") from e

    logger.info("✅ Письмо со ссылкой сброса пароля успешно отправлено.")


def _build_password_reset_payload(request: HttpRequest, user: CustomUser, uidb64: str, token: str) -> dict:
    """Собирает payload письма сброса пароля для конкретного пользователя."""
    relative_url = reverse("users:password_reset_confirm", kwargs={"uidb64": uidb64, "token": token})
    scheme = "https" if request.is_secure() else "http"
    activation_url = f"{scheme}://{request.get_host()}{relative_url}"

    return {
        "to_email": user.email,
        "email_type": "password_reset",
        "subject": "Сброс пароля",
        "body_text": (
            "Вы запросили сброс пароля.\n\n"
            "Для установки нового пароля перейдите по ссылке:\n"
            f"{activation_url}\n\n"
            "Если вы не запрашивали сброс — просто проигнорируйте это письмо."
        ),
    }


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
    """Отправляет письмо со ссылкой активации через настроенный email-backend.

    Raises:
        EmailActivationError: Если письмо не удалось отправить.
    """
    payload = _build_activation_payload(request, user)
    _send_email(
        subject=payload["subject"],
        message=payload["body_text"],
        recipient=user.email,
        error_message="Не удалось отправить письмо активации.",
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
    elapsed = now - user.last_activation_sent_at

    # С момента последней отправки прошло больше суток — началось новое
    # окно, лимит и кулдаун прошлых суток больше не действуют.
    if elapsed >= ACTIVATION_RESEND_WINDOW:
        return True

    # Внутри суточного окна сначала проверяем кулдаун, затем количество
    # отправок: он не должен превышать суточный лимит.
    if elapsed < timedelta(seconds=ACTIVATION_RESEND_COOLDOWN_SECONDS):
        return False

    return user.activation_emails_sent_today < ACTIVATION_RESEND_DAILY_LIMIT


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
    # не прошли проверку частоты одновременно.
    mark_activation_sent(user)
    return True


def mark_activation_sent(user: CustomUser) -> None:
    """Запоминает факт отправки ссылки активации при регистрации.

    Обновляет и запись в БД, и переданный экземпляр пользователя, чтобы
    вызывающий код видел актуальные значения без дополнительного запроса.

    Args:
        user: Пользователь, которому только что отправлено письмо.
    """
    sent_at = timezone.now()
    window_start = sent_at - ACTIVATION_RESEND_WINDOW

    # CASE читает старое значение last_activation_sent_at: если прошло больше
    # суток (или отправки ещё не было), начинаем счёт заново с единицы.
    # Счётчик присваивается первым, чтобы порядок SET не влиял на результат
    # в СУБД, которые вычисляют выражения слева направо (например, MySQL).
    CustomUser.objects.filter(pk=user.pk).update(
        activation_emails_sent_today=Case(
            When(last_activation_sent_at__isnull=True, then=Value(1)),
            When(last_activation_sent_at__lte=window_start, then=Value(1)),
            default=F("activation_emails_sent_today") + 1,
        ),
        last_activation_sent_at=sent_at,
    )

    # Синхронизируем экземпляр в памяти, чтобы вызывающий код видел
    # актуальные значения без дополнительного запроса.
    new_window = (
        user.last_activation_sent_at is None
        or user.last_activation_sent_at <= window_start
    )
    user.activation_emails_sent_today = (
        1 if new_window else (user.activation_emails_sent_today or 0) + 1
    )
    user.last_activation_sent_at = sent_at
