"""
Сервисный слой для бизнес-логики приложения управления пользователями (users).

Данный модуль изолирует сложную логику от представлений (views) и содержит
функции для регистрации аккаунтов, отправки писем верификации и сброса пароля,
а также валидации одноразовых токенов активации.
"""

import requests
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from users.models import CustomUser

from .exceptions import EmailActivationError  # Твое кастомное исключение

# Константа таймаута для HTTP-запроса
REQUEST_TIMEOUT = 15


class InvalidActivationToken(Exception):
    """Исключение для неверного или просроченного токена."""

    pass


def register_inactive_user(request, save_callback):
    """
    Регистрирует пользователя как неактивного и отправляет письмо активации
    через Cloud Function в Yandex Cloud.
    """
    mail_url = getattr(settings, 'MAIL_FUNCTION_URL', None)
    if not mail_url:
        print("❌ MAIL_FUNCTION_URL не настроен в settings.py", flush=True)
        raise ImproperlyConfigured("MAIL_FUNCTION_URL не настроен в settings.py")

    with transaction.atomic():
        print("💾 Начинаем транзакцию. Сохраняем пользователя...", flush=True)

        # 1. Сохраняем пользователя
        user = save_callback()
        user.is_active = False
        user.save()
        print(f"✅ Пользователь {user.email} создан (is_active=False).", flush=True)

        # 2. Генерируем токен и ссылку
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        relative_url = reverse(
            "users:email_confirm", kwargs={"uidb64": uid, "token": token}
        )
        scheme = "https" if request.is_secure() else "http"
        host = request.get_host()
        activation_url = f"{scheme}://{host}{relative_url}"

        subject = "Подтверждение регистрации"
        message = f"Спасибо за регистрацию!\n\nДля активации аккаунта перейдите по ссылке:\n{activation_url}"

        # 3. Формируем payload
        payload = {
            "to_email": user.email,
            "email_type": "registration",
            "subject": subject,
            "body_text": message,
        }

        print(f"📬 Отправляем запрос на {mail_url}", flush=True)
        print(f"📬 Payload: to_email={user.email}, email_type=registration", flush=True)

        try:
            response = requests.post(mail_url, json=payload, timeout=REQUEST_TIMEOUT)

            print(
                f"📥 Получен ответ: Status={response.status_code}, Body={response.text}",
                flush=True,
            )

            if response.status_code != 200:
                print(
                    f"❌ Cloud Function вернула HTTP {response.status_code}",
                    flush=True,
                )
                transaction.set_rollback(True)
                raise EmailActivationError(
                    f"Сервис почты вернул HTTP {response.status_code}: {response.text}"
                )

            print("✅ Письмо успешно отправлено!", flush=True)
            return user

        except requests.exceptions.Timeout as e:
            print("💥 Ошибка: Превышено время ожидания ответа от функции.", flush=True)
            transaction.set_rollback(True)
            raise EmailActivationError("Сервис отправки писем не ответил вовремя.") from e
        except requests.exceptions.ConnectionError as e:
            print("💥 Ошибка: Не удалось соединиться с сервисом отправки писем.", flush=True)
            transaction.set_rollback(True)
            raise EmailActivationError(
                "Не удалось соединиться с сервисом отправки писем."
            ) from e
        except ValueError as e:
            print(f"💥 Ошибка парсинга JSON: {e}", flush=True)
            transaction.set_rollback(True)
            raise EmailActivationError("Неверный формат ответа от сервиса.") from e
        except EmailActivationError:
            raise
        except Exception as e:
            print(f"💥 Непредвиденная ошибка: {e}", flush=True)
            transaction.set_rollback(True)
            raise EmailActivationError(
                "Произошла непредвиденная ошибка при отправке письма."
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
        raise InvalidActivationToken("Неверный идентификатор пользователя.") from None

    if not default_token_generator.check_token(user, token):
        raise InvalidActivationToken(
            "Токен недействителен или его срок действия истек."
        )

    # Переносим логику смены статусов в сервис
    user.is_active = True
    user.email_status = "verified"
    user.save()

    return user
