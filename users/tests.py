"""Тесты критичных сценариев приложения users.

Покрывают регистрацию, активацию по токену, ограничения повторной отправки
письма и расчёт лимитов тарифных планов.
"""

import json
from datetime import timedelta
from unittest import mock

import pytest
from django.contrib.auth.tokens import default_token_generator
from django.test import RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from users.constants import (
    ACTIVATION_RESEND_COOLDOWN_SECONDS,
    ACTIVATION_RESEND_DAILY_LIMIT,
    ACTIVATION_RESEND_WINDOW,
)
from users.models import CustomUser
from users.services import (
    EmailActivationError,
    InvalidActivationToken,
    _can_resend_activation,
    activate_user_by_token,
    mark_activation_sent,
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
@mock.patch("users.services.send_mail", return_value=1)
def test_register_inactive_user_saves_account_and_sends_activation(mock_send_mail):
    """Успешная регистрация: аккаунт создан неактивным, письмо отправлено."""
    request = RequestFactory().post("/users/register/")

    user = register_inactive_user(
        request,
        save_callback=lambda: make_user("newbie", "newbie@example.com", is_active=True),
    )

    assert user.is_active is False
    assert CustomUser.objects.filter(email="newbie@example.com").exists()

    mock_send_mail.assert_called_once()
    kwargs = mock_send_mail.call_args.kwargs
    assert kwargs["recipient_list"] == ["newbie@example.com"]
    assert "email-confirm" in kwargs["message"]
    assert kwargs["fail_silently"] is False


@pytest.mark.django_db
@mock.patch("users.services.send_mail", return_value=1)
def test_register_marks_activation_as_sent(_mock_send_mail):
    """После регистрации кулдаун повторной отправки уже действует."""
    request = RequestFactory().post("/users/register/")

    user = register_inactive_user(
        request,
        save_callback=lambda: make_user("sent", "sent@example.com"),
    )

    user.refresh_from_db()
    assert user.last_activation_sent_at is not None
    assert user.activation_emails_sent_today == 1
    assert _can_resend_activation(user) is False


@pytest.mark.django_db
@mock.patch(
    "users.services.send_mail",
    side_effect=OSError("Network is unreachable"),
)
def test_register_keeps_account_inactive_when_email_service_unavailable(_mock_send_mail):
    """Сбой почтового сервиса не удаляет аккаунт, не активирует его и не тратит лимит."""
    request = RequestFactory().post("/users/register/")

    with pytest.raises(EmailActivationError):
        register_inactive_user(
            request,
            save_callback=lambda: make_user("unlucky", "unlucky@example.com"),
        )

    created = CustomUser.objects.get(email="unlucky@example.com")
    assert created.is_active is False
    assert created.last_activation_sent_at is None
    assert created.activation_emails_sent_today == 0


@pytest.mark.django_db
@mock.patch("users.services.send_mail", return_value=0)
def test_register_raises_when_email_service_sends_nothing(_mock_send_mail):
    """Если бэкенд не принял ни одного письма, это считается ошибкой доставки."""
    request = RequestFactory().post("/users/register/")

    with pytest.raises(EmailActivationError):
        register_inactive_user(
            request,
            save_callback=lambda: make_user("another", "another@example.com"),
        )


@pytest.mark.django_db
@mock.patch("users.services.send_mail", return_value=1)
def test_register_view_creates_inactive_user(mock_send_mail, client):
    """Сквозной сценарий регистрации через веб-форму."""
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
        secure=True,
    )

    assert response.status_code == 302
    assert response.url == reverse("users:email_confirmation_sent")
    created = CustomUser.objects.get(username="webuser")
    assert created.is_active is False
    assert created.last_activation_sent_at is not None
    mock_send_mail.assert_called_once()


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
def test_resend_is_allowed_after_daily_window():
    """Через сутки после последней отправки лимит снова действует с нуля."""
    user = make_user(is_active=False)
    user.last_activation_sent_at = timezone.now() - ACTIVATION_RESEND_WINDOW - timedelta(seconds=1)
    user.activation_emails_sent_today = ACTIVATION_RESEND_DAILY_LIMIT
    user.save(update_fields=["last_activation_sent_at", "activation_emails_sent_today"])

    assert _can_resend_activation(user) is True


@pytest.mark.django_db
def test_mark_activation_sent_increments_counter_within_window():
    """Внутри суток счётчик растёт, а не сбрасывается."""
    user = make_user(is_active=False)
    user.last_activation_sent_at = timezone.now() - timedelta(hours=1)
    user.activation_emails_sent_today = 2
    user.save(update_fields=["last_activation_sent_at", "activation_emails_sent_today"])

    mark_activation_sent(user)

    user.refresh_from_db()
    assert user.activation_emails_sent_today == 3


