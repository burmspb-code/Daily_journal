"""Тесты критичных сценариев приложения users.

Покрывают регистрацию, активацию по токену, ограничения повторной отправки
письма и расчёт лимитов тарифных планов.
"""

from datetime import timedelta
from unittest import mock

import pytest
import requests
from django.contrib.auth.tokens import default_token_generator
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from users.constants import (
    ACTIVATION_RESEND_COOLDOWN_SECONDS,
    ACTIVATION_RESEND_DAILY_LIMIT,
)
from users.models import CustomUser
from users.services import (
    EmailActivationError,
    InvalidActivationToken,
    _can_resend_activation,
    activate_user_by_token,
    register_inactive_user,
    resend_activation_email,
)

PASSWORD = "StrongPass-123"


def make_user(username="testuser", email="testuser@example.com", *, is_active=True):
    return CustomUser.objects.create_user(
        username=username, email=email, password=PASSWORD, is_active=is_active
    )


def activation_uid(user):
    return urlsafe_base64_encode(force_bytes(user.pk))


# =============================================================================
# РЕГИСТРАЦИЯ
# =============================================================================


@pytest.mark.django_db
@mock.patch("users.services.requests.post")
def test_register_inactive_user_saves_account_and_sends_activation(mock_post):
    """Успешная регистрация: аккаунт создан неактивным, письмо отправлено."""
    mock_post.return_value.status_code = 200
    mock_post.return_value.text = "ok"
    request = RequestFactory().post("/users/register/")

    user = register_inactive_user(
        request,
        save_callback=lambda: make_user("newbie", "newbie@example.com", is_active=True),
    )

    assert user.is_active is False
    assert CustomUser.objects.filter(email="newbie@example.com").exists()

    payload = mock_post.call_args.kwargs["json"]
    assert payload["to_email"] == "newbie@example.com"
    assert payload["email_type"] == "registration"
    assert "email-confirm" in payload["body_text"]


@pytest.mark.django_db
@mock.patch(
    "users.services.requests.post",
    side_effect=requests.exceptions.ConnectionError("mail service is down"),
)
def test_register_keeps_account_inactive_when_mail_service_unavailable(_mock_post):
    """Сбой почтового сервиса не удаляет аккаунт и не активирует его."""
    request = RequestFactory().post("/users/register/")

    with pytest.raises(EmailActivationError):
        register_inactive_user(
            request,
            save_callback=lambda: make_user("unlucky", "unlucky@example.com"),
        )

    created = CustomUser.objects.get(email="unlucky@example.com")
    assert created.is_active is False


@pytest.mark.django_db
@mock.patch("users.services.requests.post")
def test_register_raises_on_non_200_response(mock_post):
    """HTTP-отказ почтовой функции считается ошибкой доставки."""
    mock_post.return_value.status_code = 503
    mock_post.return_value.text = "Service Unavailable"
    request = RequestFactory().post("/users/register/")

    with pytest.raises(EmailActivationError):
        register_inactive_user(
            request,
            save_callback=lambda: make_user("another", "another@example.com"),
        )


@pytest.mark.django_db
@mock.patch("users.services.requests.post")
def test_register_view_creates_inactive_user(mock_post, client):
    """Сквозной сценарий регистрации через веб-форму."""
    mock_post.return_value.status_code = 200
    mock_post.return_value.text = "ok"

    response = client.post(
        reverse("users:register"),
        {
            "username": "webuser",
            "email": "webuser@example.com",
            "phone_number": "",
            "tg_chat_id": "",
            "password1": PASSWORD,
            "password2": PASSWORD,
        },
    )

    assert response.status_code == 302
    assert response.url == reverse("users:email_confirmation_sent")
    assert CustomUser.objects.get(username="webuser").is_active is False


# =============================================================================
# АКТИВАЦИЯ ПО ТОКЕНУ
# =============================================================================


@pytest.mark.django_db
def test_activate_user_by_valid_token():
    """Валидный токен переводит аккаунт в активное состояние."""
    user = make_user(is_active=False)
    token = default_token_generator.make_token(user)

    activated = activate_user_by_token(activation_uid(user), token)

    assert activated.pk == user.pk
    activated.refresh_from_db()
    assert activated.is_active is True


