"""
Сериализаторы основного приложения (daily) для Django REST Framework.
"""
from typing import ClassVar

from rest_framework import serializers

from .models import Bookmark, Task


class TaskSerializer(serializers.ModelSerializer):
    # Выводим человекочитаемое имя закладки (read_only=True означает, что поле только для чтения)
    bookmark_title = serializers.CharField(source="bookmark.title", read_only=True)
    owner_username = serializers.CharField(source="owner.username", read_only=True)
    status_display = serializers.CharField(source="get_status_flag_display", read_only=True)

    class Meta:
        model = Task
        fields = (
            "id",
            "title",
            "created_at",
            "reminder_at",
            "comment",
            "status_flag",
            "status_display",
            "periodicity_value",
            "periodicity_unit",
            "bookmark_title",
            "owner_username",
        )


class BookmarkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bookmark
        fields = "__all__"

    # Говорим DRF, что owner не нужно требовать на вход и валидировать от клиента
    extra_kwargs: ClassVar[dict] = {"owner": {"read_only": True}}


class BookmarkUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bookmark
        fields = ("id", "title", "description")

    def validate_title(self, value):
        if value and not value.strip():
            raise serializers.ValidationError("Название не может быть пустым.")
        return value.strip() if value else value


class TaskUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ("id", "title", "comment", "reminder_at", "status_flag",
                  "periodicity_value", "periodicity_unit")

    def validate_status_flag(self, value):
        """
        Валидация статуса: разрешаем изменение только на 'Выполнена' (2)
        из статусов 'Создана' (0), 'В работе' (1), 'Дедлайн' (3).
        Запрещает любые другие значения статуса.
        """
        if value is not None:
            # Проверяем, что новое значение - это статус "Выполнена"
            if value != Task.StatusChoices.COMPLETED:
                raise serializers.ValidationError(
                    "Разрешено менять статус только на 'Выполнена'"
                )
        return value

    def validate(self, attrs):
        """
        Дополнительная валидация на уровне объекта.
        Проверяем, что текущий статус позволяет изменение.
        """
        # Если пытаемся изменить статус
        if 'status_flag' in attrs and attrs['status_flag'] is not None:
            instance = self.instance
            if instance:
                allowed_current_statuses = [
                    Task.StatusChoices.CREATED,
                    Task.StatusChoices.IN_PROGRESS,
                    Task.StatusChoices.OVERDUE
                ]
                if instance.status_flag not in allowed_current_statuses:
                    raise serializers.ValidationError(
                        {"status_flag": "Текущий статус не позволяет изменение"}
                    )
        return attrs