@pytest.mark.django_db
def test_mark_activation_sent_resets_counter_after_daily_window():
    """Если прошло больше суток, счётчик начинается заново с единицы."""
    user = make_user(is_active=False)
    user.last_activation_sent_at = timezone.now() - ACTIVATION_RESEND_WINDOW - timedelta(minutes=1)
    user.activation_emails_sent_today = ACTIVATION_RESEND_DAILY_LIMIT
    user.save(update_fields=["last_activation_sent_at", "activation_emails_sent_today"])

    mark_activation_sent(user)

    user.refresh_from_db()
    assert user.activation_emails_sent_today == 1


@pytest.mark.django_db
@mock.patch("users.services.send_mail", return_value=1)
def test_resend_activation_starts_new_window_after_day(_mock_send_mail):
    """Ресенд после суток молчания снова разрешён и обнуляет счётчик."""
    user = make_user(is_active=False)
    user.last_activation_sent_at = timezone.now() - ACTIVATION_RESEND_WINDOW - timedelta(minutes=1)
    user.activation_emails_sent_today = ACTIVATION_RESEND_DAILY_LIMIT
    user.save(update_fields=["last_activation_sent_at", "activation_emails_sent_today"])
    request = RequestFactory().post("/users/resend-activation/")

    assert resend_activation_email(request, user.email) is True

    user.refresh_from_db()
    assert user.activation_emails_sent_today == 1
    assert user.last_activation_sent_at > timezone.now() - timedelta(seconds=5)


@pytest.mark.django_db
@mock.patch("users.services.send_mail", return_value=1)
def test_resend_activation_sends_mail_and_updates_counters(mock_send_mail):
    user = make_user(is_active=False)
    request = RequestFactory().post("/users/resend-activation/")

    assert resend_activation_email(request, user.email) is True

    user.refresh_from_db()
    assert user.last_activation_sent_at is not None
    assert user.activation_emails_sent_today == 1
    mock_send_mail.assert_called_once()
    assert mock_send_mail.call_args.kwargs["recipient_list"] == [user.email]


@pytest.mark.django_db
@mock.patch("users.services.send_mail", return_value=1)
def test_resend_activation_is_silent_for_unknown_and_active_accounts(mock_send_mail):
    """Ответ не раскрывает, существует ли адрес: письма просто не отправляются."""
    active_user = make_user(is_active=True)
    request = RequestFactory().post("/users/resend-activation/")

    assert resend_activation_email(request, "nobody@example.com") is False
    assert resend_activation_email(request, active_user.email) is False
    mock_send_mail.assert_not_called()


@pytest.mark.django_db
@mock.patch("users.services.send_mail", return_value=1)
def test_resend_view_redirects_on_success(mock_send_mail, client):
    """Успешная повторная отправка ведёт на страницу «письмо отправлено»."""
    user = make_user(is_active=False)

    response = client.post(
        reverse("users:resend_activation"),
        {"email": user.email},
        secure=True,
    )

    assert response.status_code == 302
    assert response.url == reverse("users:email_confirmation_sent")
    mock_send_mail.assert_called_once()


@pytest.mark.django_db
@mock.patch(
    "users.services.send_mail",
    side_effect=OSError("Network is unreachable"),
)
def test_resend_view_shows_error_instead_of_500_on_email_service_failure(
    _mock_send_mail, client
):
    """Сбой почтового сервиса при повторной отправке даёт ошибку, а не HTTP 500."""
    user = make_user(is_active=False)

    response = client.post(
        reverse("users:resend_activation"),
        {"email": user.email},
        secure=True,
    )

    assert response.status_code == 200
    assert response.context["form"].is_bound
    assert "Не удалось отправить письмо активации" in response.content.decode()

    user.refresh_from_db()
    assert user.last_activation_sent_at is None
    assert user.activation_emails_sent_today == 0


@pytest.mark.django_db
@override_settings(
    EMAIL_BACKEND="anymail.backends.brevo.EmailBackend",
    ANYMAIL={"BREVO_API_KEY": "test-key"},
    DEFAULT_FROM_EMAIL="mib.dev@yandex.ru",
)
@mock.patch("requests.Session.request")
def test_resend_activation_uses_brevo_https_api(mock_request):
    """Письмо уходит в Brevo по HTTPS, а не через заблокированный SMTP."""
    mock_request.return_value.status_code = 201
    mock_request.return_value.json.return_value = {"messageId": "<test@brevo>"}

    user = make_user(is_active=False)
    request = RequestFactory().post("/users/resend-activation/")

    assert resend_activation_email(request, user.email) is True

    call = mock_request.call_args.kwargs
    assert call["url"] == "https://api.brevo.com/v3/smtp/email"
    assert call["method"] == "POST"
    assert call["headers"]["api-key"] == "test-key"

    payload = json.loads(call["data"])
    assert payload["sender"] == {"email": "mib.dev@yandex.ru"}
    assert payload["to"] == [{"email": user.email}]
    assert "email-confirm" in payload["textContent"]


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