@pytest.mark.django_db
def test_activate_user_with_invalid_token_raises():
    """Неверный токен не активирует аккаунт."""
    user = make_user(is_active=False)

    with pytest.raises(InvalidActivationToken) as exc_info:
        activate_user_by_token(activation_uid(user), "definitely-wrong-token")

    assert exc_info.value.reason == InvalidActivationToken.REASON_LINK_INVALID
    user.refresh_from_db()
    assert user.is_active is False


@pytest.mark.django_db
def test_activate_unknown_user_reports_missing_account():
    """Ссылка для несуществующего аккаунта даёт отдельную причину отказа."""
    unknown_uid = urlsafe_base64_encode(force_bytes(999_999))

    with pytest.raises(InvalidActivationToken) as exc_info:
        activate_user_by_token(unknown_uid, "any-token")

    assert exc_info.value.reason == InvalidActivationToken.REASON_ACCOUNT_MISSING


# =============================================================================
# ОГРАНИЧЕНИЯ ПОВТОРНОЙ ОТПРАВКИ
# =============================================================================


@pytest.mark.django_db
def test_resend_is_blocked_during_cooldown():
    user = make_user(is_active=False)
    user.last_activation_sent_at = timezone.now() - timedelta(
        seconds=ACTIVATION_RESEND_COOLDOWN_SECONDS - 1
    )
    user.activation_emails_sent_today = 1
    user.save(update_fields=["last_activation_sent_at", "activation_emails_sent_today"])

    assert _can_resend_activation(user) is False


@pytest.mark.django_db
def test_resend_is_blocked_by_daily_limit():
    user = make_user(is_active=False)
    user.last_activation_sent_at = timezone.now() - timedelta(
        seconds=ACTIVATION_RESEND_COOLDOWN_SECONDS + 1
    )
    user.activation_emails_sent_today = ACTIVATION_RESEND_DAILY_LIMIT
    user.save(update_fields=["last_activation_sent_at", "activation_emails_sent_today"])

    assert _can_resend_activation(user) is False


@pytest.mark.django_db
@mock.patch("users.services.requests.post")
def test_resend_activation_sends_mail_and_updates_counters(mock_post):
    mock_post.return_value.status_code = 200
    mock_post.return_value.text = "ok"
    user = make_user(is_active=False)
    request = RequestFactory().post("/users/resend-activation/")

    assert resend_activation_email(request, user.email) is True

    user.refresh_from_db()
    assert user.last_activation_sent_at is not None
    assert user.activation_emails_sent_today == 1
    mock_post.assert_called_once()


@pytest.mark.django_db
@mock.patch("users.services.requests.post")
def test_resend_activation_is_silent_for_unknown_and_active_accounts(mock_post):
    """Ответ не раскрывает, существует ли адрес: письма просто не отправляются."""
    active_user = make_user(is_active=True)
    request = RequestFactory().post("/users/resend-activation/")

    assert resend_activation_email(request, "nobody@example.com") is False
    assert resend_activation_email(request, active_user.email) is False
    mock_post.assert_not_called()


# =============================================================================
# ТАРИФНЫЕ ПЛАНЫ
# =============================================================================


@pytest.mark.django_db
def test_new_user_gets_base_tariff_plan():
    user = make_user()

    plan = user.tariff_plan

    assert plan.plan_name == "BASE"
    assert plan.max_tasks == 50
    assert plan.max_bookmarks == 5


@pytest.mark.django_db
def test_tariff_plan_recalculates_limits_on_save():
    plan = make_user().tariff_plan

    plan.plan_name = "PREMIUM"
    plan.save()
    plan.refresh_from_db()

    assert plan.max_tasks == 250
    assert plan.max_bookmarks == 20


@pytest.mark.django_db
def test_superuser_gets_extended_limits():
    admin = CustomUser.objects.create_superuser(
        username="root", email="root@example.com", password=PASSWORD
    )

    plan = admin.tariff_plan

    assert plan.max_tasks == 500
    assert plan.max_bookmarks == 50
