"""
Сервисный слой для бизнес-логики приложения управления пользователями (users).

Данный модуль изолирует сложную логику от представлений (views) и содержит
функции для регистрации аккаунтов, отправки писем верификации и сброса пароля,
а также валидации одноразовых токенов активации.
"""

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from users.models import CustomUser


class EmailActivationError(Exception):
    """Исключение для ошибок отправки письма активации."""

    pass


class InvalidActivationToken(Exception):
    """Исключение для неверного или просроченного токена."""

    pass


def register_inactive_user(
    request: HttpRequest, save_callback: Callable[[], User]
) -> User:
    """Бизнес-логика регистрации неактивного пользователя и отправки email.

    Args:
        request: Объект HTTP-запроса (нужен для хоста и схемы).
        save_callback: Функция/метод, который сохраняет пользователя в БД.

    Returns:
        User: Созданный объект пользователя.

    Raises:
        EmailActivationError: Если отправка письма завершилась сбоем.
    """
    with transaction.atomic():
        # Сохраняем пользователя (подходит и для формы, и для сериализатора)
        user = save_callback()
        user.is_active = False
        user.save()

        # Генерируем uid и токен
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        # Собираем абсолютную ссылку активации
        relative_url = reverse(
            "users:email_confirm", kwargs={"uidb64": uid, "token": token}
        )
        scheme = "https" if request.is_secure() else "http"
        host = request.get_host()
        activation_url = f"{scheme}://{host}{relative_url}"

        try:
            send_mail(
                subject="Подтверждение регистрации",
                message=f"Спасибо за регистрацию! Ссылка для активации: {activation_url}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
            return user
        except Exception as e:
            # Отменяем транзакцию в БД
            transaction.set_rollback(True)
            # Выбрасываем понятное сервису исключение
            raise EmailActivationError(
                "Сбой SMTP при отправке письма подтверждения."
            ) from e


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
    ):  # Исправлен синтаксис
        raise InvalidActivationToken("Неверный идентификатор пользователя.")

    if not default_token_generator.check_token(user, token):
        raise InvalidActivationToken(
            "Токен недействителен или его срок действия истек."
        )

    # Переносим логику смены статусов в сервис
    user.is_active = True
    user.email_status = "verified"
    user.save()

    return user
