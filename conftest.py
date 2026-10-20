"""Общие pytest-фикстуры проекта."""

import pytest

from users.models import CustomUser


@pytest.fixture
def user(db):
    """Обычный активный пользователь с тарифом BASE (создаётся сигналом)."""
    return CustomUser.objects.create_user(
        username="alice",
        email="alice@example.com",
        password="StrongPass-123",
    )


@pytest.fixture
def other_user(db):
    """Второй пользователь — для проверки изоляции данных."""
    return CustomUser.objects.create_user(
        username="bob",
        email="bob@example.com",
        password="StrongPass-123",
    )


@pytest.fixture
def auth_client(client, user):
    """Django-клиент, авторизованный под фикстурой `user`."""
    client.force_login(user)
    return client
