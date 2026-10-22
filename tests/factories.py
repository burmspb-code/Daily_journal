"""Фабрики тестовых объектов (factory_boy)."""

import factory

from daily.models import Bookmark, Task
from users.models import CustomUser


class UserFactory(factory.django.DjangoModelFactory):
    """Пользователь с тарифом BASE, который создаётся сигналом post_save."""

    class Meta:
        model = CustomUser
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    password = factory.PostGenerationMethodCall("set_password", "StrongPass-123")


class BookmarkFactory(factory.django.DjangoModelFactory):
    """Закладка, по умолчанию принадлежащая новому пользователю."""

    class Meta:
        model = Bookmark

    title = factory.Sequence(lambda n: f"Закладка {n}")
    description = "Тестовое описание закладки"
    owner = factory.SubFactory(UserFactory)


class TaskFactory(factory.django.DjangoModelFactory):
    """Задача; владелец по умолчанию совпадает с владельцем закладки."""

    class Meta:
        model = Task

    title = factory.Sequence(lambda n: f"Задача {n}")
    comment = ""
    bookmark = factory.SubFactory(BookmarkFactory)
    owner = factory.SelfAttribute("bookmark.owner")
